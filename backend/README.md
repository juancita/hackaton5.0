# Backend — Muévete CB (FastAPI, hexagonal)

API que concentra la lógica del producto para que **web, Telegram y WhatsApp** usen el mismo cerebro:
- sugerencias de lugares;
- rutas multimodales (formales e informales);
- asistente guiado o manual con Gemini Flash opcional;
- reportes ciudadanos con roles y reputación, guardados en **PostgreSQL**.

Los specs de cada funcionalidad están en [`docs/specs/`](../docs/specs/00-contexto.md).

## Arranque rápido
**Todo en Docker (sin instalar Python):** desde la raíz del repo, `docker compose up -d --build`. Levanta `db`, `backend` y `web`; la API queda en http://localhost:8080 y la web en http://localhost. Detalle en [docs/DESPLIEGUE.md](../docs/DESPLIEGUE.md).

**Desarrollo en local (API con recarga automática):**
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
- **Todo en contenedores:** ver arriba y [docs/DESPLIEGUE.md](../docs/DESPLIEGUE.md).

## Docker (imagen del backend)
| Archivo | Qué hace |
|---|---|
| `Dockerfile` | `python:3.12-slim`; instala `requirements.txt`; copia `app/`, `alembic/`, `data/`, `scripts/`; corre como `appuser` (sin root); healthcheck `GET /health`; expone 8080. |
| `docker-entrypoint.sh` | Si `STORAGE=postgres`: espera a la BD (hasta `DB_WAIT_SECONDS`, 60 s) y aplica `alembic upgrade head`. Luego ejecuta el comando recibido (`uvicorn app.main:app --port $PORT`). |
| `.dockerignore` | Excluye `.venv`, cachés, `.env` y `tests/` de la imagen. |

- Construir y probar solo esta imagen: `docker build -t muevete-cb/backend backend/` y `docker run --rm -p 8080:8080 -e STORAGE=memory muevete-cb/backend`.
- En compose, `DATABASE_URL` apunta al servicio `db` (`postgresql+psycopg://muevete:muevete@db:5432/muevete`); `backend/.env` se carga como extra si existe, pero `STORAGE`, `DATABASE_URL` y `PORT` los fija el compose.
- Nuevas migraciones: crea el archivo en `alembic/versions/`, haz commit y en cada máquina basta `docker compose up -d --build backend`; el entrypoint las aplica al arrancar.
- La imagen **no** incluye la web: en compose la sirve nginx (`web/Dockerfile`). La imagen única API + web es el `Dockerfile` de la raíz (Railway).

## Despliegue en Railway
Un solo servicio sirve la **API y la web** (la web se monta en `/`, la API conserva sus rutas y el front la llama en el mismo origen).
- **Build:** `railway.json` (raíz del repo) indica usar el `Dockerfile` de la raíz. En el servicio, *Root Directory* debe quedar vacío (`/`).
- **Arranque:** el contenedor aplica `alembic upgrade head` y levanta uvicorn en el `PORT` que asigna Railway. Healthcheck: `/health`.
- **Base de datos:** agrega un servicio **PostgreSQL** al proyecto y en las variables de la API pon `DATABASE_URL=${{Postgres.DATABASE_URL}}` (la URL `postgresql://` se convierte sola al driver psycopg).
- **Variables:** `STORAGE=postgres`, `ID_SALT`, `ADMIN_API_KEY`, y opcionalmente `LLM_PROVIDER`/`GEMINI_API_KEY`, `TELEGRAM_*`, `WHATSAPP_*` (ver `.env.example`).
- **Dominio:** *Settings → Networking → Generate Domain*. Con él registra el webhook de Telegram: `python -m scripts.set_telegram_webhook https://<dominio>`.

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
data/network.json  red semilla (fuente de verdad), generada por scripts/build_network.py
alembic/           migraciones
```

## Endpoints
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/places/suggest?q=Mei` | Sugerencias para el autocompletado |
| GET | `/places/resolve?q=` | `exacto` / `ambiguo` / `ninguno` |
| GET | `/network` | Modos, paraderos, tramos y cámaras (solo marcadores) |
| POST | `/routes` | `{origen_id, destino_id, prioridad?}` → `TripPlan` |
| GET | `/mapas/ruta.jpg?r=&u=` | Imagen de la ruta (trazado por modo, A/B, transbordos y ubicación `u=lat,lng`). `r` es el `mapa.ruta` que devuelve el chat |
| POST | `/chat/web` | Asistente para la web (header `X-Client-Id`). Body `{texto, lat?, lng?}` |
| POST | `/webhooks/telegram` | Webhook del bot de Telegram |
| GET/POST | `/webhooks/whatsapp` | Verificación y mensajes de WhatsApp Cloud API |
| GET/POST | `/incidents` | Incidentes vigentes / reportar. Body: `{tipo, lat, lng, nota?}` (como Waze: se asigna al tramo más cercano, ≤1.5 km) o `{tipo, de_id, a_id, modo?, nota?}` |
| POST | `/incidents/{id}/votos` | Confirmar o negar un incidente |
| GET | `/reporters/me` | Reputación y peso de quien consulta |
| POST | `/admin/incidents/{id}/verificar` \| `/rechazar` | Moderación (`X-Admin-Key`) |
| DELETE | `/admin/incidents` | Limpiar incidentes (`X-Admin-Key`) |

