# Base de datos — PostgreSQL 16 con la base principal (muevete) y la de pruebas (muevete_test).
# Los scripts de db/initdb se ejecutan SOLO la primera vez que se crea el volumen de datos.
FROM postgres:16-alpine

ENV POSTGRES_USER=muevete \
    POSTGRES_PASSWORD=muevete \
    POSTGRES_DB=muevete \
    TZ=America/Bogota

COPY initdb/ /docker-entrypoint-initdb.d/

EXPOSE 5432

HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=10 \
    CMD pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" || exit 1
