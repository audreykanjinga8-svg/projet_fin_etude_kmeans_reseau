import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd
import joblib
from sklearn.cluster import KMeans
import config as cfg


def main():
    X = pd.read_csv(cfg.OUT / "05_X_scaled.csv")
    cles = pd.read_csv(cfg.OUT / "03_dataset_agrege.csv")[["fichier_source", "fenetre_id"]]

    km = KMeans(n_clusters=cfg.K, random_state=cfg.RANDOM_STATE, n_init=10)
    clusters = km.fit_predict(X)
    distances = km.transform(X)
    assigned_distances = distances[np.arange(len(clusters)), clusters]

    seuils = {}
    for cl in sorted(set(clusters)):
        cluster_distances = assigned_distances[clusters == cl]
        seuils[int(cl)] = float(np.quantile(cluster_distances, 0.95)) if len(cluster_distances) else float("inf")

    with open(cfg.OUT / "07_centroid_thresholds.json", "w") as fh:
        json.dump(seuils, fh, indent=2)

    joblib.dump(km, cfg.OUT / "07_kmeans_model.pkl")
    res = cles.copy()
    res["cluster"] = clusters
    res.to_csv(cfg.OUT / "07_resultats_clustering.csv", index=False)

    print(f"K-Means entraîné (K={cfg.K})")
    print(f"  Inertie : {km.inertia_:.0f}")
    print(f"  Tailles : {res['cluster'].value_counts().sort_index().to_dict()}")
    print(f"  Seuils centroïdes : {seuils}")
    print("-> outputs/07_kmeans_model.pkl + 07_resultats_clustering.csv + 07_centroid_thresholds.json")


if __name__ == "__main__":
    main()
