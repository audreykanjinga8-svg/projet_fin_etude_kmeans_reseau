#!/usr/bin/env python3
"""
=========================================================
 DÉTECTION D'ANOMALIES - XGBOOST
=========================================================
Détection par XGBoost avec matrice de confusion.
Supervisé (classification Normal/Perf/Config).

ENTRÉE  : outputs/03_dataset_agrege.csv
SORTIES : outputs/xgboost_model.pkl
          outputs/xgboost_confusion_matrix.csv
          outputs/xgboost_confusion_matrix.png
          outputs/xgboost_resultats.csv (prédictions + labels)

Lancer :  python src/detect_anomalie_xgboost.py
"""
import sys
import time
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import (confusion_matrix, accuracy_score, precision_score,
                             recall_score, f1_score, classification_report)

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("⚠️  XGBoost non installé. Installez avec : pip install xgboost")

import config as cfg


def main():
    if not XGBOOST_AVAILABLE:
        print("❌ Impossible de continuer sans XGBoost. Installez-le d'abord.")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(" ÉTAPE - DÉTECTION XGBOOST")
    print("=" * 70)

    # Charger données
    print("\n[1/5] Chargement des données...")
    agg = pd.read_csv(cfg.OUT / "03_dataset_agrege.csv")
    X = agg[cfg.FEATURES]
    y = agg["fichier_source"].map(cfg.CAPTURES)  # Normal, Perte de performance, Erreur de configuration

    print(f"  Dataset: {len(agg)} échantillons, {len(cfg.FEATURES)} features")
    print(f"  Classes: {y.value_counts().to_dict()}")

    # Split train/test
    print("\n[2/5] Split train/test (70/30)...")
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.30, random_state=cfg.RANDOM_STATE, stratify=y
    )
    print(f"  Train: {len(Xtr)} | Test: {len(Xte)}")

    # Entraînement XGBoost
    print("\n[3/5] Entraînement XGBoost...")
    codes = {c: i for i, c in enumerate(cfg.ORDRE_CLASSES)}  # class -> code numérique
    codes_inv = {v: k for k, v in codes.items()}

    t0 = time.time()
    xgb = XGBClassifier(
        n_estimators=200,
        random_state=cfg.RANDOM_STATE,
        eval_metric="mlogloss",
        verbosity=0
    )
    xgb.fit(Xtr, ytr.map(codes))
    temps_entrainement = time.time() - t0

    print(f"  ✓ Entraîné en {temps_entrainement:.2f}s")

    # Prédictions
    print("\n[4/5] Prédictions sur ensemble de test...")
    y_pred_codes = xgb.predict(Xte)
    y_pred = pd.Series([codes_inv[c] for c in y_pred_codes], index=yte.index)

    # Métriques
    accuracy = accuracy_score(yte, y_pred)
    precision_macro = precision_score(yte, y_pred, average="macro", zero_division=0)
    recall_macro = recall_score(yte, y_pred, average="macro", zero_division=0)
    f1_macro = f1_score(yte, y_pred, average="macro", zero_division=0)

    print(f"\n  Accuracy  : {accuracy:.4f}")
    print(f"  Precision (macro) : {precision_macro:.4f}")
    print(f"  Recall (macro)    : {recall_macro:.4f}")
    print(f"  F1-Score (macro)  : {f1_macro:.4f}")

    print("\n[Classification Report]")
    print(classification_report(yte, y_pred, zero_division=0))

    # Matrice de confusion
    print("\n[5/5] Génération matrice de confusion...")
    cm = confusion_matrix(yte, y_pred, labels=cfg.ORDRE_CLASSES)
    cm_df = pd.DataFrame(
        cm,
        index=["Actual " + c for c in cfg.ORDRE_CLASSES],
        columns=["Pred " + c for c in cfg.ORDRE_CLASSES]
    )

    print("\n" + cm_df.to_string())

    # Sauvegarde matrice CSV
    cm_df.to_csv(cfg.OUT / "xgboost_confusion_matrix.csv")
    print(f"\n  ✓ CSV : outputs/xgboost_confusion_matrix.csv")

    # Visualisation matrice
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False, ax=ax,
                xticklabels=cfg.ORDRE_CLASSES, yticklabels=cfg.ORDRE_CLASSES)
    ax.set(title="XGBoost - Matrice de Confusion", xlabel="Prédictions", ylabel="Réalité")
    fig.tight_layout()
    fig.savefig(cfg.OUT / "xgboost_confusion_matrix.png", dpi=130)
    plt.close(fig)
    print(f"  ✓ PNG  : outputs/xgboost_confusion_matrix.png")

    # Sauvegarde modèle
    joblib.dump(xgb, cfg.OUT / "xgboost_model.pkl")
    print(f"  ✓ Modèle: outputs/xgboost_model.pkl")

    # Sauvegarde résultats détaillés
    resultats = pd.DataFrame({
        "actual": yte.values,
        "predicted": y_pred.values,
        "match": (yte.values == y_pred.values).astype(int)
    })
    resultats.to_csv(cfg.OUT / "xgboost_resultats.csv", index=False)
    print(f"  ✓ Résultats: outputs/xgboost_resultats.csv")

    # Importance des features
    importances = xgb.feature_importances_
    top_features = np.argsort(importances)[::-1][:10]
    print(f"\n[Top 10 Features (importance)]")
    for i, feat_idx in enumerate(top_features, 1):
        print(f"  {i:2d}. {cfg.FEATURES[feat_idx]:30s} : {importances[feat_idx]:.4f}")

    print("\n✅ Détection XGBoost terminée !")


if __name__ == "__main__":
    main()
