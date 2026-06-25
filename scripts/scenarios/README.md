# Scénarios d'entreprise pour le détecteur K-Means

Ce dossier contient des scripts prêts à l’emploi pour simuler des cas réalistes de trafic réseau dans un environnement d’entreprise.

## Scénarios disponibles

- normal_web.sh : trafic normal de navigation web et accès à des services internes
- performance_loss.sh : perte de performance avec latence, perte de paquets et congestion
- config_error.sh : erreur de configuration réseau (port down, route cassée, service inaccessible)
- server_tcp.sh : serveur TCP de test basé sur iperf3
- tcp_server.py : serveur TCP simple et robuste pour des flux continus
- continuous_tcp_client.sh : client TCP continu qui envoie du trafic vers un serveur à l’écoute

## Utilisation rapide

1. Démarrer le serveur :
   ```bash
   sudo ./scripts/scenarios/server_tcp.sh
   ```
2. Lancer un scénario client :
   ```bash
   sudo ./scripts/scenarios/normal_web.sh
   ```
3. Laisser tourner le détecteur en parallèle :
   ```bash
   /data/Projet_PFE/projet_kmeans_reseau_modele/.venv/bin/python src/detect_anomalie.py
   ```
