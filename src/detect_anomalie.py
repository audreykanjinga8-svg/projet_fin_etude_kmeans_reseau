import sys
import os
import json
import time
import subprocess
import argparse
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import joblib

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config as cfg

# ---------------------------------------------------------
# Configuration
PCAP_PAR_DEFAUT = (
    "/home/audrey/GNS3/projects/Projet_Final_topo/project-files/captures/"
    "AlpiNet-6_eth0_to_SwitchDatacenter_Ethernet02.pcap"
)
ZABBIX_SERVER = "127.0.0.1"
ZABBIX_HOST = "Detection-KMeans"
ZABBIX_CLE = "kmeans.regime"
MAX_FENETRES_VIDES_CONSECUTIVES = 5   # ~25s sans paquet  on arrête d'envoyer "Normal" par défaut
CENTROID_THRESHOLDS_FILE = cfg.OUT / "07_centroid_thresholds.json"

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


# ---------------------------------------------------------
# Capture & features (mêmes définitions que 02_/03_, mais
# calculées directement par champs tshark plutôt que par
# regex sur la colonne Info)
# ---------------------------------------------------------
def capturer_derniere_fenetre(pcap_path, duree):
    """Relit le fichier .pcap (alimenté en continu par GNS3) et ne garde
    que les paquets des <duree> dernières secondes."""
    cmd = ["tshark", "-r", pcap_path, "-T", "fields",
           "-E", "separator=|", "-E", "occurrence=f"]
    for c in CHAMPS:
        cmd += ["-e", c]

    resultat = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                               encoding=cfg.ENCODAGE, errors="replace")
    if resultat.returncode != 0:
        log.warning("tshark a renvoyé une erreur : %s", resultat.stderr.strip())

    lignes = [l for l in resultat.stdout.splitlines() if l.strip()]
    if not lignes:
        return pd.DataFrame(columns=CHAMPS)

    data = [l.split("|") for l in lignes]
    data = [r + [""] * (len(CHAMPS) - len(r)) for r in data]
    df = pd.DataFrame(data, columns=CHAMPS)

    t = pd.to_numeric(df["frame.time_relative"], errors="coerce")
    if t.notna().any():
        df = df[t >= (t.max() - duree)]
    return df


def construire_features(df):
    """Calcule les 23 features à partir des paquets de la fenêtre."""
    n = len(df)
    if n == 0:
        return pd.DataFrame([[0] * len(FEATURES)], columns=FEATURES)

    fl = pd.to_numeric(df["frame.len"], errors="coerce")
    proto = df["_ws.col.Protocol"].astype(str)
    win = pd.to_numeric(df["tcp.window_size"], errors="coerce")
    syn = df["tcp.flags.syn"].isin(["1", "True"])
    ack = df["tcp.flags.ack"].isin(["1", "True"])
    rst = df["tcp.flags.reset"].isin(["1", "True"])

    # Port destination : TCP ou UDP (DNS passe en UDP, sinon on le perd)
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
        # Non calculable de façon fiable sur une fenêtre isolée de 5s
        # (la réponse peut arriver après la fenêtre) -> figé à 0.
        # Limite connue, documentée dans le mémoire.
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
        # Même limite que pct_icmp_no_response : non calculable sur une
        # fenêtre isolée -> figé à 0.
        "pct_dns_sans_reponse": 0.0,
        "pct_http": prop(proto.eq("HTTP")),
    }
    return pd.DataFrame([f], columns=FEATURES).fillna(0)


def calculer_latence_icmp_ms(df):
    """Calcule la latence ICMP réelle (ms) en appariant les paquets
    'echo request' (type 8) et 'echo reply' (type 0) par numéro de
    séquence, sur la fenêtre capturée. Retourne None si aucune paire
    complète n'est trouvée.

    NOTE : ce calcul est PUREMENT DESCRIPTIF, pour enrichir le message
    envoyé à l'opérateur/Zabbix. Il n'entre PAS dans les 23 features
    utilisées par le modèle K-Means (qui reste inchangé).
    """
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


