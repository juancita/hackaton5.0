# Imagen única: API FastAPI + web estática (servida por la misma API en "/").
# Railway inyecta PORT; en local se usa 8080.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY web/ /web
ENV WEB_DIR=/web
EXPOSE 8080
CMD ["sh", "-c", "if [ \"${STORAGE:-postgres}\" = postgres ]; then alembic upgrade head; fi && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
