#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
while true; do
  python bot.py || true
  echo "Bot caiu. Reiniciando em 5 segundos..."
  sleep 5
done
