#!/usr/bin/env bash
set -euo pipefail

TARGET="${TARGET:-192.168.30.20}"
PORT="${PORT:-7001}"
DURATION="${DURATION:-45}"
INTERVAL="${INTERVAL:-2}"
CHUNK_SIZE="${CHUNK_SIZE:-16384}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 est introuvable." >&2
  exit 1
fi

echo "Scénario entreprise doux : trafic TCP ponctuel vers $TARGET:$PORT"
echo "Durée : ${DURATION}s | intervalle : ${INTERVAL}s | taille : ${CHUNK_SIZE} octets"

python3 - "$TARGET" "$PORT" "$DURATION" "$INTERVAL" "$CHUNK_SIZE" <<'PY'
import socket
import sys
import time
import os

host = sys.argv[1]
port = int(sys.argv[2])
duration = int(sys.argv[3])
interval = float(sys.argv[4])
chunk_size = int(sys.argv[5])

end = time.time() + duration
payload = os.urandom(chunk_size)

while time.time() < end:
    try:
        with socket.create_connection((host, port), timeout=2) as sock:
            sock.sendall(payload)
            sock.shutdown(socket.SHUT_WR)
            sock.recv(1024)
            time.sleep(interval)
    except Exception as exc:
        print(f"[client] erreur: {exc}", flush=True)
        time.sleep(interval)
PY

echo "Scénario TCP doux terminé"
