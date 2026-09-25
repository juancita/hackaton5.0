#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# telegram_demo.sh — Deja el bot de Telegram funcionando desde la app real.
#
# Qué hace:
#   1. Verifica que TELEGRAM_TOKEN esté en el .env de la raíz.
#   2. Levanta los servicios (docker compose).
#   3. Abre un túnel HTTPS público con cloudflared hacia el backend (:8080).
#   4. Escribe PUBLIC_BASE_URL en .env y reinicia el backend (para las imágenes de ruta).
#   5. Registra el webhook de Telegram apuntando al túnel.
#   6. Deja el túnel abierto: MANTÉN esta terminal abierta durante el demo.
#
# Uso:  bash scripts/telegram_demo.sh
# Antes: pon TELEGRAM_TOKEN (y opcional TELEGRAM_WEBHOOK_SECRET) en .env
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."   # raíz del repo
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"

command -v cloudflared >/dev/null || { echo "❌ Falta cloudflared. Instálalo: brew install cloudflared"; exit 1; }
command -v docker >/dev/null || { echo "❌ Falta docker en el PATH. export PATH=\"/Applications/Docker.app/Contents/Resources/bin:\$PATH\""; exit 1; }

# 1) Token
set -a; [ -f .env ] && . ./.env; set +a
if [ -z "${TELEGRAM_TOKEN:-}" ]; then
  echo "❌ Falta TELEGRAM_TOKEN en .env (raíz). Ponlo (de @BotFather) y reintenta."; exit 1
fi
API_PORT="${API_PORT:-8080}"

# 2) Servicios arriba
echo "🐳 Levantando servicios..."
docker compose up -d >/dev/null

# 3) Túnel cloudflared hacia el backend
LOG="$(mktemp)"
echo "🌐 Abriendo túnel HTTPS hacia http://localhost:${API_PORT} ..."
cloudflared tunnel --url "http://localhost:${API_PORT}" >"$LOG" 2>&1 &
TUNEL_PID=$!
trap 'kill $TUNEL_PID 2>/dev/null || true' EXIT

# 4) Esperar la URL pública
URL=""
for _ in $(seq 1 40); do
  URL="$(grep -Eo 'https://[a-z0-9.-]+\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done
[ -z "$URL" ] && { echo "❌ No se obtuvo URL del túnel. Log:"; cat "$LOG"; exit 1; }
echo "✅ URL pública del backend: $URL"

# 4b) Esperar a que el túnel sea ENRUTABLE públicamente antes de registrar el webhook
#     (si no, Telegram responde "Failed to resolve host").
echo -n "⏳ Esperando enrutamiento público"
for _ in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 "$URL/health" || true)"
  [ "$code" = "200" ] && { echo " -> OK"; break; }
  echo -n "."; sleep 2
done

# 5) PUBLIC_BASE_URL en .env + reiniciar backend (para /mapas/ruta.jpg)
if grep -q '^PUBLIC_BASE_URL=' .env; then
  sed -i '' "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=$URL|" .env
else
  printf '\nPUBLIC_BASE_URL=%s\n' "$URL" >> .env
fi
docker compose up -d backend >/dev/null

# 6) Registrar el webhook (con reintentos por si el túnel aún propaga)
echo "🔗 Registrando webhook en Telegram..."
for intento in 1 2 3 4 5; do
  res="$(docker compose exec -T backend python -m scripts.set_telegram_webhook "$URL" 2>&1 || true)"
  echo "$res"
  echo "$res" | grep -q "'ok': True" && { echo "✅ Webhook registrado."; break; }
  echo "   reintentando en 4 s..."; sleep 4
done
echo "ℹ️  Estado del webhook:"
docker compose exec -T backend python -m scripts.set_telegram_webhook --info

echo
echo "🤖 ¡Listo! Escríbele a tu bot en Telegram (busca su @usuario)."
echo "   Deja ESTA terminal abierta: mantiene el túnel vivo."
echo "   Para terminar: Ctrl+C (luego, opcional: quita PUBLIC_BASE_URL del .env)."
wait "$TUNEL_PID"
