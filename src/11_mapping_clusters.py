"""
=========================================================
 ÉTAPE 11 — CORRESPONDANCE CLUSTER -> RÉGIME
=========================================================
Détermine quel cluster correspond à quel régime de trafic
(par vote majoritaire) et sauvegarde la table de correspondance.
Indispensable pour l'intégration Zabbix : sans elle, Zabbix ne
sait pas qu'un cluster donné = "erreur de configuration".

ENTRÉES : outputs/03_dataset_agrege.csv + 05_scaler.pkl + 07_kmeans_model.pkl
SORTIE  : outputs/cluster_mapping.json

Lancer :  python src/11_mapping_clusters.py
"""
import sys, json
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import pandas as pd
import joblib
import config as cfg


def main():
    agg = pd.read_csv(cfg.OUT / "03_dataset_agrege.csv")
    scaler = joblib.load(cfg.OUT / "05_scaler.pkl")
    km = joblib.load(cfg.OUT / "07_kmeans_model.pkl")

    Xs = scaler.transform(agg[cfg.FEATURES])
    clusters = km.predict(Xs)

    code = {"Normal": 0, "Perte de performance": 1, "Erreur de configuration": 2}
    vraie = agg["fichier_source"].map(cfg.CAPTURES)

    mapping = {}
    for cl in sorted(set(clusters)):
        regime = vraie[clusters == cl].value_counts().idxmax()
        mapping[int(cl)] = {"regime": regime, "code": code[regime]}
        print(f"Cluster {cl} -> {regime} (code Zabbix {code[regime]})")

    json.dump(mapping, open(cfg.OUT / "cluster_mapping.json", "w"),
              ensure_ascii=False, indent=2)
    print("-> outputs/cluster_mapping.json")


if __name__ == "__main__":
    main()
