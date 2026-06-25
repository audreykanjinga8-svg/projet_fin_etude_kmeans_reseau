#!/usr/bin/env bash
set -euo pipefail

INTERFACE="${INTERFACE:-eth0}"
TARGET="${TARGET:-192.168.30.20}"
PORT="${PORT:-7001}"
DURATION="${DURATION:-45}"
LOSS="${LOSS:-5}"
DELAY_MS="${DELAY_MS:-20}"

if ! command -v tc >/dev/null 2>&1; then
  echo "tc est introuvable." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 est introuvable." >&2
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "Ce script doit être lancé en root (sudo)." >&2
  exit 1
fi

cleanup() {
  tc qdisc del dev "$INTERFACE" root 2>/dev/null || true
  echo "Netem supprimé sur $INTERFACE"
}
trap cleanup EXIT

echo "Scénario entreprise doux : perte de performance légère"
echo "Perte de paquets = ${LOSS}% | Délai = ${DELAY_MS} ms | Durée = ${DURATION}s"
tc qdisc replace dev "$INTERFACE" root netem loss "${LOSS}%" delay "${DELAY_MS}ms"
TARGET="$TARGET" PORT="$PORT" DURATION="$DURATION" INTERVAL=2 CHUNK_SIZE=16384 ./scripts/scenarios/continuous_tcp_client.sh