def determiner_regime(features_row, regime_cluster, latence_ms=None):
    """Détermine le régime le plus probable à partir des features observées,
    en priorisant les signatures explicites de performance ou de configuration
    sur l’étiquette de cluster si celle-ci est peu fiable ou ambiguë."""
    if isinstance(features_row, pd.DataFrame):
        x = features_row.iloc[0]
    else:
        x = features_row

    if not isinstance(x, pd.Series):
        x = pd.Series(x)

    performance_signals = (
        float(x.get("pct_retransmission", 0)) > 0.15
        or float(x.get("pct_zerowindow", 0)) > 0.05
        or float(x.get("pct_out_of_order", 0)) > 0.05
        or (float(x.get("tcp_win_mean", 0)) < 1000 and float(x.get("tcp_win_mean", 0)) > 0
            and (float(x.get("pct_retransmission", 0)) > 0.05 or float(x.get("pct_zerowindow", 0)) > 0.01))
        or (latence_ms is not None and latence_ms > 150)
    )
    if performance_signals:
        return "Perte de performance"

    config_signals = (
        float(x.get("pct_dns_sans_reponse", 0)) > 0.1
        or int(x.get("arp_conflict_present", 0)) >= 1
        or float(x.get("pct_icmp_unreachable", 0)) > 0.02
        or float(x.get("pct_stp", 0)) > 0.5
        or (float(x.get("pct_rst", 0)) > 0.2)
        or (float(x.get("pct_syn", 0)) > 0.15 and float(x.get("pct_syn_ack", 0)) < 0.02 and float(x.get("pct_rst", 0)) < 0.05)
        or (int(x.get("nb_paquets", 0)) <= 2)
    )
    if config_signals:
        return "Erreur de configuration"

    return regime_cluster


def analyser_centroides(scaled_row, centroid, regime):
    """Produit une courte interprétation des écarts dominants du point
    courant par rapport au centroïde du cluster attribué."""
    if not isinstance(scaled_row, pd.Series):
        scaled_row = pd.Series(scaled_row, index=FEATURES)
    if not isinstance(centroid, pd.Series):
        centroid = pd.Series(centroid, index=FEATURES)

    deltas = (scaled_row - centroid).fillna(0)
    top_features = deltas.abs().sort_values(ascending=False).head(4)
    top_desc = ", ".join([f"{feat}={deltas[feat]:+.2f}σ" for feat in top_features.index])

    reasons = []
    if regime == "Perte de performance":
        if deltas.get("pct_retransmission", 0) > 0.8:
            reasons.append("rétransmissions")
        if deltas.get("pct_zerowindow", 0) > 0.8:
            reasons.append("zero-window")
        if deltas.get("tcp_win_mean", 0) < -0.8:
            reasons.append("fenêtre TCP réduite")
        if deltas.get("frame_len_std", 0) > 0.8:
            reasons.append("gigue")
    elif regime == "Erreur de configuration":
        if deltas.get("pct_dns_sans_reponse", 0) > 0.8:
            reasons.append("DNS sans réponse")
        if deltas.get("pct_icmp_unreachable", 0) > 0.8:
            reasons.append("erreurs ICMP")
        if deltas.get("arp_conflict_present", 0) > 0.8:
            reasons.append("conflit ARP")
    elif regime == "Normal":
        if deltas.get("nb_paquets", 0) < -0.8:
            reasons.append("faible volume")
        if deltas.get("pct_dns", 0) > 0.8:
            reasons.append("activité DNS")

    if reasons:
        return f"Analyse centroïde : écart dominant sur {', '.join(reasons)} ({top_desc})."
    return f"Analyse centroïde : principaux écarts par rapport au centroïde ({top_desc})."


