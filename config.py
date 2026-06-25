"""
Configuration centrale du projet.
Un seul endroit à modifier pour les chemins et les paramètres.
"""
from pathlib import Path

# --- Dossiers ---
BASE = Path(__file__).resolve().parent   # racine du projet (où est config.py)
DATA = BASE / "data"          # tes 3 captures brutes vont ici
OUT = BASE / "outputs"        # toutes les sorties sortent ici
OUT.mkdir(exist_ok=True)

# --- Paramètres du pipeline ---
FENETRE_SEC = 5          # taille de la fenêtre temporelle (en secondes)
K = 3                    # nombre de clusters K-Means
RANDOM_STATE = 42        # reproductibilité
ENCODAGE = "latin-1"     # encodage des captures Wireshark (PAS utf-8 !)

# --- Tes captures : nom de fichier -> classe réelle ---
# (la classe ne sert QU'À L'ÉVALUATION, jamais à l'entraînement)
CAPTURES = {
    "normal_capture.csv": "Normal",
    "performance_capture.csv": "Perte de performance",
    "erreur_conf.csv": "Erreur de configuration",
}
ORDRE_CLASSES = ["Normal", "Perte de performance", "Erreur de configuration"]

# --- Les 23 features finales (ordre figé) ---
FEATURES = [
    "frame_len_mean", "frame_len_std", "nb_mac_src_distinct",
    "pct_arp", "pct_stp", "arp_conflict_present", "pct_tcp", "pct_icmp",
    "pct_icmp_unreachable", "pct_icmp_no_response", "nb_ip_dst_distinct",
    "nb_paquets", "tcp_win_mean", "pct_retransmission", "pct_zerowindow",
    "pct_out_of_order", "pct_rst", "pct_syn", "pct_syn_ack",
    "nb_ports_dst_distinct", "pct_dns", "pct_dns_sans_reponse", "pct_http",
]
