#!/usr/bin/env python3
"""
=========================================================
 DÉTECTION D'ANOMALIES - ENSEMBLE
=========================================================
Ensemble voting : combine K-Means, XGBoost, Isolation Forest
pour une détection robuste et comparative.

ENTRÉE  : outputs/03_dataset_agrege.csv
          outputs/*_model.pkl (tous les modèles)
SORTIES : outputs/ensemble_confusion_matrix.csv
          outputs/ensemble_confusion_matrix.png
          outputs/ensemble_comparaison.csv (résultats tous algos)
          outputs/ensemble_voting_matrix.png (heatmap votes)

Lancer :  python src/detect_anomalie_ensemble.py
"""
import sys
import time
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (confusion_matrix, accuracy_score, precision_score,
                             recall_score, f1_score, classification_report)

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

import config as cfg


def charger_modeles():
    """Charge tous les modèles disponibles"""
    modeles = {}
    
    # K-Means
    try:
        modeles['kmeans'] = {
            'model': joblib.load(cfg.OUT / "07_kmeans_model.pkl"),
            'scaler': joblib.load(cfg.OUT / "05_scaler.pkl"),
            'available': True
        }
        print("  ✓ K-Means chargé")
    except Exception as e:
        print(f"  ✗ K-Means non disponible: {e}")
        modeles['kmeans'] = {'available': False}

    # XGBoost
    if XGBOOST_AVAILABLE:
        try:
            modeles['xgboost'] = {
                'model': joblib.load(cfg.OUT / "xgboost_model.pkl"),
                'available': True
            }
            print("  ✓ XGBoost chargé")
        except Exception as e:
            print(f"  ✗ XGBoost non disponible: {e}")
            modeles['xgboost'] = {'available': False}
    else:
        modeles['xgboost'] = {'available': False}

    # Isolation Forest
    try:
        modeles['iso_forest'] = {
            'model': joblib.load(cfg.OUT / "isolation_forest_model.pkl"),
            'scaler': joblib.load(cfg.OUT / "isolation_forest_scaler.pkl"),
            'available': True
        }
        print("  ✓ Isolation Forest chargé")
    except Exception as e:
        print(f"  ✗ Isolation Forest non disponible: {e}")
        modeles['iso_forest'] = {'available': False}

    return modeles


def predire_kmeans(X, modeles):
    """Prédiction K-Means -> classe"""
    if not modeles['kmeans']['available']:
        return None
    
    scaler = modeles['kmeans']['scaler']
    km = modeles['kmeans']['model']
    mapping = json.load(open(cfg.OUT / "cluster_mapping.json"))
    
    X_scaled = pd.DataFrame(scaler.transform(X), columns=cfg.FEATURES)
    clusters = km.predict(X_scaled)
    
    predictions = []
    for c in clusters:
        info = mapping[str(int(c))]
        predictions.append(info["regime"])
    
    return np.array(predictions)


def predire_xgboost(X, modeles):
    """Prédiction XGBoost -> classe"""
    if not modeles['xgboost']['available']:
        return None
    
    xgb = modeles['xgboost']['model']
    codes_inv = {0: "Normal", 1: "Perte de performance", 2: "Erreur de configuration"}
    
    y_pred_codes = xgb.predict(X)
    return np.array([codes_inv[int(c)] for c in y_pred_codes])


def predire_iso_forest(X, modeles):
    """Prédiction Isolation Forest -> Normal/Anomalie"""
    if not modeles['iso_forest']['available']:
        return None
    
    scaler = modeles['iso_forest']['scaler']
    iso = modeles['iso_forest']['model']
    
    X_scaled = scaler.transform(X)
    y_pred_encoded = iso.predict(X_scaled)
    
    # -1: anomalie, 1: normal
    return np.array(["Anomalie" if p == -1 else "Normal" for p in y_pred_encoded])


def voter_ensemble(pred_kmeans, pred_xgb, pred_iso):
    """Vote majoritaire entre les trois algos"""
    votes = []
    
    for i in range(len(pred_kmeans)):
        # Normaliser les prédictions Iso Forest
        iso_pred = pred_iso[i]
        if iso_pred == "Anomalie":
            # Anomalie = Perf dégradée ou Config
            iso_vote = ["Perte de performance", "Erreur de configuration"]
        else:
            iso_vote = ["Normal"]
        
        # Collecter les votes
        candidats = [pred_kmeans[i], pred_xgb[i]] + iso_vote
        
        # Vote majoritaire
        from collections import Counter
        votes_count = Counter(candidats)
        winner = votes_count.most_common(1)[0][0]
        votes.append(winner)
    
    return np.array(votes)


