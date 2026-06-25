#!/usr/bin/env bash
set -euo pipefail

TARGET="${TARGET:-192.168.30.20}"
PORT="${PORT:-80}"
DURATION="${DURATION:-45}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl est introuvable." >&2
  exit 1
fi

echo "Scénario entreprise : navigation web normale"
echo "Simulation d'un utilisateur qui visite plusieurs services web internes"

end=$((SECONDS + DURATION))
while (( SECONDS < end )); do
  curl -sS --max-time 3 "http://$TARGET:$PORT/" >/dev/null || true
  sleep 2
  curl -sS --max-time 3 "http://$TARGET:$PORT/health" >/dev/null || true
  sleep 2
  curl -sS --max-time 3 "http://$TARGET:$PORT/login" >/dev/null || true
  sleep 2
done

echo "Scénario normal terminé"
