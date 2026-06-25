"""
=========================================================
 ÉTAPE 6 — CHOIX DE K
=========================================================
Teste K de 2 à 10 et trace la méthode du coude (inertie)
et le score de silhouette. On retient K=3, cohérent avec
le coude ET avec la connaissance métier (3 régimes attendus).

ENTRÉE  : outputs/05_X_scaled.csv
SORTIE  : outputs/06_coude_silhouette.png

Lancer :  python src/06_choix_k.py
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import config as cfg


def main():
    X = pd.read_csv(cfg.OUT / "05_X_scaled.csv")
    Ks = range(2, 11)
    inerties, silhouettes = [], []
    for k in Ks:
        km = KMeans(n_clusters=k, random_state=cfg.RANDOM_STATE, n_init=10).fit(X)
        inerties.append(km.inertia_)
        silhouettes.append(silhouette_score(X, km.labels_))
        print(f"  K={k:2d}  inertie={km.inertia_:8.0f}  silhouette={silhouettes[-1]:.3f}")

    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    ax[0].plot(Ks, inerties, "o-", color="#2a7fb8")
    ax[0].axvline(cfg.K, ls="--", color="grey")
    ax[0].set(title="Méthode du coude", xlabel="K", ylabel="Inertie (J)")
    ax[1].plot(Ks, silhouettes, "o-", color="#d33")
    ax[1].axvline(cfg.K, ls="--", color="grey")
    ax[1].set(title="Score de silhouette", xlabel="K", ylabel="Silhouette")
    fig.tight_layout()
    fig.savefig(cfg.OUT / "06_coude_silhouette.png", dpi=130)
    plt.close(fig)
    print(f"-> outputs/06_coude_silhouette.png  (K retenu = {cfg.K})")


if __name__ == "__main__":
    main()