def decrire_anomalie(features_row, regime, latence_ms=None, centroid_analysis=None):
    """Décrit la signature probable de l'anomalie (ou du trafic normal)
    à partir des features de la fenêtre. NE remplace PAS le modèle
    (K-Means ne distingue que 3 régimes globaux) : c'est une couche de
    règles, lisible par un opérateur, posée SUR le résultat du
    clustering. Documenté comme tel dans le mémoire.

    Les règles sont ordonnées de la plus spécifique/sévère à la plus
    générique : la première condition vraie l'emporte. Le cas générique
    en fin de liste ne devrait être atteint que pour des signatures
    réellement ambiguës.
    """
    regime_final = determiner_regime(features_row, regime, latence_ms=latence_ms)
    x = features_row.iloc[0] if isinstance(features_row, pd.DataFrame) else features_row
    suffixe_latence = f" (latence ICMP mesurée : {latence_ms} ms)" if latence_ms else ""

    # ---------------------------------------------------------------
    if regime_final == "Normal":
        if x["nb_paquets"] < 5:
            description = "Trafic normal de très faible volume (réseau calme)."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_tcp"] > 0.5 and x["pct_dns"] > 0.1:
            description = f"Trafic normal mixte TCP/DNS ({int(x['nb_paquets'])} paquets)."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_tcp"] > 0.5:
            description = f"Trafic normal, activité TCP soutenue ({int(x['nb_paquets'])} paquets)."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_icmp"] > 0.5:
            description = f"Trafic normal, majoritairement ICMP ({int(x['nb_paquets'])} paquets)."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_dns"] > 0.2:
            description = "Trafic normal avec résolutions DNS actives."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_http"] > 0.1:
            description = "Trafic normal avec activité HTTP."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["nb_ip_dst_distinct"] > 5:
            description = f"Trafic normal réparti sur {int(x['nb_ip_dst_distinct'])} destinations distinctes."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        description = f"Trafic conforme au profil normal ({int(x['nb_paquets'])} paquets)."
        return f"{description} {centroid_analysis}" if centroid_analysis else description

    # ---------------------------------------------------------------
    if regime_final == "Perte de performance":
        # Cas combinés (plus sévères) d'abord
        if x["pct_retransmission"] > 0.15 and x["pct_zerowindow"] > 0.05:
            description = "Congestion sévère : retransmissions ET zero-window combinés." + suffixe_latence
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if latence_ms is not None and latence_ms > 150:
            description = f"Latence élevée détectée : {latence_ms} ms en moyenne sur la fenêtre."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_retransmission"] > 0.15:
            description = "Congestion probable : taux de retransmission élevé." + suffixe_latence
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_retransmission"] > 0.05 and x["pct_out_of_order"] > 0.05:
            description = "Congestion probable : retransmissions et paquets hors-séquence détectés." + suffixe_latence
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["tcp_win_mean"] < 2000 and x["tcp_win_mean"] > 0:
            description = "Saturation probable du buffer récepteur (fenêtre TCP réduite)." + suffixe_latence
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_zerowindow"] > 0.05:
            description = "Zero-window détecté : récepteur saturé." + suffixe_latence
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_out_of_order"] > 0.1:
            description = "Paquets hors-séquence fréquents : chemin réseau instable." + suffixe_latence
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["nb_paquets"] > 0 and x["pct_syn"] > 0.15 and x["pct_syn_ack"] < 0.05:
            description = "Connexions TCP lentes à s'établir (SYN sans réponse rapide)." + suffixe_latence
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["frame_len_std"] > 400:
            description = "Forte variabilité de la taille des paquets : gigue (jitter) possible." + suffixe_latence
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["nb_ip_dst_distinct"] > 8 and x["nb_paquets"] > 30:
            description = "Dispersion élevée des destinations : possible surcharge du lien partagé." + suffixe_latence
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["frame_len_mean"] > 800:
            description = "Paquets volumineux dominants : transfert de données lourd, ralentissement possible." + suffixe_latence
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        description = "Dégradation des performances réseau, signature mixte non isolée." + suffixe_latence
        return f"{description} {centroid_analysis}" if centroid_analysis else description

    # ---------------------------------------------------------------
    if regime_final == "Erreur de configuration":
        if x["pct_dns_sans_reponse"] > 0.1:
            description = "Résolution DNS probablement défaillante."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["arp_conflict_present"] >= 1:
            description = "Conflit d'adresse IP détecté (ARP)."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_icmp_unreachable"] > 0.02:
            description = "Destination injoignable : route ou passerelle probablement erronée."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["nb_ip_dst_distinct"] <= 1 and x["pct_tcp"] > 0.5 and x["pct_syn"] > 0.15 and x["pct_syn_ack"] < 0.05:
            description = "Service ou route inaccessible : peu de destinations et peu de réponses TCP."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_syn"] > 0.15 and x["pct_syn_ack"] < 0.02 and x["pct_rst"] < 0.05:
            description = ("Aucune réponse aux tentatives de connexion : service arrêté ou "
                           "filtrage silencieux (pare-feu sans rejet explicite).")
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_rst"] > 0.2:
            description = "Connexions rejetées fréquentes (RST) : service ou pare-feu mal configuré."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["nb_mac_src_distinct"] > 3 and x["nb_paquets"] < 30:
            description = ("Multiples adresses MAC sources sur peu de trafic : possible boucle "
                           "réseau ou erreur de segmentation VLAN.")
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_arp"] > 0.3:
            description = "Activité ARP anormalement élevée (scan ou boucle réseau possible)."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["nb_ports_dst_distinct"] > 10 and x["nb_paquets"] < 50:
            description = "Balayage de ports probable (nombreux ports distincts, peu de données)."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["frame_len_std"] < 1 and x["nb_paquets"] > 20:
            description = "Paquets de taille strictement identique et répétitifs : possible scan automatisé."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["pct_stp"] > 0.5 and x["nb_paquets"] > 5:
            description = "Reconvergence STP probable : changement de topologie réseau détecté."
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        if x["nb_paquets"] <= 2:
            description = ("Quasi-absence de trafic : interface probablement désactivée "
                           "(shutdown) ou câble déconnecté (à confirmer sur plusieurs fenêtres).")
            return f"{description} {centroid_analysis}" if centroid_analysis else description
        description = "Anomalie de configuration réseau de type non identifié par les règles actuelles."
        return f"{description} {centroid_analysis}" if centroid_analysis else description

    description = "Régime non reconnu."
    return f"{description} {centroid_analysis}" if centroid_analysis else description



