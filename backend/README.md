# Backend — Muévete CB (FastAPI, hexagonal)

API que concentra la lógica del producto para que **web, Telegram y WhatsApp** usen el mismo cerebro:
- sugerencias de lugares;
- rutas multimodales (formales e informales);
- asistente guiado o manual con Gemini Flash opcional;
- reportes ciudadanos con roles y reputación, guardados en **PostgreSQL**.

Los specs de cada funcionalidad están en [`docs/specs/`](../docs/specs/00-contexto.md).

## Arranque rápido
```bash
# 1) Base de datos (desde la raíz del repo)
docker compose up -d db

# 2) Dependencias y esquema
cd backend
python -m venv .venv && .venv/Scripts/activate      # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                 # ajusta ADMIN_API_KEY, ID_SALT, GEMINI_API_KEY…
alembic upgrade head

# 3) API en el puerto 8080 (el front lo busca ahí; el 8000 es para web/)
uvicorn app.main:app --reload --port 8080            # Swagger: http://localhost:8080/docs
```
- **Sin Docker:** con `STORAGE=memory` en `.env` la API funciona sin base de datos, pero los reportes se pierden al reiniciar.
- **Todo en contenedores:** `docker compose --profile api up -d --build` levanta la BD y la API (migra sola).

## Arquitectura
```
app/
  domain/        Lógica pura, sin FastAPI ni SQL
    places.py      sugerencias y resolución de lugares ("Mei" → Meissen)
    routing.py     motor Dijkstra (port fiel de web/js/engine.js; hay una prueba de paridad)
    trip.py        PlanTripUseCase: origen + destino → TripPlan con toda la información
    reports.py     roles, reputación, confianza, penalizaciones
    assistant.py   máquina de estados guiada/manual, independiente del canal
  ports/         Protocolos de entrada (ChatPort, TripPort, ReportPort) y de salida
                 (ResponseRefiner, repositorios, ConversationStore)
  adapters/
    inbound/       http_api.py (REST), chat_channels.py (web, Telegram, WhatsApp)
    outbound/      pg/ (PostgreSQL), memory_repos.py, refiners.py (Gemini / Noop), json_catalog.py
  container.py   conecta los adaptadores según .env
data/network.json  red semilla exportada de web/js/data.js
alembic/           migraciones
```

## Endpoints
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/places/suggest?q=Mei` | Sugerencias para el autocompletado |
| GET | `/places/resolve?q=` | `exacto` / `ambiguo` / `ninguno` |
| GET | `/network` | Modos, paraderos, tramos y cámaras (solo marcadores) |
| POST | `/routes` | `{origen_id, destino_id, prioridad?}` → `TripPlan` |
| POST | `/chat/web` | Asistente para la web (header `X-Client-Id`) |
| POST | `/webhooks/telegram` | Webhook del bot de Telegram |
| GET/POST | `/webhooks/whatsapp` | Verificación y mensajes de WhatsApp Cloud API |
| GET/POST | `/incidents` | Incidentes vigentes / reportar |
| POST | `/incidents/{id}/votos` | Confirmar o negar un incidente |
| GET | `/reporters/me` | Reputación y peso de quien consulta |
| POST | `/admin/incidents/{id}/verificar` \| `/rechazar` | Moderación (`X-Admin-Key`) |
| DELETE | `/admin/incidents` | Limpiar incidentes (`X-Admin-Key`) |

## Identidad y roles (sin cuentas)
- **Usuario:** el id viene del canal: `from.id` en Telegram, `wa_id` en WhatsApp y el header `X-Client-Id` en la web (un UUID que guarda el navegador). Se guarda como `sha256(ID_SALT + canal:id)`, así que no queda ningún teléfono en la BD.
- **Admin:** cualquier petición con `X-Admin-Key = ADMIN_API_KEY`. Pesa 1.0 y sus reportes quedan verificados de inmediato.
- **Reputación:** `(aciertos+1)/(aciertos+fallos+2)`. El peso de un usuario es `0.1 + 0.6·rep`. La confianza de un incidente es `1 − Π(1 − w)`. Detalle en el [spec 05](../docs/specs/05-reportes-roles.md).

## LLM (Gemini Flash)
Con `LLM_PROVIDER=gemini` y `GEMINI_API_KEY`, las respuestas de ruta y de reporte se pulen con el modelo de `GEMINI_MODEL`.
- Si el LLM falla, tarda más de `LLM_TIMEOUT_S` o **cambia alguna cifra**, se envía el texto original del dominio.
- Otro proveedor se integra con una clase que implemente `refine(ctx) -> str` (ver `adapters/outbound/refiners.py`).

## Canales
- **Telegram:**
  - Registrar el webhook: `https://api.telegram.org/bot<TOKEN>/setWebhook?url=<URL_PUBLICA>/webhooks/telegram&secret_token=<TELEGRAM_WEBHOOK_SECRET>`.
  - Las opciones rápidas se muestran como teclado.
- **WhatsApp (Meta Cloud API):**
  - URL de callback: `<URL_PUBLICA>/webhooks/whatsapp`, con el verify token `WHATSAPP_VERIFY_TOKEN`.
  - Si configuras `WHATSAPP_APP_SECRET`, se valida la firma de cada petición.
  - Las opciones se envían como lista numerada.
- **Pruebas locales:** para exponer la API usa un túnel (ngrok o cloudflared).

## Pruebas
```bash
pytest -m "not pg"     # unitarias + API (sin BD)
pytest -m pg           # integración con PostgreSQL (docker compose up -d db && alembic upgrade head)
```
- Usa `TEST_DATABASE_URL` para apuntar las pruebas de integración a otra base; esas pruebas vacían las tablas.
- La prueba de paridad con `engine.js` necesita `node`; si no está, se omite.
