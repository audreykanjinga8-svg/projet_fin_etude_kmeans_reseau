#!/usr/bin/env bash
set -euo pipefail

INTERFACE="${INTERFACE:-eth0}"
TARGET="${TARGET:-192.168.30.20}"
PORT="${PORT:-5201}"
DURATION="${DURATION:-60}"
LOSS="${LOSS:-15}"
DELAY_MS="${DELAY_MS:-80}"

if ! command -v tc >/dev/null 2>&1; then
  echo "tc est introuvable. Installe-le avant de continuer." >&2
  exit 1
fi

if ! command -v iperf3 >/dev/null 2>&1; then
  echo "iperf3 est introuvable. Installe-le avant de continuer." >&2
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

echo "Application de la perte de performance sur $INTERFACE"
echo "  - perte = ${LOSS}%"
echo "  - délai = ${DELAY_MS} ms"
echo "  - cible = ${TARGET}:${PORT}"
echo "  - durée = ${DURATION}s"

tc qdisc replace dev "$INTERFACE" root netem loss "${LOSS}%" delay "${DELAY_MS}ms"

echo "Lancement du test iperf3..."
iperf3 -c "$TARGET" -p "$PORT" -t "$DURATION" -i 2 -P 4
