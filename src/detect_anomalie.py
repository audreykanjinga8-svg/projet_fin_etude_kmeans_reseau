#!/usr/bin/env python3
import sys
import os
import json
import time
import struct
import tempfile
import subprocess
import argparse
import logging
from pathlib import Path

import pandas as pd
import numpy as np
import joblib

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config as cfg

PCAP_PAR_DEFAUT = (
    "/home/audrey/GNS3/projects/Projet_Final_topo/project-files/captures/"
    "AlpiNet-6_eth0_to_SwitchDatacenter_Ethernet02.pcap"
)
ZABBIX_SERVER = "127.0.0.1"
ZABBIX_HOST = "Detection-KMeans"
ZABBIX_CLE = "kmeans.regime"
MAX_FENETRES_VIDES_CONSECUTIVES = 5

FEATURES = cfg.FEATURES
FENETRE_SEC = cfg.FENETRE_SEC

CHAMPS = ["frame.time_relative", "frame.len", "_ws.col.Protocol", "eth.src",
          "ip.dst", "tcp.window_size", "tcp.dstport", "udp.dstport",
          "tcp.flags.syn", "tcp.flags.ack", "tcp.flags.reset",
          "tcp.analysis.retransmission", "tcp.analysis.zero_window",
          "tcp.analysis.out_of_order",
          "arp.duplicate-address-detected", "icmp.type", "icmp.seq"]

LOG_FILE = Path(__file__).resolve().parent / "detect_anomalie.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("detect_anomalie")


class CaptureIncrementale:
    def __init__(self, path):
        self.path = path
        self.prefix = b""
        self.offset = 0
        self.fmt = None
        self.endian = "<"
        self._init()

    def _init(self):
        with open(self.path, "rb") as f:
            magic = f.read(4)
        if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
            self.fmt, self.endian = "pcap", "<"
        elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
            self.fmt, self.endian = "pcap", ">"
        elif magic == b"\x0a\x0d\x0d\x0a":
            self.fmt = "pcapng"
        else:
            self.fmt = None
            log.warning("Format pcap inconnu -> lecture du fichier entier (peut ralentir).")
            return
        if self.fmt == "pcap":
            with open(self.path, "rb") as f:
                self.prefix = f.read(24)
            self.offset = os.path.getsize(self.path)
        else:
            self._init_pcapng()
        log.info("Capture incrementale active (format=%s).", self.fmt)

    def _init_pcapng(self):
        with open(self.path, "rb") as f:
            data = f.read()
        bom = data[8:12]
        self.endian = "<" if bom == b"\x4d\x3c\x2b\x1a" else ">"
        pos = 0
        prefix_end = 0
        while pos + 12 <= len(data):
            btype = struct.unpack(self.endian + "I", data[pos:pos + 4])[0]
            blen = struct.unpack(self.endian + "I", data[pos + 4:pos + 8])[0]
            if blen < 12 or blen % 4 or pos + blen > len(data):
                break
            if btype in (0x00000006, 0x00000003, 0x00000002):
                break
            prefix_end = pos + blen
            pos += blen
        self.prefix = data[:prefix_end]
        self.offset = os.path.getsize(self.path)

    def lire_nouveaux(self):
        if self.fmt is None:
            return None
        taille = os.path.getsize(self.path)
        if taille <= self.offset:
            return b""
        with open(self.path, "rb") as f:
            f.seek(self.offset)
            data = f.read(taille - self.offset)
        pos = 0
        complete = 0
        if self.fmt == "pcap":
            while pos + 16 <= len(data):
                incl = struct.unpack(self.endian + "I", data[pos + 8:pos + 12])[0]
                rec = 16 + incl
                if pos + rec > len(data):
                    break
                pos += rec
                complete = pos
        else:
            while pos + 8 <= len(data):
                blen = struct.unpack(self.endian + "I", data[pos + 4:pos + 8])[0]
                if blen < 12 or blen % 4 or pos + blen > len(data):
                    break
                pos += blen
                complete = pos
        if complete == 0:
            return b""
        self.offset += complete
        return self.prefix + data[:complete]


def lire_via_tshark(pcap_path):
    cmd = ["tshark", "-r", pcap_path, "-T", "fields",
           "-E", "separator=|", "-E", "occurrence=f"]
    for c in CHAMPS:
        cmd += ["-e", c]
    resultat = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                               encoding=cfg.ENCODAGE, errors="replace")
    if resultat.returncode != 0:
        log.warning("tshark a renvoye une erreur : %s", resultat.stderr.strip())
    lignes = [l for l in resultat.stdout.splitlines() if l.strip()]
    if not lignes:
        return pd.DataFrame(columns=CHAMPS)
    data = [l.split("|") for l in lignes]
    data = [r + [""] * (len(CHAMPS) - len(r)) for r in data]
    return pd.DataFrame(data, columns=CHAMPS)