def main():
    print("\n" + "=" * 70)
    print(" ÉTAPE - ENSEMBLE VOTING (K-Means + XGBoost + Isolation Forest)")
    print("=" * 70)

    # Charger données
    print("\n[1/6] Chargement des données...")
    agg = pd.read_csv(cfg.OUT / "03_dataset_agrege.csv")
    X = agg[cfg.FEATURES].values
    y_true = agg["fichier_source"].map(cfg.CAPTURES)
    
    print(f"  Dataset: {len(agg)} échantillons")
    print(f"  Classes: {y_true.value_counts().to_dict()}")

    # Charger modèles
    print("\n[2/6] Chargement des modèles...")
    modeles = charger_modeles()
    modeles_dispo = [m for m in modeles if modeles[m]['available']]
    
    if len(modeles_dispo) < 2:
        print(f"❌ Besoin d'au moins 2 modèles, trouvé: {modeles_dispo}")
        sys.exit(1)

    # Prédictions individuelles
    print("\n[3/6] Prédictions par algorithme...")
    pred_kmeans = predire_kmeans(X, modeles)
    pred_xgb = predire_xgboost(X, modeles)
    pred_iso = predire_iso_forest(X, modeles)

    if pred_kmeans is not None:
        print(f"  K-Means: {len(set(pred_kmeans))} classes")
    if pred_xgb is not None:
        print(f"  XGBoost: {len(set(pred_xgb))} classes")
    if pred_iso is not None:
        print(f"  Iso Forest: {len(set(pred_iso))} classes")

    # Voting ensemble
    print("\n[4/6] Vote majoritaire...")
    y_pred_ensemble = voter_ensemble(pred_kmeans, pred_xgb, pred_iso)
    print(f"  ✓ Prédictions combées: {len(set(y_pred_ensemble))} classes")

    # Métriques ensemble
    print("\n[5/6] Métriques...")
    accuracy = accuracy_score(y_true, y_pred_ensemble)
    precision_macro = precision_score(y_true, y_pred_ensemble, average="macro", zero_division=0)
    recall_macro = recall_score(y_true, y_pred_ensemble, average="macro", zero_division=0)
    f1_macro = f1_score(y_true, y_pred_ensemble, average="macro", zero_division=0)

    print(f"\n  Ensemble Accuracy  : {accuracy:.4f}")
    print(f"  Ensemble Precision : {precision_macro:.4f}")
    print(f"  Ensemble Recall    : {recall_macro:.4f}")
    print(f"  Ensemble F1-Score  : {f1_macro:.4f}")

    # Comparaison avec modèles individuels
    print("\n[Comparaison Individuels]")
    comparaison = {
        'Algorithme': [],
        'Accuracy': [],
        'Precision': [],
        'Recall': [],
        'F1-Score': []
    }

    if pred_kmeans is not None:
        acc_km = accuracy_score(y_true, pred_kmeans)
        prec_km = precision_score(y_true, pred_kmeans, average="macro", zero_division=0)
        rec_km = recall_score(y_true, pred_kmeans, average="macro", zero_division=0)
        f1_km = f1_score(y_true, pred_kmeans, average="macro", zero_division=0)
        print(f"  K-Means         : Acc={acc_km:.4f}, Prec={prec_km:.4f}, Rec={rec_km:.4f}, F1={f1_km:.4f}")
        comparaison['Algorithme'].append('K-Means')
        comparaison['Accuracy'].append(acc_km)
        comparaison['Precision'].append(prec_km)
        comparaison['Recall'].append(rec_km)
        comparaison['F1-Score'].append(f1_km)

    if pred_xgb is not None:
        acc_xgb = accuracy_score(y_true, pred_xgb)
        prec_xgb = precision_score(y_true, pred_xgb, average="macro", zero_division=0)
        rec_xgb = recall_score(y_true, pred_xgb, average="macro", zero_division=0)
        f1_xgb = f1_score(y_true, pred_xgb, average="macro", zero_division=0)
        print(f"  XGBoost         : Acc={acc_xgb:.4f}, Prec={prec_xgb:.4f}, Rec={rec_xgb:.4f}, F1={f1_xgb:.4f}")
        comparaison['Algorithme'].append('XGBoost')
        comparaison['Accuracy'].append(acc_xgb)
        comparaison['Precision'].append(prec_xgb)
        comparaison['Recall'].append(rec_xgb)
        comparaison['F1-Score'].append(f1_xgb)

    # Ensemble
    comparaison['Algorithme'].append('Ensemble (Voting)')
    comparaison['Accuracy'].append(accuracy)
    comparaison['Precision'].append(precision_macro)
    comparaison['Recall'].append(recall_macro)
    comparaison['F1-Score'].append(f1_macro)
    print(f"  Ensemble (Voting) : Acc={accuracy:.4f}, Prec={precision_macro:.4f}, Rec={recall_macro:.4f}, F1={f1_macro:.4f}")

    # Sauvegarde comparaison
    comp_df = pd.DataFrame(comparaison)
    comp_df.to_csv(cfg.OUT / "ensemble_comparaison.csv", index=False)
    print(f"\n  ✓ Comparaison: outputs/ensemble_comparaison.csv")

    # Visualisation comparaison
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    metrics = ['Accuracy', 'Precision', 'Recall', 'F1-Score']
    colors = ['#2a7fb8' if algo != 'Ensemble (Voting)' else '#7ab648' 
              for algo in comp_df['Algorithme']]

    for ax, metric in zip(axes.flat, metrics):
        ax.barh(comp_df['Algorithme'], comp_df[metric], color=colors)
        ax.set(xlim=(0, 1), title=f'{metric}')
        for i, v in enumerate(comp_df[metric]):
            ax.text(v + 0.02, i, f'{v:.3f}', va='center')

    fig.suptitle("Comparaison des Algorithmes de Détection", fontsize=14, fontweight='bold')
    fig.tight_layout()
    fig.savefig(cfg.OUT / "ensemble_comparaison.png", dpi=130)
    plt.close(fig)
    print(f"  ✓ Graphe comparaison: outputs/ensemble_comparaison.png")

    # Matrice de confusion ensemble
    print("\n[6/6] Matrice de confusion...")
    cm = confusion_matrix(y_true, y_pred_ensemble, labels=cfg.ORDRE_CLASSES)
    cm_df = pd.DataFrame(
        cm,
        index=["Actual " + c for c in cfg.ORDRE_CLASSES],
        columns=["Pred " + c for c in cfg.ORDRE_CLASSES]
    )

    print("\n" + cm_df.to_string())
    cm_df.to_csv(cfg.OUT / "ensemble_confusion_matrix.csv")
    print(f"  ✓ CSV : outputs/ensemble_confusion_matrix.csv")

    # Visualisation matrice
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Greens", cbar=False, ax=ax,
                xticklabels=cfg.ORDRE_CLASSES, yticklabels=cfg.ORDRE_CLASSES)
    ax.set(title="Ensemble (Voting) - Matrice de Confusion",
           xlabel="Prédictions", ylabel="Réalité")
    fig.tight_layout()
    fig.savefig(cfg.OUT / "ensemble_confusion_matrix.png", dpi=130)
    plt.close(fig)
    print(f"  ✓ PNG  : outputs/ensemble_confusion_matrix.png")

    # Sauvegarde résultats détaillés
    resultats = pd.DataFrame({
        "true_label": y_true.values,
        "kmeans": pred_kmeans if pred_kmeans is not None else "N/A",
        "xgboost": pred_xgb if pred_xgb is not None else "N/A",
        "isolation_forest": pred_iso if pred_iso is not None else "N/A",
        "ensemble_vote": y_pred_ensemble,
        "match_ensemble": (y_true.values == y_pred_ensemble).astype(int)
    })
    resultats.to_csv(cfg.OUT / "ensemble_resultats.csv", index=False)
    print(f"  ✓ Résultats détaillés: outputs/ensemble_resultats.csv")

    print("\n✅ Ensemble terminé !")


if __name__ == "__main__":
    main()
