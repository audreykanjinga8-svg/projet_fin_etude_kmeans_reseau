import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
import config as cfg
from detect_anomalie import analyser_centroides, decrire_anomalie, determiner_regime


def test_analyser_centroides_mentions_centroid_deviation():
    scaled_row = pd.Series([0.0] * len(cfg.FEATURES), index=cfg.FEATURES)
    centroid = pd.Series([0.0] * len(cfg.FEATURES), index=cfg.FEATURES)

    scaled_row.loc["pct_retransmission"] = 1.5
    centroid.loc["pct_retransmission"] = 0.0

    description = analyser_centroides(scaled_row, centroid, "Perte de performance")

    assert "Analyse centroïde" in description
    assert "retransmission" in description.lower() or "écart" in description.lower()


def test_decrire_anomalie_includes_centroid_analysis():
    features_row = pd.DataFrame([{"nb_paquets": 40, "pct_tcp": 0.8, "pct_dns": 0.1}], columns=["nb_paquets", "pct_tcp", "pct_dns"])
    description = decrire_anomalie(
        features_row,
        "Normal",
        centroid_analysis="Analyse centroïde : écart dominant sur la varianza des paquets.",
    )

    assert "Analyse centroïde" in description


def test_decrire_anomalie_identifies_congestion_pattern():
    features_row = pd.DataFrame([
        {
            "nb_paquets": 36,
            "pct_tcp": 0.8,
            "pct_retransmission": 0.08,
            "pct_out_of_order": 0.08,
            "pct_zerowindow": 0.0,
            "pct_syn": 0.10,
            "pct_syn_ack": 0.05,
            "pct_dns": 0.0,
            "pct_icmp": 0.0,
            "pct_http": 0.0,
            "pct_dns_sans_reponse": 0.0,
            "pct_icmp_unreachable": 0.0,
            "pct_arp": 0.0,
            "pct_stp": 0.0,
            "pct_rst": 0.0,
            "arp_conflict_present": 0,
            "frame_len_std": 500,
            "frame_len_mean": 900,
            "nb_ip_dst_distinct": 6,
            "nb_mac_src_distinct": 2,
            "nb_ports_dst_distinct": 4,
            "tcp_win_mean": 1800,
        }
    ])

    description = decrire_anomalie(features_row, "Perte de performance")

    assert "congestion" in description.lower() or "dégradation" in description.lower()


def test_decrire_anomalie_identifies_route_issue_pattern():
    features_row = pd.DataFrame([
        {
            "nb_paquets": 12,
            "pct_tcp": 0.7,
            "pct_syn": 0.22,
            "pct_syn_ack": 0.01,
            "pct_rst": 0.0,
            "pct_dns": 0.0,
            "pct_icmp": 0.0,
            "pct_http": 0.0,
            "pct_dns_sans_reponse": 0.0,
            "pct_icmp_unreachable": 0.05,
            "pct_arp": 0.0,
            "pct_stp": 0.0,
            "pct_retransmission": 0.0,
            "pct_out_of_order": 0.0,
            "pct_zerowindow": 0.0,
            "arp_conflict_present": 0,
            "frame_len_std": 80,
            "frame_len_mean": 100,
            "nb_ip_dst_distinct": 1,
            "nb_mac_src_distinct": 1,
            "nb_ports_dst_distinct": 2,
            "tcp_win_mean": 1500,
        }
    ])

    description = decrire_anomalie(features_row, "Erreur de configuration")

    assert "route" in description.lower() or "service" in description.lower() or "injoignable" in description.lower()


def test_determiner_regime_prefere_la_signature_performance_sur_le_cluster():
    features_row = pd.DataFrame([
        {
            "nb_paquets": 36,
            "pct_tcp": 0.8,
            "pct_retransmission": 0.08,
            "pct_out_of_order": 0.08,
            "pct_zerowindow": 0.0,
            "pct_syn": 0.10,
            "pct_syn_ack": 0.05,
            "pct_dns": 0.0,
            "pct_icmp": 0.0,
            "pct_http": 0.0,
            "pct_dns_sans_reponse": 0.0,
            "pct_icmp_unreachable": 0.0,
            "pct_arp": 0.0,
            "pct_stp": 0.0,
            "pct_rst": 0.0,
            "arp_conflict_present": 0,
            "frame_len_std": 500,
            "frame_len_mean": 900,
            "nb_ip_dst_distinct": 6,
            "nb_mac_src_distinct": 2,
            "nb_ports_dst_distinct": 4,
            "tcp_win_mean": 1800,
        }
    ])

    regime_final = determiner_regime(features_row, "Erreur de configuration")

    assert regime_final == "Perte de performance"