def capturer_derniere_fenetre(capture, pcap_path, duree):
    if capture is not None and capture.fmt is not None:
        brut = capture.lire_nouveaux()
        if not brut:
            return pd.DataFrame(columns=CHAMPS)
        with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp:
            tmp.write(brut)
            chemin_tmp = tmp.name
        try:
            df = lire_via_tshark(chemin_tmp)
        finally:
            os.unlink(chemin_tmp)
    else:
        df = lire_via_tshark(pcap_path)

    if df.empty:
        return df
    t = pd.to_numeric(df["frame.time_relative"], errors="coerce")
    if t.notna().any():
        df = df[t >= (t.max() - duree)]
    return df


def construire_features(df):
    n = len(df)
    if n == 0:
        return pd.DataFrame([[0] * len(FEATURES)], columns=FEATURES)

    fl = pd.to_numeric(df["frame.len"], errors="coerce")
    proto = df["_ws.col.Protocol"].astype(str)
    win = pd.to_numeric(df["tcp.window_size"], errors="coerce")
    syn = df["tcp.flags.syn"].isin(["1", "True"])
    ack = df["tcp.flags.ack"].isin(["1", "True"])
    rst = df["tcp.flags.reset"].isin(["1", "True"])

    port_tcp = df["tcp.dstport"].replace("", np.nan)
    port_udp = df["udp.dstport"].replace("", np.nan)
    port_dst = port_tcp.fillna(port_udp)

    def prop(masque):
        return float(masque.sum()) / n

    f = {
        "frame_len_mean": fl.mean(),
        "frame_len_std": fl.std(ddof=1) if n > 1 else 0,
        "nb_mac_src_distinct": df["eth.src"].replace("", np.nan).nunique(),
        "pct_arp": prop(proto.eq("ARP")),
        "pct_stp": prop(proto.eq("STP")),
        "arp_conflict_present": int((df["arp.duplicate-address-detected"] != "").any()),
        "pct_tcp": prop(proto.eq("TCP")),
        "pct_icmp": prop(proto.eq("ICMP")),
        "pct_icmp_unreachable": prop(df["icmp.type"] == "3"),
        "pct_icmp_no_response": 0.0,
        "nb_ip_dst_distinct": df["ip.dst"].replace("", np.nan).nunique(),
        "nb_paquets": n,
        "tcp_win_mean": win.mean() if win.notna().any() else 0,
        "pct_retransmission": prop(df["tcp.analysis.retransmission"] != ""),
        "pct_zerowindow": prop(df["tcp.analysis.zero_window"] != ""),
        "pct_out_of_order": prop(df["tcp.analysis.out_of_order"] != ""),
        "pct_rst": prop(rst),
        "pct_syn": prop(syn & ~ack),
        "pct_syn_ack": prop(syn & ack),
        "nb_ports_dst_distinct": port_dst.nunique(),
        "pct_dns": prop(proto.eq("DNS")),
        "pct_dns_sans_reponse": 0.0,
        "pct_http": prop(proto.eq("HTTP")),
    }
    return pd.DataFrame([f], columns=FEATURES).fillna(0)


def calculer_latence_icmp_ms(df):
    if "icmp.seq" not in df.columns or df.empty:
        return None
    t = pd.to_numeric(df["frame.time_relative"], errors="coerce")
    seq = df["icmp.seq"].replace("", np.nan)
    type_icmp = df["icmp.type"].replace("", np.nan)

    requetes = df[(type_icmp == "8")].assign(t=t, seq=seq)
    reponses = df[(type_icmp == "0")].assign(t=t, seq=seq)
    if requetes.empty or reponses.empty:
        return None

    latences = []
    for s in requetes["seq"].dropna().unique():
        t_req = requetes.loc[requetes["seq"] == s, "t"]
        t_rep = reponses.loc[reponses["seq"] == s, "t"]
        if not t_req.empty and not t_rep.empty:
            latences.append(abs(float(t_rep.iloc[0]) - float(t_req.iloc[0])) * 1000)
    return round(float(np.mean(latences)), 1) if latences else None