# ---------------------------------------------------------
# Zabbix
# ---------------------------------------------------------
def envoyer_zabbix(valeur, cle=ZABBIX_CLE):
    cmd = ["zabbix_sender", "-z", ZABBIX_SERVER, "-s", ZABBIX_HOST,
           "-k", cle, "-o", str(valeur)]
    try:
        resultat = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                   encoding="utf-8", errors="replace")
        if resultat.returncode == 0 and "failed: 0" in resultat.stdout:
            log.info("Zabbix <- %s=%s OK (%s)", cle, valeur, resultat.stdout.strip())
            return True
        log.error("zabbix_sender a échoué (%s) : %s / %s",
                   cle, resultat.stdout.strip(), resultat.stderr.strip())
        return False
    except Exception as e:
        log.error("Impossible d'appeler zabbix_sender (%s) : %s", cle, e)
        return False


# ---------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------
def un_cycle(pcap_path, scaler, km, mapping, fenetres_vides_consecutives, centroid_thresholds=None):
    df = capturer_derniere_fenetre(pcap_path, FENETRE_SEC)

    if df.empty:
        fenetres_vides_consecutives += 1
        if fenetres_vides_consecutives <= MAX_FENETRES_VIDES_CONSECUTIVES:
            log.info("Aucun paquet capturé (vide #%d/%d) -> envoi Normal (0) par défaut",
                      fenetres_vides_consecutives, MAX_FENETRES_VIDES_CONSECUTIVES)
            envoyer_zabbix(0)
            envoyer_zabbix("Aucun trafic capturé (réseau calme).", cle="kmeans.detail")
        else:
            log.warning(
                "Aucun paquet depuis %d fenêtres consécutives (~%ds) -> "
                "capture probablement en panne, on N'ENVOIE PLUS de valeur "
                "par défaut. Vérifier GNS3 / le fichier %s",
                fenetres_vides_consecutives,
                fenetres_vides_consecutives * FENETRE_SEC, pcap_path)
        return fenetres_vides_consecutives

    # Au moins un paquet -> on réinitialise le compteur de silence
    fenetres_vides_consecutives = 0

    X = construire_features(df)
    log.debug("Features brutes: %s", X.iloc[0].round(3).to_dict())
    X_scaled = pd.DataFrame(scaler.transform(X), columns=FEATURES)
    distances = km.transform(X_scaled)
    cluster = int(km.predict(X_scaled)[0])
    info = mapping[str(cluster)]
    distance_to_centroid = float(distances[0, cluster])
    threshold = None
    if centroid_thresholds:
        threshold = centroid_thresholds.get(str(cluster))
    confiance = threshold is None or distance_to_centroid <= threshold
    latence_ms = calculer_latence_icmp_ms(df)
    regime_final = determiner_regime(X, info["regime"], latence_ms=latence_ms)
    centroid_analysis = analyser_centroides(X_scaled.iloc[0], km.cluster_centers_[cluster], regime_final)
    description = decrire_anomalie(X, regime_final, latence_ms=latence_ms,
                                   centroid_analysis=centroid_analysis)

    code = {
        "Normal": 0,
        "Perte de performance": 1,
        "Erreur de configuration": 2,
    }.get(regime_final, info["code"])
    if not confiance and regime_final != "Normal":
        description = (
            f"Prédiction peu fiable (distance au centroïde {distance_to_centroid:.2f} > seuil {threshold:.2f}) ; {description}"
        )

    log.info("Fenêtre: %d paquets -> cluster %d (%s) -> régime '%s' (code %d, confiance=%s, distance=%.2f) | %s",
              len(df), cluster, info["regime"], regime_final, code, "oui" if confiance else "non",
              distance_to_centroid, description)
    envoyer_zabbix(code)
    envoyer_zabbix(description, cle="kmeans.detail")
    return fenetres_vides_consecutives


