#!/usr/bin/env bash
set -euo pipefail

TARGET="${TARGET:-192.168.30.20}"
PORT="${PORT:-7001}"
DURATION="${DURATION:-20}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 est introuvable." >&2
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "Ce script doit être lancé en root (sudo)." >&2
  exit 1
fi

echo "Scénario entreprise doux : erreur de configuration réseau"
echo "Simulation d'un service temporairement indisponible"

python3 - "$TARGET" "$PORT" "$DURATION" <<'PY'
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])
duration = int(sys.argv[3])
end = time.time() + duration

while time.time() < end:
    try:
        with socket.create_connection((host, port), timeout=1) as sock:
            sock.sendall(b'ping')
    except Exception:
        pass
    time.sleep(2)
PY

echo "Scénario de configuration terminé"
