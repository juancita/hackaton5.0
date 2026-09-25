#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# telegram_guardian.sh — Mantiene vivo el bot de Telegram durante el demo.
#
# El túnel gratuito de Cloudflare se cae al cambiar de red, al suspender el Mac
# o tras varias horas. Este vigilante levanta el túnel (con telegram_demo.sh),
# revisa cada 20 s que la URL pública responda y, si falla 3 veces seguidas,
# abre un túnel nuevo y vuelve a registrar el webhook de Telegram solo.
#
# Uso:  bash scripts/telegram_guardian.sh      (deja esta terminal abierta; Ctrl+C para salir)
# ---------------------------------------------------------------------------
set -uo pipefail
cd "$(dirname "$0")/.."
LOG="$(mktemp -t telegram_demo)"
DEMO_PID=""

detener() {
  [ -n "$DEMO_PID" ] && kill "$DEMO_PID" 2>/dev/null
  pkill -f "^cloudflared tunnel --url" 2>/dev/null || true
}
trap 'detener; echo; echo "👋 Vigilante detenido."; exit 0' INT TERM

while true; do
  detener; sleep 1
  echo "🚀 $(date +%H:%M:%S) Levantando túnel y registrando el bot..."
  : > "$LOG"
  bash scripts/telegram_demo.sh >"$LOG" 2>&1 &
  DEMO_PID=$!
  for _ in $(seq 1 90); do                      # hasta 3 minutos para quedar listo
    grep -qE "¡Listo!|❌" "$LOG" && break
    kill -0 "$DEMO_PID" 2>/dev/null || break
    sleep 2
  done
  if ! grep -q "¡Listo!" "$LOG"; then
    echo "⚠️  No quedó listo; reintento en 10 s. Últimas líneas:"; tail -5 "$LOG"; sleep 10; continue
  fi
  URL="$(grep '^PUBLIC_BASE_URL=' .env | cut -d= -f2-)"
  echo "✅ $(date +%H:%M:%S) Bot en línea: $URL"
  fallos=0
  while kill -0 "$DEMO_PID" 2>/dev/null; do
    sleep 20
    code="$(curl -s -o /dev/null -m 8 -w '%{http_code}' "$URL/health" || true)"
    if [ "$code" = "200" ]; then fallos=0; else fallos=$((fallos + 1)); echo "⚠️  $(date +%H:%M:%S) El túnel no responde ($code), intento $fallos/3"; fi
    [ "$fallos" -ge 3 ] && break
  done
  echo "🔁 $(date +%H:%M:%S) Túnel caído: abro uno nuevo."
done