def main():
    parser = argparse.ArgumentParser(description="Détection K-Means en direct -> Zabbix")
    parser.add_argument("--pcap", default=PCAP_PAR_DEFAUT,
                         help="Chemin du fichier .pcap alimenté par GNS3")
    parser.add_argument("--once", action="store_true",
                         help="Exécute un seul cycle puis quitte (debug)")
    parser.add_argument("--debug", action="store_true",
                         help="Affiche le détail des 23 features de chaque fenêtre")
    args = parser.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)

    log.info("=== Démarrage detect_anomalie.py ===")
    log.info("Capture: %s | Fenêtre: %ds | Zabbix: %s/%s/%s",
              args.pcap, FENETRE_SEC, ZABBIX_SERVER, ZABBIX_HOST, ZABBIX_CLE)

    if not Path(args.pcap).is_file():
        log.error("Fichier de capture introuvable : %s", args.pcap)
        sys.exit(1)

    scaler = joblib.load(cfg.OUT / "05_scaler.pkl")
    km = joblib.load(cfg.OUT / "07_kmeans_model.pkl")
    mapping = json.load(open(cfg.OUT / "cluster_mapping.json"))
    centroid_thresholds = {}
    if CENTROID_THRESHOLDS_FILE.is_file():
        centroid_thresholds = json.load(open(CENTROID_THRESHOLDS_FILE))
    log.info("Modèle, scaler, mapping et seuils centroïdes chargés depuis %s", cfg.OUT)

    fenetres_vides = 0
    try:
        while True:
            debut = time.time()
            fenetres_vides = un_cycle(args.pcap, scaler, km, mapping, fenetres_vides,
                                      centroid_thresholds=centroid_thresholds)
            if args.once:
                break
            # On garde le rythme de FENETRE_SEC entre deux cycles,
            # en tenant compte du temps déjà passé dans le cycle.
            attente = FENETRE_SEC - (time.time() - debut)
            if attente > 0:
                time.sleep(attente)
    except KeyboardInterrupt:
        log.info("Arrêt demandé (Ctrl+C). Fin du script.")


if __name__ == "__main__":
    main()
