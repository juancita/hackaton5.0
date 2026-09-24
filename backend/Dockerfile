# Backend — API FastAPI (hexagonal). Solo la API; la web vive en su propio contenedor (web/Dockerfile).
# Al arrancar aplica las migraciones (alembic upgrade head) si STORAGE=postgres y levanta uvicorn.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias primero para aprovechar la caché de capas
COPY requirements.txt .
RUN pip install -r requirements.txt

# Código, migraciones y datos de la red de movilidad
COPY alembic.ini pyproject.toml ./
COPY alembic/ alembic/
COPY app/ app/
COPY data/ data/
COPY scripts/ scripts/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/.cache && chown -R appuser:appuser /app
USER appuser

ENV PORT=8080 \
    STORAGE=postgres
EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8080\")}/health', timeout=3).status == 200 else 1)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--proxy-headers", "--forwarded-allow-ips=*"]
