"""
=========================================================
 ÉTAPE 2 — ENRICHISSEMENT
=========================================================
Extrait les indicateurs réseau depuis la colonne `Info`
de Wireshark : drapeaux TCP, retransmissions, fenêtre TCP,
ICMP unreachable, conflits ARP, etc.

ENTRÉE  : outputs/01_dataset_fusionne.csv
SORTIE  : outputs/02_dataset_enrichi.csv

Lancer :  python src/02_enrichissement.py
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import pandas as pd
import config as cfg


def main():
    df = pd.read_csv(cfg.OUT / "01_dataset_fusionne.csv", low_memory=False)
    info = df["Info"].fillna("").astype(str)
    P = df["Protocol"].astype(str)

    # Numériser le temps et la taille de trame
    df["Time"] = pd.to_numeric(df["Time"], errors="coerce")
    df["Frame Length"] = pd.to_numeric(df["Frame Length"], errors="coerce")

    # Port destination : extrait de "40430  >  9000"
    df["port_dst"] = pd.to_numeric(
        info.str.extract(r"\d+\s+>\s+(\d+)")[0], errors="coerce")

    # Drapeaux TCP (lus dans les crochets de Info)
    df["flag_syn"] = info.str.contains(r"\[SYN\]", regex=True)
    df["flag_syn_ack"] = info.str.contains(r"\[SYN, ACK\]", regex=True)
    df["flag_rst"] = info.str.contains("RST")

    # Anomalies TCP
    df["is_retransmission"] = info.str.contains("Retransmission")
    df["is_zerowindow"] = info.str.contains("ZeroWindow")
    df["is_out_of_order"] = info.str.contains("Out-Of-Order")

    # Fenêtre TCP (Win=...) — seulement sur les paquets TCP
    df["tcp_win"] = pd.to_numeric(
        info.str.extract(r"Win=(\d+)")[0], errors="coerce").where(P.eq("TCP"))

    # ICMP
    df["icmp_unreachable"] = P.eq("ICMP") & info.str.contains("unreachable")
    df["icmp_no_response"] = info.str.contains("no response found")

    # ARP : conflit d'adresse
    df["arp_conflict"] = info.str.contains("duplicate use")

    # DNS sans réponse : requête dont l'identifiant n'a pas de réponse
    df["dns_query_no_response"] = _dns_sans_reponse(df, info, P)

    # On ne garde que les colonnes utiles à la suite (allège le fichier)
    colonnes = ["fichier_source", "Time", "Protocol", "Frame Length",
                "Source_MAC", "Destination", "port_dst",
                "flag_syn", "flag_syn_ack", "flag_rst",
                "is_retransmission", "is_zerowindow", "is_out_of_order",
                "tcp_win", "icmp_unreachable", "icmp_no_response",
                "arp_conflict", "dns_query_no_response"]
    df[colonnes].to_csv(cfg.OUT / "02_dataset_enrichi.csv", index=False)
    print(f"{len(df)} paquets enrichis -> outputs/02_dataset_enrichi.csv")


def _dns_sans_reponse(df, info, P):
    """True sur une requête DNS dont l'ID n'a aucune réponse dans la capture."""
    import numpy as np
    est_dns = P.eq("DNS")
    txid = info.str.extract(r"(0x[0-9a-fA-F]+)")[0]
    est_reponse = info.str.contains("response")
    # identifiants (capture, txid) ayant au moins une réponse
    masque_rep = est_dns & est_reponse
    ids_avec_reponse = set(zip(df.loc[masque_rep, "fichier_source"],
                               txid[masque_rep]))
    est_requete = est_dns & ~est_reponse
    a_une_reponse = np.array([(s, t) in ids_avec_reponse
                              for s, t in zip(df["fichier_source"], txid)])
    return est_requete.to_numpy() & ~a_une_reponse


if __name__ == "__main__":
    main()
