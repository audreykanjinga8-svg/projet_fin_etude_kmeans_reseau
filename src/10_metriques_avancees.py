"""
=========================================================
 ÉTAPE 10 — MÉTRIQUES AVANCÉES (demandées par l'encadreur)
=========================================================
Complète l'évaluation avec :
  - indice de silhouette + Davies-Bouldin
  - pureté des clusters
  - comparaison non supervisée étendue : DBSCAN, Isolation Forest
  - importance des variables (Random Forest)
  - temps d'entraînement de K-Means

ENTRÉE  : outputs/03_dataset_agrege.csv
SORTIES : outputs/10_importance_features.png + .csv
          (affiche les autres métriques dans le terminal)

Lancer :  python src/10_metriques_avancees.py
"""
import sys, time
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, DBSCAN
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import (adjusted_rand_score, silhouette_score,
                             davies_bouldin_score, accuracy_score)
import config as cfg


def main():
    agg = pd.read_csv(cfg.OUT / "03_dataset_agrege.csv")
    X = StandardScaler().fit_transform(agg[cfg.FEATURES])
    y = (agg["fichier_source"].map(cfg.CAPTURES)
         .map({c: i for i, c in enumerate(cfg.ORDRE_CLASSES)}).values)

    # --- K-Means : qualité + temps ---
    t0 = time.perf_counter()
    km = KMeans(n_clusters=cfg.K, random_state=cfg.RANDOM_STATE, n_init=10).fit(X)
    dt = (time.perf_counter() - t0) * 1000
    c = km.labels_
    print("=== K-MEANS ===")
    print(f"  Silhouette       : {silhouette_score(X, c):.3f}")
    print(f"  Davies-Bouldin   : {davies_bouldin_score(X, c):.3f}  (plus bas = mieux)")
    print(f"  ARI              : {adjusted_rand_score(y, c):.3f}")
    print(f"  Temps entraînement : {dt:.0f} ms")
    print("  Pureté par cluster :")
    for cl in sorted(set(c)):
        vals = y[c == cl]
        maj = np.bincount(vals).max()
        print(f"    Cluster {cl} ({cfg.ORDRE_CLASSES[np.bincount(vals).argmax()]:24s})"
              f" : {maj}/{len(vals)} = {maj/len(vals):.3f}")
    purete = sum(np.bincount(y[c == cl]).max() for cl in set(c)) / len(y)
    print(f"  Pureté globale   : {purete:.3f}")

    # --- DBSCAN ---
    print("\n=== DBSCAN ===")
    meilleur = None
    for eps in [1.5, 2.0, 2.5, 3.0, 3.5]:
        lab = DBSCAN(eps=eps, min_samples=5).fit(X).labels_
        n_cl = len(set(lab)) - (1 if -1 in lab else 0)
        bruit = int((lab == -1).sum())
        if n_cl >= 2:
            ari = adjusted_rand_score(y, lab)
            print(f"  eps={eps}: {n_cl} clusters, {bruit} bruit, ARI={ari:.3f}")
            if meilleur is None or ari > meilleur[1]:
                meilleur = (eps, ari)

    # --- Isolation Forest (détection normal vs anomalie) ---
    print("\n=== ISOLATION FOREST ===")
    y_bin = (y != 0).astype(int)
    iso = IsolationForest(contamination="auto", random_state=cfg.RANDOM_STATE).fit(X)
    acc = accuracy_score(y_bin, (iso.predict(X) == -1).astype(int))
    print(f"  Accuracy normal/anomalie : {acc:.3f}")
    print(f"  ({(y_bin == 1).mean()*100:.0f}% du trafic est anormal -> méthode peu adaptée,")
    print("   Isolation Forest suppose des anomalies rares)")

    # --- Importance des variables (Random Forest) ---
    print("\n=== IMPORTANCE DES VARIABLES (Random Forest) ===")
    rf = RandomForestClassifier(n_estimators=200, random_state=cfg.RANDOM_STATE)
    rf.fit(agg[cfg.FEATURES], y)
    imp = pd.Series(rf.feature_importances_, index=cfg.FEATURES).sort_values()
    for f, v in imp.tail(8)[::-1].items():
        print(f"  {f:24s} {v:.3f}")
    imp.to_csv(cfg.OUT / "10_importance_features.csv")

    fig, ax = plt.subplots(figsize=(9, 8))
    top = imp.tail(15)
    ax.barh(top.index, top.values, color="#2a7fb8")
    ax.set(title="Importance des variables (Random Forest)", xlabel="Importance")
    fig.tight_layout()
    fig.savefig(cfg.OUT / "10_importance_features.png", dpi=130)
    plt.close(fig)
    print("-> outputs/10_importance_features.png + .csv")


if __name__ == "__main__":
    main()
