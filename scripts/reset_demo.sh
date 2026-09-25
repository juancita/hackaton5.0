#!/usr/bin/env bash
# reset_demo.sh — Deja el demo limpio antes del pitch:
#   borra alertas, viajes y cupos de ensayo, y vuelve a cargar los conductores de demo.
#   (No borra usuarios ni los números vinculados de Telegram.)
# Uso: bash scripts/reset_demo.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
docker compose exec -T db psql -U muevete -d muevete -q -c \
  "delete from votes; delete from reports; delete from incidents; delete from seat_requests; delete from trips; delete from driver_profiles;"
docker compose exec -T backend python -m scripts.seed_demo
docker compose restart backend >/dev/null   # limpia también la memoria del chat
echo "✅ Demo listo: sin alertas, con conductores y viajes de ejemplo."
