#!/bin/sh
set -eu
TARGET="${TARGET:-192.168.30.20}"
PORT="${PORT:-7001}"
DURATION="${DURATION:-30}"
SLEEP_SEC="${SLEEP_SEC:-2}"
END=$(( $(date +%s) + DURATION ))
while [ $(date +%s) -lt "$END" ]; do
  echo "test" | nc -w 1 "$TARGET" "$PORT" >/dev/null 2>&1 || true
  sleep "$SLEEP_SEC"
done
