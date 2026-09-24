# db — imagen de PostgreSQL para Muévete CB

Imagen basada en `postgres:16-alpine` (ver [`Dockerfile`](Dockerfile)) que `docker-compose.yml` usa como servicio `db`.

- **Credenciales por defecto:** usuario, clave y base `muevete` (se sobreescriben con `POSTGRES_*` en el `.env` de la raíz).
- **Zona horaria:** `America/Bogota`.
- **`initdb/`**: scripts que Postgres ejecuta **solo la primera vez** que se crea el volumen de datos (`muevete-cb-pgdata`).
  - `01-test-database.sh` crea la base `muevete_test` para las pruebas de integración (`pytest -m pg`).
- **Esquema:** no está aquí. Lo crean y actualizan las migraciones de Alembic (`backend/alembic/versions/`) cuando arranca el backend.
- **Datos:** viven en el volumen Docker; `docker compose down` los conserva, `docker compose down -v` los borra.

Comandos útiles (desde la raíz del repo):
```bash
docker compose up -d db                                       # solo la BD
docker compose exec db psql -U muevete -d muevete             # consola SQL
docker compose exec -T db pg_dump -U muevete muevete > backup.sql
docker compose exec -T db psql -U muevete -d muevete < backup.sql
```
Guía completa: [docs/DESPLIEGUE.md](../docs/DESPLIEGUE.md).
