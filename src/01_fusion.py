"""
=========================================================
 ÉTAPE 1 — FUSION
=========================================================
Empile les 3 captures brutes en un seul fichier et ajoute
une colonne `fichier_source` (= la classe réelle, qui ne
servira QU'à l'évaluation).

ENTRÉE  : data/*.csv  (les 3 captures Wireshark)
SORTIE  : outputs/01_dataset_fusionne.csv

Lancer :  python src/01_fusion.py
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import pandas as pd
import config as cfg


def main():
    morceaux = []
    for fichier in cfg.CAPTURES:
        chemin = cfg.DATA / fichier
        if not chemin.exists():
            print(f"  !! manquant : {chemin}")
            continue
        df = pd.read_csv(chemin, low_memory=False, encoding=cfg.ENCODAGE)
        # La colonne "Source" apparaît 2 fois dans l'export Wireshark :
        # pandas renomme la 2e en "Source.1" -> c'est l'adresse MAC.
        if "Source.1" in df.columns:
            df = df.rename(columns={"Source.1": "Source_MAC"})
        df["fichier_source"] = fichier
        morceaux.append(df)
        print(f"  {fichier:26s} : {len(df):>7} paquets")

    fusion = pd.concat(morceaux, ignore_index=True)
    fusion.to_csv(cfg.OUT / "01_dataset_fusionne.csv", index=False)
    print(f"TOTAL : {len(fusion)} paquets -> outputs/01_dataset_fusionne.csv")


if __name__ == "__main__":
    main()
