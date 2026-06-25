#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-7001}"
HOST="${HOST:-0.0.0.0}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 est introuvable." >&2
  exit 1
fi

echo "Serveur TCP de test démarré sur $HOST:$PORT"
echo "Appuyez sur Ctrl+C pour arrêter"
python3 scripts/scenarios/tcp_server.py --host "$HOST" --port "$PORT"