def decrire_anomalie(features_row, regime, latence_ms=None):
    x = features_row.iloc[0] if isinstance(features_row, pd.DataFrame) else features_row
    suffixe_latence = f" (latence ICMP mesuree : {latence_ms} ms)" if latence_ms else ""

    if regime == "Normal":
        if x["nb_paquets"] < 5:
            return "Trafic normal de tres faible volume (reseau calme)."
        if x["pct_tcp"] > 0.5 and x["pct_dns"] > 0.1:
            return f"Trafic normal mixte TCP/DNS ({int(x['nb_paquets'])} paquets)."
        if x["pct_tcp"] > 0.5:
            return f"Trafic normal, activite TCP soutenue ({int(x['nb_paquets'])} paquets)."
        if x["pct_icmp"] > 0.5:
            return f"Trafic normal, majoritairement ICMP ({int(x['nb_paquets'])} paquets)."
        if x["pct_dns"] > 0.2:
            return "Trafic normal avec resolutions DNS actives."
        if x["pct_http"] > 0.1:
            return "Trafic normal avec activite HTTP."
        if x["nb_ip_dst_distinct"] > 5:
            return f"Trafic normal reparti sur {int(x['nb_ip_dst_distinct'])} destinations distinctes."
        return f"Trafic conforme au profil normal ({int(x['nb_paquets'])} paquets)."

    if regime == "Perte de performance":
        if x["pct_retransmission"] > 0.15 and x["pct_zerowindow"] > 0.05:
            return "Congestion severe : retransmissions ET zero-window combines." + suffixe_latence
        if latence_ms is not None and latence_ms > 150:
            return f"Latence elevee detectee : {latence_ms} ms en moyenne sur la fenetre."
        if x["pct_retransmission"] > 0.15:
            return "Congestion probable : taux de retransmission eleve." + suffixe_latence
        if x["pct_retransmission"] > 0.05 and x["pct_out_of_order"] > 0.05:
            return "Congestion probable : retransmissions et paquets hors-sequence detectes." + suffixe_latence
        if x["tcp_win_mean"] < 2000 and x["tcp_win_mean"] > 0:
            return "Saturation probable du buffer recepteur (fenetre TCP reduite)." + suffixe_latence
        if x["pct_zerowindow"] > 0.05:
            return "Zero-window detecte : recepteur sature." + suffixe_latence
        if x["pct_out_of_order"] > 0.1:
            return "Paquets hors-sequence frequents : chemin reseau instable." + suffixe_latence
        if x["nb_paquets"] > 0 and x["pct_syn"] > 0.15 and x["pct_syn_ack"] < 0.05:
            return "Connexions TCP lentes a s'etablir (SYN sans reponse rapide)." + suffixe_latence
        if x["frame_len_std"] > 400:
            return "Forte variabilite de la taille des paquets : gigue (jitter) possible." + suffixe_latence
        if x["nb_ip_dst_distinct"] > 8 and x["nb_paquets"] > 30:
            return "Dispersion elevee des destinations : possible surcharge du lien partage." + suffixe_latence
        if x["frame_len_mean"] > 800:
            return "Paquets volumineux dominants : transfert lourd, ralentissement possible." + suffixe_latence
        return "Degradation des performances reseau, signature mixte non isolee." + suffixe_latence

    if regime == "Erreur de configuration":
        if x["pct_dns_sans_reponse"] > 0.1:
            return "Resolution DNS probablement defaillante."
        if x["arp_conflict_present"] >= 1:
            return "Conflit d'adresse IP detecte (ARP)."
        if x["pct_icmp_unreachable"] > 0.1:
            return "Destination injoignable : route ou passerelle probablement erronee."
        if x["pct_syn"] > 0.15 and x["pct_syn_ack"] < 0.02 and x["pct_rst"] < 0.05:
            return ("Aucune reponse aux tentatives de connexion : service arrete ou "
                     "filtrage silencieux (pare-feu sans rejet explicite).")
        if x["pct_rst"] > 0.2:
            return "Connexions rejetees frequentes (RST) : service ou pare-feu mal configure."
        if x["nb_mac_src_distinct"] > 3 and x["nb_paquets"] < 30:
            return ("Multiples adresses MAC sources sur peu de trafic : possible boucle "
                     "reseau ou erreur de segmentation VLAN.")
        if x["pct_arp"] > 0.3:
            return "Activite ARP anormalement elevee (scan ou boucle reseau possible)."
        if x["nb_ports_dst_distinct"] > 10 and x["nb_paquets"] < 50:
            return "Balayage de ports probable (nombreux ports distincts, peu de donnees)."
        if x["frame_len_std"] < 1 and x["nb_paquets"] > 20:
            return "Paquets de taille strictement identique et repetitifs : possible scan automatise."
        if x["pct_icmp"] < 0.05 and x["pct_tcp"] > 0.5 and x["pct_syn_ack"] > 0.15:
            return ("Trafic majoritairement applicatif (TCP) avec quasi-absence d'ICMP : "
                     "ICMP probablement filtre par une politique de securite "
                     "(faux positif possible, a valider manuellement).")
        if x["pct_stp"] > 0.5 and x["nb_paquets"] > 5:
            return "Reconvergence STP probable : changement de topologie reseau detecte."
        if x["nb_paquets"] <= 2:
            return ("Quasi-absence de trafic : interface probablement desactivee "
                     "(shutdown) ou cable deconnecte (a confirmer sur plusieurs fenetres).")
        return "Anomalie de configuration reseau de type non identifie par les regles actuelles."

    return "Regime non reconnu."


