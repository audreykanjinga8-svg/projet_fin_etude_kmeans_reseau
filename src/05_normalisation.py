"""
=========================================================
 ÉTAPE 5 — NORMALISATION
=========================================================
Centre-réduit les 23 features (StandardScaler). Obligatoire :
K-Means utilise la distance euclidienne, donc une feature à
grande échelle (nb_paquets) écraserait les proportions (0-1)
sans normalisation.

ENTRÉE  : outputs/03_dataset_agrege.csv
SORTIES : outputs/05_scaler.pkl
          outputs/05_X_scaled.csv

Lancer :  python src/05_normalisation.py
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import pandas as pd
import joblib
from sklearn.preprocessing import StandardScaler
import config as cfg


def main():
    df = pd.read_csv(cfg.OUT / "03_dataset_agrege.csv")
    X = df[cfg.FEATURES]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    joblib.dump(scaler, cfg.OUT / "05_scaler.pkl")
    pd.DataFrame(X_scaled, columns=cfg.FEATURES).to_csv(
        cfg.OUT / "05_X_scaled.csv", index=False)
    print("Normalisation OK -> outputs/05_scaler.pkl + 05_X_scaled.csv")


if __name__ == "__main__":
    main()
