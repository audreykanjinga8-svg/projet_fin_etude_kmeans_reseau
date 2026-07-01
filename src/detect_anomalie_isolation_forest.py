#!/usr/bin/env python3
"""
=========================================================
 DÉTECTION D'ANOMALIES - ISOLATION FOREST
=========================================================
Détection par Isolation Forest (non supervisé).
Identifie les anomalies comme valeurs aberrantes.

ENTRÉE  : outputs/03_dataset_agrege.csv
SORTIES : outputs/isolation_forest_model.pkl
          outputs/isolation_forest_confusion_matrix.csv
          outputs/isolation_forest_confusion_matrix.png
          outputs/isolation_forest_scores.csv (anomaly scores)

Lancer :  python src/detect_anomalie_isolation_forest.py
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
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (confusion_matrix, accuracy_score, precision_score,
                             recall_score, f1_score, classification_report)

import config as cfg


def main():
    print("\n" + "=" * 70)
    print(" ÉTAPE - DÉTECTION ISOLATION FOREST")
    print("=" * 70)

    # Charger données
    print("\n[1/5] Chargement des données...")
    agg = pd.read_csv(cfg.OUT / "03_dataset_agrege.csv")
    X = agg[cfg.FEATURES].values
    y_true = agg["fichier_source"].map(cfg.CAPTURES)  # Labels réels

    print(f"  Dataset: {len(agg)} échantillons, {len(cfg.FEATURES)} features")
    print(f"  Classes: {y_true.value_counts().to_dict()}")

    # Normalisation
    print("\n[2/5] Normalisation des données...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    print(f"  ✓ Données normalisées")

    # Entraînement Isolation Forest
    print("\n[3/5] Entraînement Isolation Forest...")
    t0 = time.time()
    iso_forest = IsolationForest(
        contamination="auto",  # Auto-détecte % d'anomalies
        random_state=cfg.RANDOM_STATE,
        n_estimators=100
    )
    iso_forest.fit(X_scaled)
    temps_entrainement = time.time() - t0
    print(f"  ✓ Entraîné en {temps_entrainement:.2f}s")

    # Prédictions
    print("\n[4/5] Prédictions anomalies...")
    y_pred_encoded = iso_forest.predict(X_scaled)  # -1: anomalie, 1: normal
    anomaly_scores = iso_forest.score_samples(X_scaled)

    # Mapping à labels de classe
    # Convention : "Normal" = 1, autres = -1 (anomalies)
    y_pred = pd.Series(
        ["Normal" if pred == 1 else "Anomalie" for pred in y_pred_encoded],
        index=y_true.index
    )

    n_anomalies = (y_pred_encoded == -1).sum()
    contamination = iso_forest.offset_  # Seuil d'anomalie
    print(f"  Anomalies détectées: {n_anomalies}/{len(agg)} ({n_anomalies/len(agg)*100:.1f}%)")
    print(f"  Seuil (offset): {contamination:.4f}")

    # Conversion y_true en binaire pour comparaison
    y_true_binary = pd.Series(
        ["Anomalie" if c != "Normal" else "Normal" for c in y_true],
        index=y_true.index
    )

    # Métriques
    accuracy = accuracy_score(y_true_binary, y_pred)
    precision = precision_score(y_true_binary, y_pred, average="macro", zero_division=0)
    recall = recall_score(y_true_binary, y_pred, average="macro", zero_division=0)
    f1 = f1_score(y_true_binary, y_pred, average="macro", zero_division=0)

    print(f"\n  Accuracy  : {accuracy:.4f}")
    print(f"  Precision : {precision:.4f}")
    print(f"  Recall    : {recall:.4f}")
    print(f"  F1-Score  : {f1:.4f}")

    print("\n[Classification Report]")
    print(classification_report(y_true_binary, y_pred, zero_division=0))

    # Matrice de confusion
    print("\n[5/5] Génération matrice de confusion...")
    cm = confusion_matrix(y_true_binary, y_pred, labels=["Normal", "Anomalie"])
    cm_df = pd.DataFrame(
        cm,
        index=["Actual Normal", "Actual Anomalie"],
        columns=["Pred Normal", "Pred Anomalie"]
    )

    print("\n" + cm_df.to_string())

    # Sauvegarde matrice CSV
    cm_df.to_csv(cfg.OUT / "isolation_forest_confusion_matrix.csv")
    print(f"\n  ✓ CSV : outputs/isolation_forest_confusion_matrix.csv")

    # Visualisation matrice
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="YlOrRd", cbar=False, ax=ax,
                xticklabels=["Normal", "Anomalie"],
                yticklabels=["Normal", "Anomalie"])
    ax.set(title="Isolation Forest - Matrice de Confusion",
           xlabel="Prédictions", ylabel="Réalité")
    fig.tight_layout()
    fig.savefig(cfg.OUT / "isolation_forest_confusion_matrix.png", dpi=130)
    plt.close(fig)
    print(f"  ✓ PNG  : outputs/isolation_forest_confusion_matrix.png")

    # Sauvegarde modèle
    joblib.dump(iso_forest, cfg.OUT / "isolation_forest_model.pkl")
    joblib.dump(scaler, cfg.OUT / "isolation_forest_scaler.pkl")
    print(f"  ✓ Modèle: outputs/isolation_forest_model.pkl")
    print(f"  ✓ Scaler: outputs/isolation_forest_scaler.pkl")

    # Sauvegarde scores d'anomalie
    scores_df = pd.DataFrame({
        "true_label": y_true.values,
        "true_binary": y_true_binary.values,
        "predicted": y_pred.values,
        "anomaly_score": anomaly_scores,
        "is_anomaly": (y_pred_encoded == -1).astype(int)
    })
    scores_df.to_csv(cfg.OUT / "isolation_forest_scores.csv", index=False)
    print(f"  ✓ Scores: outputs/isolation_forest_scores.csv")

    # Visualisation scores d'anomalie
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Distribution des scores
    ax1.hist(anomaly_scores, bins=50, edgecolor='black', alpha=0.7)
    ax1.axvline(contamination, color='r', linestyle='--', label=f'Seuil ({contamination:.2f})')
    ax1.set(title="Distribution des Anomaly Scores",
            xlabel="Score d'anomalie", ylabel="Fréquence")
    ax1.legend()

    # Scores par classe réelle
    for label in ["Normal", "Perte de performance", "Erreur de configuration"]:
        mask = (y_true == label).values
        ax2.hist(anomaly_scores[mask], bins=30, alpha=0.6, label=label)
    ax2.axvline(contamination, color='r', linestyle='--', label=f'Seuil ({contamination:.2f})')
    ax2.set(title="Scores par classe réelle",
            xlabel="Score d'anomalie", ylabel="Fréquence")
    ax2.legend()

    fig.tight_layout()
    fig.savefig(cfg.OUT / "isolation_forest_scores.png", dpi=130)
    plt.close(fig)
    print(f"  ✓ Scores plot: outputs/isolation_forest_scores.png")

    print("\n✅ Détection Isolation Forest terminée !")


if __name__ == "__main__":
    main()
