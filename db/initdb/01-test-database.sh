#!/bin/sh
# Crea la base de pruebas de integración (pytest -m pg). El esquema lo aplican las migraciones de alembic.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE DATABASE "${POSTGRES_DB}_test" OWNER "$POSTGRES_USER";
SQL
echo "[initdb] base ${POSTGRES_DB}_test creada"
