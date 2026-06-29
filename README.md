# Détection d'anomalies réseau par K-Means

Ce projet met en place un pipeline complet pour détecter des anomalies sur un réseau à partir de captures Wireshark. L'objectif est de classer des fenêtres de trafic en trois régimes principaux : Normal, Perte de performance et Erreur de configuration.

Le projet se découpe en deux parties : l'entraînement du modèle à partir de captures enregistrées, et la détection en direct sur un réseau GNS3 avec remontée vers Zabbix et remédiation automatique.

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

## Lancement du pipeline d'entraînement

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
- python src/11_mapping_clusters.py

Chaque script affiche les résultats dans le terminal et écrit les sorties dans outputs.

## Résultats obtenus

Avec une fenêtre de 5 secondes et K égal à 3, le pipeline donne un résultat stable et interprétable :

- Fusion : environ 198 486 paquets
- Agrégation : 946 fenêtres avec 23 features
- Entraînement : inertie proche de 13 000 et clusters de taille approximative 467, 321 et 158
- Évaluation : ARI autour de 0,74, accuracy autour de 0,83, et recall sur la classe Erreur de configuration proche de 1,00
- Comparaison supervisée : Random Forest et XGBoost servent de référence et atteignent des scores proches de 0,99

## Détection en direct

Une fois le modèle entraîné, le script src/detect_anomalie.py tourne en continu sur la machine hôte. Toutes les 5 secondes il relit les nouveaux paquets de la capture GNS3, calcule les 23 features de la fenêtre, prédit le cluster avec K-Means, traduit le cluster en code régime, et envoie le résultat à Zabbix.

Les trois codes régime sont :

- 0 : Normal
- 1 : Perte de performance
- 2 : Erreur de configuration

Lancer la détection depuis la racine du projet :

   python3 src/detect_anomalie.py

Options utiles :

   python3 src/detect_anomalie.py --once     pour un seul cycle puis quitter
   python3 src/detect_anomalie.py --debug    pour afficher le détail des 23 features

Au démarrage, la ligne "Capture incrementale active" confirme que le script ne relit pas tout le fichier .pcap à chaque cycle. C'est important car la capture GNS3 grossit en continu, et relire le fichier entier finissait par bloquer le script. La lecture incrémentale ne lit que les paquets nouveaux depuis le dernier cycle.

Le détail de chaque détection est aussi écrit dans src/detect_anomalie.log. Pour suivre en direct :

   tail -f src/detect_anomalie.log

## Reproduire les trois régimes pour tester

Les anomalies sont injectées automatiquement dans les nœuds GNS3. D'abord, sur le nœud serveur (datacenter), lancer un récepteur :

   while true; do nc -l -p 9000 >/dev/null 2>&1; done

Trafic Normal (code 0), depuis un nœud client :

   SERVER=192.168.30.20
   while true; do dd if=/dev/zero bs=1024 count=500 2>/dev/null | nc -w3 $SERVER 9000; sleep 1; done

Perte de performance (code 1). On dégrade le réseau puis on ouvre beaucoup de connexions courtes, qui peinent alors à s'établir (beaucoup de SYN, peu de réponses, retransmissions). C'est cette signature, et pas un simple gros transfert, qui correspond au régime perte de performance :

   tc qdisc add dev eth0 root netem delay 300ms loss 40%
   SERVER=192.168.30.20
   while true; do for i in $(seq 1 30); do ( echo x | nc -w2 $SERVER 9000 >/dev/null 2>&1 ) & done; sleep 1; done

Pour arrêter et rétablir le réseau du nœud :

   tc qdisc del dev eth0 root

Erreur de configuration (code 2). Couper l'interface provoque une quasi-absence de trafic, ce qui est classé comme une erreur de configuration :

   ip link set eth0 down; sleep 10; ip link set eth0 up

## Remontée vers Zabbix et remédiation

Le script envoie deux valeurs à Zabbix : kmeans.regime (le code 0, 1 ou 2) et kmeans.detail (la description lisible). Un déclencheur Zabbix sur kmeans.regime supérieur ou égal à 1 lance une action, qui exécute un playbook Ansible de remédiation sur le nœud concerné. Cette partie remédiation est en cours d'intégration.

## Paramètres principaux

Le fichier config.py permet de régler :

- FENETRE_SEC : taille de la fenêtre temporelle
- K : nombre de clusters
- ENCODAGE : latin 1

## Points importants

Le fenêtrage est au cœur du traitement. La détection ne se fait pas sur un paquet isolé, mais sur des fenêtres de trafic de 5 secondes. K-Means n'utilise pas les labels pendant l'apprentissage. Ces labels servent uniquement pour évaluer la qualité du clustering et comparer les résultats avec des modèles supervisés.

K-Means choisit toujours le cluster dont le centre est le plus proche. Une fenêtre très inhabituelle mais sans signature claire peut donc être rattachée au régime Normal. C'est une limite connue du non supervisé. De plus, le régime perte de performance correspond surtout à des connexions qui peinent à s'établir, donc à un réseau sous pression, et pas à n'importe quel ralentissement. Enfin, la détection ne voit que le trafic qui passe par le lien capturé dans GNS3.
