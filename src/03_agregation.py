"""
=========================================================
 ÉTAPE 3 — AGRÉGATION (fenêtrage + features)
=========================================================
Regroupe les paquets en fenêtres de 5 s et calcule 23
features par couche OSI. C'est le coeur du prétraitement :
on passe de "1 ligne = 1 paquet" à "1 ligne = 1 observation
(l'état du réseau pendant 5 s)".

ENTRÉE  : outputs/02_dataset_enrichi.csv
SORTIE  : outputs/03_dataset_agrege.csv  (clés + 23 features)

Lancer :  python src/03_agregation.py
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import pandas as pd
import config as cfg


def en_bool(serie):
    return serie.astype(str).str.lower().isin(["true", "1", "1.0"])


def main():
    df = pd.read_csv(cfg.OUT / "02_dataset_enrichi.csv", low_memory=False)
    df["Time"] = pd.to_numeric(df["Time"], errors="coerce")
    df = df.dropna(subset=["Time"])

    # Découpage en fenêtres (par capture)
    df["fenetre_id"] = (df["Time"] // cfg.FENETRE_SEC).astype(int)
    cles = [df["fichier_source"], df["fenetre_id"]]
    g = df.groupby(["fichier_source", "fenetre_id"])
    P = df["Protocol"].astype(str)

    def prop(masque):
        return masque.groupby(cles).mean()   # proportion 0-1

    feat = pd.DataFrame({
        # Couche 2 (trame / liaison)
        "frame_len_mean": g["Frame Length"].mean(),
        "frame_len_std": g["Frame Length"].std().fillna(0),
        "nb_mac_src_distinct": g["Source_MAC"].nunique(),
        "pct_arp": prop(P.eq("ARP")),
        "pct_stp": prop(P.eq("STP")),
        "arp_conflict_present": en_bool(df["arp_conflict"]).groupby(cles).max().astype(int),
        # Couche 3 (réseau)
        "pct_tcp": prop(P.eq("TCP")),
        "pct_icmp": prop(P.eq("ICMP")),
        "pct_icmp_unreachable": prop(en_bool(df["icmp_unreachable"])),
        "pct_icmp_no_response": prop(en_bool(df["icmp_no_response"])),
        "nb_ip_dst_distinct": g["Destination"].nunique(),
        "nb_paquets": g.size(),
        # Couche 4 (transport TCP)
        "tcp_win_mean": g["tcp_win"].mean().fillna(0),
        "pct_retransmission": prop(en_bool(df["is_retransmission"])),
        "pct_zerowindow": prop(en_bool(df["is_zerowindow"])),
        "pct_out_of_order": prop(en_bool(df["is_out_of_order"])),
        "pct_rst": prop(en_bool(df["flag_rst"])),
        "pct_syn": prop(en_bool(df["flag_syn"])),
        "pct_syn_ack": prop(en_bool(df["flag_syn_ack"])),
        "nb_ports_dst_distinct": g["port_dst"].nunique(),
        # Couche 7 (application)
        "pct_dns": prop(P.eq("DNS")),
        "pct_dns_sans_reponse": prop(en_bool(df["dns_query_no_response"])),
        "pct_http": prop(P.eq("HTTP")),
    }).reset_index()

    feat = feat[["fichier_source", "fenetre_id"] + cfg.FEATURES]
    feat.to_csv(cfg.OUT / "03_dataset_agrege.csv", index=False)
    print(f"{len(feat)} fenêtres x {len(cfg.FEATURES)} features"
          f" -> outputs/03_dataset_agrege.csv")
    print(feat["fichier_source"].value_counts().to_string())


if __name__ == "__main__":
    main()
