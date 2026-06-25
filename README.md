# Détection de anomalies réseau par K-Means

Ce projet met en place un pipeline complet pour détecter des anomalies sur un réseau à partir de captures Wireshark. L'objectif est de classer des fenêtres de trafic en trois régimes principaux : Normal, Perte de performance et Erreur de configuration.

## Installation

1. Ouvrir le dossier du projet dans VS Code.
2. Ouvrir un terminal.
3. Exécuter les commandes suivantes :

   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

4. Placer les trois captures dans le dossier data :
   - normal_capture.csv
   - performance_capture.csv
   - erreur_conf.csv

## Lancement du pipeline

Exécuter les scripts dans l'ordre suivant :

- python src/01_fusion.py
- python src/02_enrichissement.py
- python src/03_agregation.py
- python src/04_exploration.py
- python src/05_normalisation.py
- python src/06_choix_k.py
- python src/07_entrainement.py
- python src/08_evaluation.py
- python src/09_comparaison.py
- python src/10_metriques_avancees.py

Chaque script affiche les résultats dans le terminal et écrit les sorties dans outputs.

## Résultats obtenus

Avec une fenêtre de 5 secondes et K égal à 3, le pipeline donne un résultat stable et interprétable :

- Fusion : environ 198 486 paquets
- Agrégation : 946 fenêtres avec 23 features
- Entraînement : inertie proche de 13 000 et clusters de taille approximative 467, 321 et 158
- Évaluation : ARI autour de 0,74, accuracy autour de 0,83, et recall sur la classe Erreur de configuration proche de 1,00
- Comparaison supervisée : Random Forest et XGBoost servent de référence et atteignent des scores proches de 0,99

## Paramètres principaux

Le fichier config.py permet de régler :

- FENETRE_SEC : taille de la fenêtre temporelle
- K : nombre de clusters
- ENCODAGE : latin 1

## Points importants

Le fenêtrage est au cœur du traitement. La détection ne se fait pas sur un paquet isolé, mais sur des fenêtres de trafic de 5 secondes. K-Means n'utilise pas les labels pendant l'apprentissage. Ces labels servent uniquement pour évaluer la qualité du clustering et comparer les résultats avec des modèles supervisés.