## Identidad y roles (sin cuentas)
- **Usuario:** el id viene del canal: `from.id` en Telegram, `wa_id` en WhatsApp y el header `X-Client-Id` en la web (un UUID que guarda el navegador). Se guarda como `sha256(ID_SALT + canal:id)`, así que no queda ningún teléfono en la BD.
- **Admin:** cualquier petición con `X-Admin-Key = ADMIN_API_KEY`. Pesa 1.0 y sus reportes quedan verificados de inmediato.
- **Reputación:** `(aciertos+1)/(aciertos+fallos+2)`. El peso de un usuario es `0.1 + 0.6·rep`. La confianza de un incidente es `1 − Π(1 − w)`. Detalle en el [spec 05](../docs/specs/05-reportes-roles.md).

## LLM (Gemini Flash)
Con `LLM_PROVIDER=gemini` y `GEMINI_API_KEY`, el asistente usa el modelo de `GEMINI_MODEL` (por defecto `gemini-3.5-flash`) para dos cosas:
- **Entender** (`MessageInterpreter`): cuando las reglas no entienden un mensaje («ando por el hospital y voy donde mi tía en el mirador», «nada que baja el carro en Paraíso»), el LLM devuelve en JSON la intención (ruta, reporte, saludo, ayuda, otro), el origen, el destino, la prioridad y el tipo de reporte. El dominio resuelve esos lugares contra el catálogo y calcula la ruta; el LLM nunca inventa rutas ni tiempos.
- **Pulir** (`ResponseRefiner`): las respuestas de ruta y de reporte se reescriben con un tono más natural.
- Si el LLM falla, tarda más de `LLM_TIMEOUT_S` o **cambia alguna cifra**, se sigue con las reglas y el texto original del dominio.
- `GEMINI_THINKING` (`minimal`/`low`/`medium`/`high`) ajusta cuánto razona el modelo; más bajo = más rápido.
- Otro proveedor se integra con clases que implementen `refine(ctx) -> str` e `interpret(ctx) -> Interpretation | None` (ver `adapters/outbound/refiners.py`).

## Canales
- **Telegram:**
  - Registrar el webhook: con `ngrok http 8000` corriendo, `python -m scripts.set_telegram_webhook` (toma la URL de ngrok y usa `TELEGRAM_TOKEN`/`TELEGRAM_WEBHOOK_SECRET` del `.env`). También acepta la URL como argumento, y `--info` / `--delete`.
  - Las opciones rápidas se muestran como teclado.
- **WhatsApp (Meta Cloud API):**
  - URL de callback: `<URL_PUBLICA>/webhooks/whatsapp`, con el verify token `WHATSAPP_VERIFY_TOKEN`.
  - Si configuras `WHATSAPP_APP_SECRET`, se valida la firma de cada petición.
  - Las opciones se envían como lista numerada.
- **Pruebas locales:** para exponer la API usa un túnel (ngrok o cloudflared). Con compose: `ngrok http 8080` y `docker compose exec backend python -m scripts.set_telegram_webhook https://xxxx.ngrok-free.app`.

## Pruebas
```bash
pytest -m "not pg"     # unitarias + API (sin BD)
pytest -m pg           # integración con PostgreSQL (docker compose up -d db); usa su propia base muevete_test (la imagen db/ la crea sola)
```
- Usa `TEST_DATABASE_URL` para apuntar las pruebas de integración a otra base; esas pruebas vacían las tablas.
- La prueba de paridad con `engine.js` necesita `node`; si no está, se omite.
