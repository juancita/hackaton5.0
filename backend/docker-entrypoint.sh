#!/bin/sh
# Entrypoint del backend: espera la BD, migra y arranca el comando recibido (uvicorn por defecto).
set -e

if [ "${STORAGE:-postgres}" = "postgres" ]; then
  echo "[entrypoint] esperando a PostgreSQL..."
  python - <<'PY'
import os, sys, time
from sqlalchemy import create_engine, text
from app.config import get_settings

url = get_settings().database_url
deadline = time.time() + float(os.environ.get("DB_WAIT_SECONDS", "60"))
while True:
    try:
        with create_engine(url, pool_pre_ping=True).connect() as c:
            c.execute(text("SELECT 1"))
        print("[entrypoint] PostgreSQL disponible")
        break
    except Exception as exc:  # noqa: BLE001
        if time.time() > deadline:
            print(f"[entrypoint] la BD no respondió a tiempo: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(2)
PY
  echo "[entrypoint] aplicando migraciones (alembic upgrade head)"
  alembic upgrade head
else
  echo "[entrypoint] STORAGE=${STORAGE}: sin base de datos (los reportes se pierden al reiniciar)"
fi

# uvicorn no expande $PORT desde CMD en forma exec; lo añadimos aquí
if [ "$1" = "uvicorn" ]; then
  set -- "$@" --port "${PORT:-8080}"
fi

exec "$@"