def envoyer_zabbix(valeur, cle=ZABBIX_CLE):
    cmd = ["zabbix_sender", "-z", ZABBIX_SERVER, "-s", ZABBIX_HOST,
           "-k", cle, "-o", str(valeur)]
    try:
        resultat = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                   encoding="utf-8", errors="replace")
        if resultat.returncode == 0 and "failed: 0" in resultat.stdout:
            log.info("Zabbix <- %s=%s OK", cle, valeur)
            return True
        log.error("zabbix_sender a echoue (%s) : %s / %s",
                   cle, resultat.stdout.strip(), resultat.stderr.strip())
        return False
    except Exception as e:
        log.error("Impossible d'appeler zabbix_sender (%s) : %s", cle, e)
        return False


def un_cycle(capture, pcap_path, scaler, km, mapping, fenetres_vides_consecutives):
    df = capturer_derniere_fenetre(capture, pcap_path, FENETRE_SEC)

    if df.empty:
        fenetres_vides_consecutives += 1
        if fenetres_vides_consecutives <= MAX_FENETRES_VIDES_CONSECUTIVES:
            log.info("Aucun paquet capture (vide #%d/%d) -> envoi Normal (0)",
                      fenetres_vides_consecutives, MAX_FENETRES_VIDES_CONSECUTIVES)
            envoyer_zabbix(0)
            envoyer_zabbix("Normal : aucun trafic capture (reseau calme).", cle="kmeans.detail")
        else:
            log.warning(
                "Aucun paquet depuis %d fenetres consecutives (~%ds) -> "
                "capture probablement en panne. Verifier GNS3 / le fichier %s",
                fenetres_vides_consecutives,
                fenetres_vides_consecutives * FENETRE_SEC, pcap_path)
        return fenetres_vides_consecutives

    fenetres_vides_consecutives = 0

    X = construire_features(df)
    log.debug("Features brutes: %s", X.iloc[0].round(3).to_dict())
    X_scaled = pd.DataFrame(scaler.transform(X), columns=FEATURES)

    cluster = int(km.predict(X_scaled)[0])
    info = mapping[str(cluster)]
    regime = info["regime"]
    code = info["code"]

    latence_ms = calculer_latence_icmp_ms(df)
    description = decrire_anomalie(X, regime, latence_ms=latence_ms)

    log.info("Fenetre: %d paquets -> cluster %d -> regime '%s' (code %d) | %s",
              len(df), cluster, regime, code, description)

    envoyer_zabbix(code)
    envoyer_zabbix(f"{regime} : {description}", cle="kmeans.detail")

    return fenetres_vides_consecutives


def main():
    parser = argparse.ArgumentParser(description="Detection K-Means en direct -> Zabbix")
    parser.add_argument("--pcap", default=PCAP_PAR_DEFAUT,
                         help="Chemin du fichier .pcap alimente par GNS3")
    parser.add_argument("--once", action="store_true",
                         help="Execute un seul cycle puis quitte")
    parser.add_argument("--debug", action="store_true",
                         help="Affiche le detail des 23 features")
    args = parser.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)

    log.info("=== Demarrage detect_anomalie.py ===")
    log.info("Capture: %s | Fenetre: %ds | Zabbix: %s/%s/%s",
              args.pcap, FENETRE_SEC, ZABBIX_SERVER, ZABBIX_HOST, ZABBIX_CLE)

    if not Path(args.pcap).is_file():
        log.error("Fichier de capture introuvable : %s", args.pcap)
        sys.exit(1)

    scaler = joblib.load(cfg.OUT / "05_scaler.pkl")
    km = joblib.load(cfg.OUT / "07_kmeans_model.pkl")
    mapping = json.load(open(cfg.OUT / "cluster_mapping.json"))
    log.info("Modele, scaler et mapping charges depuis %s", cfg.OUT)

    try:
        capture = CaptureIncrementale(args.pcap)
    except Exception as e:
        log.warning("Lecture incrementale indisponible (%s) -> repli fichier entier.", e)
        capture = None

    fenetres_vides = 0
    try:
        while True:
            debut = time.time()
            fenetres_vides = un_cycle(capture, args.pcap, scaler, km, mapping, fenetres_vides)
            if args.once:
                break
            attente = FENETRE_SEC - (time.time() - debut)
            if attente > 0:
                time.sleep(attente)
    except KeyboardInterrupt:
        log.info("Arret demande (Ctrl+C). Fin du script.")


if __name__ == "__main__":
    main()