#!/bin/sh
set -eu
PORT="${PORT:-7001}"
while true; do
  nc -l "$PORT" >/dev/null 2>&1 || true
done
