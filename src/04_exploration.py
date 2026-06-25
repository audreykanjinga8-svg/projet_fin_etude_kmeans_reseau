"""
=========================================================
 ÉTAPE 4 — EXPLORATION (corrélation + distributions)
=========================================================
Analyse exploratoire AVANT de modéliser. Deux choses :
  - matrice de corrélation : repère les features redondantes
    (fortement corrélées) -> justifie le choix des 23 features.
  - distributions par classe : montre visuellement que les
    features séparent (ou non) les 3 régimes de trafic.

Ces graphes servent à TOUS les modèles ensuite : comme on
nourrit K-Means ET RandomForest/XGBoost avec les mêmes
features, la comparaison est équitable.

ENTRÉE  : outputs/03_dataset_agrege.csv
SORTIES : outputs/04_correlation.png
          outputs/04_distributions.png

Lancer :  python src/04_exploration.py
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import config as cfg


def main():
    df = pd.read_csv(cfg.OUT / "03_dataset_agrege.csv")
    X = df[cfg.FEATURES]

    # --- 1) Matrice de corrélation ---
    corr = X.corr()
    n = len(cfg.FEATURES)
    fig, ax = plt.subplots(figsize=(15, 13))
    im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(n), cfg.FEATURES, rotation=90, fontsize=8)
    ax.set_yticks(range(n), cfg.FEATURES, fontsize=8)
    # Valeur de corrélation écrite dans chaque case
    for i in range(n):
        for j in range(n):
            v = corr.iloc[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="white" if abs(v) > 0.55 else "black", fontsize=6.5)
    ax.set_title("Matrice de corrélation des 23 features")
    fig.colorbar(im, fraction=0.046)
    fig.tight_layout()
    fig.savefig(cfg.OUT / "04_correlation.png", dpi=150)
    plt.close(fig)

    # Paires fortement corrélées (|r| > 0.85) — utile à signaler dans le mémoire
    forte = []
    for i in range(len(cfg.FEATURES)):
        for j in range(i + 1, len(cfg.FEATURES)):
            r = corr.iloc[i, j]
            if abs(r) > 0.85:
                forte.append((cfg.FEATURES[i], cfg.FEATURES[j], round(r, 2)))
    print("Paires fortement corrélées (|r|>0.85) :")
    for a, b, r in forte:
        print(f"  {a} ~ {b} : r={r}")
    if not forte:
        print("  aucune -> pas de redondance flagrante entre features")

    # --- 2) Distributions de 6 features clés par classe ---
    classe = df["fichier_source"].map(cfg.CAPTURES)
    cles = ["pct_tcp", "pct_icmp", "pct_retransmission",
            "tcp_win_mean", "nb_paquets", "pct_syn"]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    for ax, feat in zip(axes.ravel(), cles):
        donnees = [df.loc[classe == c, feat] for c in cfg.ORDRE_CLASSES]
        ax.boxplot(donnees, showfliers=False)
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels(["Norm.", "Perf.", "Conf."])
        ax.set_title(feat, fontsize=11)
    fig.suptitle("Distribution des features par classe réelle", fontsize=13)
    fig.tight_layout()
    fig.savefig(cfg.OUT / "04_distributions.png", dpi=130)
    plt.close(fig)

    print("-> outputs/04_correlation.png et 04_distributions.png")


if __name__ == "__main__":
    main()
