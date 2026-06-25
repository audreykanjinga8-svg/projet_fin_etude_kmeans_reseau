"""
=========================================================
 ÉTAPE 8 — ÉVALUATION (a posteriori)
=========================================================
Compare les clusters trouvés aux vraies classes. Les labels
ne servent QU'ICI, pour évaluer — pas pour entraîner.

Produit : ARI, accuracy équivalente, matrice de confusion,
précision/rappel par classe, et l'analyse des FAUX POSITIFS
sur la classe critique (erreur de configuration).

ENTRÉES : outputs/07_resultats_clustering.csv + 03_dataset_agrege.csv
SORTIES : outputs/08_matrice_confusion.png
          outputs/08_metriques.txt

Lancer :  python src/08_evaluation.py
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import (adjusted_rand_score, confusion_matrix,
                             classification_report)
from scipy.optimize import linear_sum_assignment
import config as cfg


def main():
    res = pd.read_csv(cfg.OUT / "07_resultats_clustering.csv")
    agg = pd.read_csv(cfg.OUT / "03_dataset_agrege.csv")
    classe = agg["fichier_source"].map(cfg.CAPTURES)
    y = classe.map({c: i for i, c in enumerate(cfg.ORDRE_CLASSES)}).values
    clusters = res["cluster"].values

    # 1) ARI (indépendant de la numérotation des clusters)
    ari = adjusted_rand_score(y, clusters)

    # 2) Mapping optimal cluster -> classe (pour une lecture supervisée)
    M = confusion_matrix(y, clusters)
    lignes, cols = linear_sum_assignment(-M)
    mapping = {cl: cls for cls, cl in zip(lignes, cols)}
    y_pred = np.array([mapping[c] for c in clusters])
    acc = (y_pred == y).mean()

    print("====== ÉVALUATION K-MEANS ======")
    print(f"ARI (référence clustering) : {ari:.3f}")
    print(f"Accuracy équivalente       : {acc:.3f}  ({(y_pred==y).sum()}/{len(y)})\n")

    cm = confusion_matrix(y, y_pred)
    print("Matrice de confusion :")
    print(pd.DataFrame(cm, index=[f"vrai_{c}" for c in cfg.ORDRE_CLASSES],
                       columns=[f"pred_{c}" for c in cfg.ORDRE_CLASSES]).to_string())
    print()
    print(classification_report(y, y_pred, target_names=cfg.ORDRE_CLASSES, digits=3))

    # 3) Faux positifs / négatifs sur la classe critique
    idx = cfg.ORDRE_CLASSES.index("Erreur de configuration")
    fp = int(((y_pred == idx) & (y != idx)).sum())
    fn = int(((y_pred != idx) & (y == idx)).sum())
    print(f"Classe critique 'Erreur de configuration' :")
    print(f"  Faux positifs : {fp}   Faux négatifs : {fn}")
    print("  (FP = fausse alerte envoyée à l'opérateur ; FN = panne manquée)")

    # 4) Graphe matrice de confusion
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(3), cfg.ORDRE_CLASSES, rotation=25, ha="right")
    ax.set_yticks(range(3), cfg.ORDRE_CLASSES)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set(title="Matrice de confusion (K-Means)", xlabel="Prédit", ylabel="Réel")
    fig.colorbar(im, fraction=0.046)
    fig.tight_layout()
    fig.savefig(cfg.OUT / "08_matrice_confusion.png", dpi=130)
    plt.close(fig)

    with open(cfg.OUT / "08_metriques.txt", "w") as f:
        f.write(f"ARI={ari:.3f}\nAccuracy={acc:.3f}\nFP={fp}\nFN={fn}\n")
    print("-> outputs/08_matrice_confusion.png + 08_metriques.txt")


if __name__ == "__main__":
    main()
