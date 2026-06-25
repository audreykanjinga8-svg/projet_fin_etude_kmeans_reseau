"""
=========================================================
 ÉTAPE 9 — COMPARAISON SUPERVISÉE (borne de référence)
=========================================================
Random Forest et XGBoost utilisent le label pendant
l'entraînement -> borne SUPÉRIEURE. Ce ne sont PAS les
modèles retenus : ils montrent que les 23 features séparent
bien les régimes. On compare aussi les FAUX POSITIFS, pas
seulement l'accuracy (ce qui compte pour un système d'alerte).

ENTRÉES : outputs/03_dataset_agrege.csv + 08_metriques.txt
SORTIES : outputs/09_comparaison_modeles.png
          outputs/09_comparaison_modeles.csv

Lancer :  python src/09_comparaison.py
(XGBoost optionnel : pip install xgboost)
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import config as cfg


def main():
    agg = pd.read_csv(cfg.OUT / "03_dataset_agrege.csv")
    X = agg[cfg.FEATURES]
    y = agg["fichier_source"].map(cfg.CAPTURES)
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.30, random_state=cfg.RANDOM_STATE, stratify=y)

    scores = {}

    rf = RandomForestClassifier(n_estimators=200, random_state=cfg.RANDOM_STATE)
    rf.fit(Xtr, ytr)
    scores["Random Forest"] = accuracy_score(yte, rf.predict(Xte))

    try:
        from xgboost import XGBClassifier
        codes = {c: i for i, c in enumerate(cfg.ORDRE_CLASSES)}
        xgb = XGBClassifier(n_estimators=200, random_state=cfg.RANDOM_STATE,
                            eval_metric="mlogloss")
        xgb.fit(Xtr, ytr.map(codes))
        scores["XGBoost"] = accuracy_score(yte.map(codes), xgb.predict(Xte))
    except ImportError:
        print("(XGBoost non installé — 'pip install xgboost' pour l'ajouter)")

    try:
        ligne = [l for l in open(cfg.OUT / "08_metriques.txt") if l.startswith("Accuracy")]
        scores["K-Means (non supervisé)"] = float(ligne[0].split("=")[1])
    except (FileNotFoundError, IndexError):
        pass

    print("====== COMPARAISON (accuracy) ======")
    for nom, s in sorted(scores.items(), key=lambda x: -x[1]):
        print(f"  {nom:28s} : {s:.3f}")

    s = pd.Series(scores, name="accuracy").sort_values()
    s.to_csv(cfg.OUT / "09_comparaison_modeles.csv")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    couleurs = ["#2a7fb8" if "Means" in n else "#7ab648" for n in s.index]
    ax.barh(s.index, s.values, color=couleurs)
    for i, v in enumerate(s.values):
        ax.text(v + 0.005, i, f"{v:.3f}", va="center")
    ax.set(title="Comparaison des modèles (accuracy)", xlim=(0, 1.05), xlabel="Accuracy")
    fig.tight_layout()
    fig.savefig(cfg.OUT / "09_comparaison_modeles.png", dpi=130)
    plt.close(fig)
    print("-> outputs/09_comparaison_modeles.png + .csv")


if __name__ == "__main__":
    main()
