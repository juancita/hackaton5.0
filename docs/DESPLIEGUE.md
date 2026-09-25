# Despliegue — Muévete CB 🐳

> Guía completa para levantar el proyecto en **cualquier máquina** (portátil del equipo, servidor Linux, VPS o nube)
> con Docker. Cubre las tres imágenes, el `docker-compose.yml`, las variables, la operación diaria y los problemas típicos.

## Resumen en 60 segundos
```bash
git clone https://github.com/juancita/hackaton5.0.git
cd hackaton5.0
cp .env.example .env              # ajusta ADMIN_API_KEY, ID_SALT y (opcional) GEMINI_API_KEY
docker compose up -d --build      # construye las 3 imágenes y levanta todo
docker compose ps                 # los 3 servicios deben quedar "healthy"
```
| Servicio | Contenedor | Imagen local | URL en la máquina |
|---|---|---|---|
| Web (PWA + nginx) | `muevete-web` | `muevete-cb/web` | http://localhost (`WEB_PORT`, por defecto 80) |
| Backend (FastAPI) | `muevete-backend` | `muevete-cb/backend` | http://localhost:8080 · Swagger en http://localhost:8080/docs |
| Base de datos (PostgreSQL 16) | `muevete-db` | `muevete-cb/db` | `localhost:5432` (`PG_PORT`), usuario/clave/base `muevete` |

Requisitos: **Docker Desktop** (Windows/Mac) o **Docker Engine 24+ con Compose v2** (Linux). Nada más: ni Python, ni Node, ni Postgres instalados.

---

## 1. Arquitectura de contenedores
```
   navegador / celular                 Telegram · WhatsApp (webhooks)
          │                                        │
          ▼ :80 (WEB_PORT)                         ▼ :8080 (API_PORT)
   ┌──────────────────┐   proxy /health,/routes,  ┌──────────────────┐
   │  web  (nginx)    │   /incidents,/chat,/docs… │ backend (FastAPI)│
   │  PWA estática    │ ────────────────────────▶ │ uvicorn :8080    │
   └──────────────────┘   http://backend:8080     └────────┬─────────┘
                                                            │ DATABASE_URL
                                                            ▼ db:5432
                                                   ┌──────────────────┐
                                                   │ db (PostgreSQL)  │
                                                   │ volumen pgdata   │
                                                   └──────────────────┘
```
- Los tres contenedores comparten la red interna de compose; se resuelven por nombre (`db`, `backend`, `web`).
- **nginx hace proxy de la API** en el mismo origen: el navegador llama `http://localhost/routes` y nginx lo reenvía a `backend:8080`.
  Así el front no necesita conocer el host del backend y no hay problemas de CORS.
- Si la web se publica en un puerto distinto de 80, `web/js/api.js` busca la API en `<mismo host>:8080`; por eso `API_PORT` debe seguir en 8080 en ese caso.
- Orden de arranque garantizado por healthchecks: `db` sano → `backend` migra y arranca → `web`.

### Las tres imágenes
| Imagen | Archivo | Base | Qué hace |
|---|---|---|---|
| backend | [`backend/Dockerfile`](../backend/Dockerfile) | `python:3.12-slim` | Instala `requirements.txt`, copia `app/`, `alembic/`, `data/network.json` y `scripts/`. Corre como usuario `appuser` (sin root). Healthcheck `GET /health`. |
| backend (arranque) | [`backend/docker-entrypoint.sh`](../backend/docker-entrypoint.sh) | — | Espera a Postgres (hasta `DB_WAIT_SECONDS`, 60 s), ejecuta `alembic upgrade head` si `STORAGE=postgres` y lanza uvicorn en `PORT`. |
| web | [`web/Dockerfile`](../web/Dockerfile) + [`web/nginx.conf`](../web/nginx.conf) | `nginx:1.27-alpine` | Sirve `index.html`, `simulador.html`, `css/`, `js/`, `sw.js`, `manifest.webmanifest`. `sw.js` y el manifest sin caché; estáticos con caché de 1 h; gzip. `BACKEND_URL` se inyecta en la plantilla al arrancar. |
| db | [`db/Dockerfile`](../db/Dockerfile) + [`db/initdb/`](../db/initdb) | `postgres:16-alpine` | Usuario/clave/base `muevete`, zona horaria `America/Bogota`. El script `01-test-database.sh` crea `muevete_test` (para `pytest -m pg`) **solo la primera vez** que se crea el volumen. |

El `Dockerfile` de la **raíz** es distinto: es la imagen única (API + web en un solo proceso) que usa **Railway** (`railway.json`). No se usa en compose.

---

## 2. Variables de entorno
Compose lee automáticamente el archivo **`.env` de la raíz** (nunca se sube al repo; `.env.example` sí). Todas tienen valor por defecto: el proyecto arranca aun sin `.env`.

| Variable | Por defecto | Para qué |
|---|---|---|
| `WEB_PORT` | `80` | Puerto publicado de la web |
| `API_PORT` | `8080` | Puerto publicado del backend. Déjalo en 8080 si cambias `WEB_PORT` |
| `PG_PORT` | `5432` | Puerto publicado de Postgres (para DBeaver, `pytest -m pg`, etc.) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `muevete` | Credenciales de la BD. El backend arma `DATABASE_URL` con ellas |
| `ID_SALT` | `cambia-este-salt` | Sal para anonimizar ids de Telegram/WhatsApp/web. **Cámbiala en producción** y no la cambies después (rompería la reputación acumulada) |
| `ADMIN_API_KEY` | vacío | Quien envíe este valor en `X-Admin-Key` es admin (verifica/rechaza/limpia incidentes). Vacío = sin admin |
| `CORS_ORIGINS` | `*` | Orígenes permitidos en la API |
| `PUBLIC_BASE_URL` | vacío | URL pública del backend, para que Telegram/WhatsApp descarguen las imágenes de ruta (`/mapas/ruta.jpg`) |
| `LLM_PROVIDER` | `none` | `gemini` para activar el LLM |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | vacío / `gemini-3.5-flash` | Credencial y modelo de Gemini |
| `TELEGRAM_TOKEN` / `TELEGRAM_WEBHOOK_SECRET` | vacío | Bot de Telegram |
| `WHATSAPP_TOKEN` / `WHATSAPP_PHONE_ID` / `WHATSAPP_VERIFY_TOKEN` / `WHATSAPP_APP_SECRET` | vacío | WhatsApp Cloud API |

Además, si existe **`backend/.env`**, compose se lo pasa al backend (`env_file`, opcional). Sirve para variables finas que no están en la tabla (`GEMINI_FALLBACK_MODEL`, `GEMINI_THINKING`, `LLM_TIMEOUT_S`, `MAP_TILE_URL`, `CONVERSATION_TTL_MIN`…). Las variables de `docker-compose.yml` (`STORAGE`, `DATABASE_URL`, `PORT`) tienen prioridad sobre `backend/.env`.

> **No** pongas `DATABASE_URL=localhost` en `backend/.env` esperando que sirva en Docker: dentro de la red de compose la BD se llama `db`, y compose ya la fija correctamente.

---

## 3. Escenarios de despliegue

### 3.1 Portátil del equipo / demo
```bash
docker compose up -d --build
```
Abre http://localhost. Para probar desde el celular en la misma wifi: `http://IP-DEL-PORTATIL` (la web). La API va por el proxy de nginx, así que no hace falta abrir el 8080.

### 3.2 Servidor Linux / VPS (producción sencilla)
```bash
sudo apt-get install -y docker.io docker-compose-v2      # Ubuntu/Debian
git clone https://github.com/juancita/hackaton5.0.git && cd hackaton5.0
cp .env.example .env
nano .env       # ID_SALT y ADMIN_API_KEY fuertes; POSTGRES_PASSWORD nueva; PUBLIC_BASE_URL=https://tu-dominio
docker compose up -d --build
```
- Pon un **proxy inverso con HTTPS** delante (Caddy, Traefik o nginx del host) apuntando a `localhost:80` (web) y, si expones la API por separado, a `localhost:8080`.
  Con Caddy basta: `tu-dominio.com { reverse_proxy localhost:80 }`. La web ya reenvía la API, así que **un solo dominio sirve todo**, incluidos los webhooks (`https://tu-dominio.com/webhooks/telegram`).
- Si no quieres exponer Postgres al mundo, quita la línea `ports` del servicio `db` o pon `PG_PORT=127.0.0.1:5432`.
- Arranque automático tras reinicio: los servicios tienen `restart: unless-stopped`; basta con que Docker inicie con el sistema.

### 3.3 Railway (PaaS)
Railway usa el `Dockerfile` de la raíz (una sola imagen API + web) y su propio Postgres. Detalle en [backend/README.md → Despliegue en Railway](../backend/README.md#despliegue-en-railway).

### 3.4 Solo la base de datos (desarrollo del backend en local)
```bash
docker compose up -d db
cd backend && pip install -r requirements.txt && alembic upgrade head
uvicorn app.main:app --reload --port 8080
```
Y la web con `cd web && python -m http.server 8000`. El front en el puerto 8000 busca la API en `localhost:8080`.

### 3.5 Backend sin base de datos (demo rápida)
`STORAGE=memory` hace que la API funcione sin Postgres (los reportes se pierden al reiniciar). En compose:
```bash
docker compose run --rm -e STORAGE=memory -p 8080:8080 --no-deps backend
```

---

## 4. Canales externos (Telegram / WhatsApp)
Ambos necesitan una **URL pública HTTPS** hacia el backend (dominio propio con proxy inverso, Railway o un túnel para pruebas).

### 4.1 Telegram para el demo (un comando) ⭐
`scripts/telegram_demo.sh` automatiza todo con **cloudflared** (túnel HTTPS gratis, sin cuenta):
```bash
brew install cloudflared                         # una sola vez
# pon TELEGRAM_TOKEN (de @BotFather) y, opcional, TELEGRAM_WEBHOOK_SECRET en .env
bash scripts/telegram_demo.sh                    # abre el túnel y registra el webhook
```
El script: levanta los servicios, abre el túnel al backend (:8080), **espera a que sea enrutable**,
fija `PUBLIC_BASE_URL` (para que Telegram descargue las imágenes de ruta), registra el webhook
**con reintentos** y deja el túnel abierto. **Mantén esa terminal abierta durante el demo.**

> La URL de `trycloudflare.com` es temporal: cambia cada vez que reinicias el script. Para una URL
> fija usa Railway (sección 3.3) o un dominio con proxy inverso.
>
> Si Telegram responde `Failed to resolve host`, es que el webhook se registró antes de que el
> túnel propagara: el script ya reintenta; si lo haces a mano, espera a que `curl $URL/health` dé 200.

### 4.2 A mano / producción
1. Pon `TELEGRAM_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` (y `PUBLIC_BASE_URL=https://tu-dominio`) en `.env` y `docker compose up -d backend`.
2. Registra el webhook desde el contenedor:
   ```bash
   docker compose exec backend python -m scripts.set_telegram_webhook https://tu-dominio
   docker compose exec backend python -m scripts.set_telegram_webhook --info
   ```
3. WhatsApp: en Meta → Webhooks pon `https://tu-dominio/webhooks/whatsapp` y el `WHATSAPP_VERIFY_TOKEN`.

---

## 5. Operación diaria
| Tarea | Comando |
|---|---|
| Ver estado y salud | `docker compose ps` |
| Logs de la API (en vivo) | `docker compose logs -f backend` |
| Logs de todo | `docker compose logs -f` |
| Actualizar a la última versión del repo | `git pull && docker compose up -d --build` (las migraciones nuevas se aplican solas al arrancar) |
| Reiniciar un servicio | `docker compose restart backend` |
| Apagar (conserva los datos) | `docker compose down` |
| Apagar y **borrar los datos** de Postgres | `docker compose down -v` |
| Entrar a la BD | `docker compose exec db psql -U muevete -d muevete` |
| Copia de seguridad | `docker compose exec -T db pg_dump -U muevete muevete > backup-$(date +%F).sql` |
| Restaurar | `docker compose exec -T db psql -U muevete -d muevete < backup-2026-09-24.sql` |
| Shell en el backend | `docker compose exec backend sh` |
| Pruebas de integración contra la BD del compose | `cd backend && pytest -m pg` (usa `muevete_test`, que la imagen crea sola) |
| Reconstruir una sola imagen | `docker compose build web` |
| Solo cambió la web (HTML/CSS/JS) | `docker compose up -d --build web` (segundos: nginx no compila nada) |

Los datos viven en el volumen Docker **`muevete-cb-pgdata`**. Sobrevive a `down`, `build` y reinicios; solo `down -v` o `docker volume rm` lo borra.

---

## 6. Verificación tras desplegar
```bash
curl http://localhost:8080/health          # {"ok":true}  ← API directa
curl http://localhost/health               # {"ok":true}  ← API a través de nginx
curl -s http://localhost/ | head -5        # HTML de la PWA
curl "http://localhost/places/suggest?q=portal&limit=2"
docker compose exec db psql -U muevete -d muevete -c "\dt"   # alembic_version, reporters, incidents, reports, votes
```
Y en el navegador: la app en http://localhost debe mostrar el indicador de **backend en línea** y permitir crear un reporte que sobreviva a recargar la página.

---

## 7. Problemas frecuentes
| Síntoma | Causa y solución |
|---|---|
| `Bind for 0.0.0.0:5432 failed: port is already allocated` | Hay otro Postgres (o un contenedor viejo, p. ej. `hackaton50-db-1` del compose anterior) en ese puerto. `docker ps` para verlo; `docker stop <nombre>` o cambia `PG_PORT=5433` en `.env`. |
| Lo mismo con el puerto 80 (IIS, Apache, otro nginx) | `WEB_PORT=3000` en `.env`. La API sigue en 8080 y el front la encuentra. |
| El backend reinicia en bucle y el log dice `la BD no respondió a tiempo` | La BD no arrancó (mira `docker compose logs db`) o cambiaste `POSTGRES_*` después de crear el volumen: las credenciales viven en el volumen, no en el `.env`. Vuelve a las anteriores o `docker compose down -v`. |
| `exec /usr/local/bin/docker-entrypoint.sh: no such file or directory` | El script llegó con finales de línea CRLF (Windows). `.gitattributes` ya fuerza LF; si un editor lo convirtió, guárdalo como LF y `docker compose build backend`. |
| La web carga pero dice que el backend está fuera de línea | `docker compose ps`: ¿`muevete-backend` está `healthy`? Si publicaste la web en otro puerto, ¿está el 8080 publicado? `curl http://localhost/health` debe responder. |
| Cambié `index.html`/`app.js` y no se ve | Reconstruye la imagen (`docker compose up -d --build web`) y en el navegador cierra las pestañas: el service worker cachea la app; sube la versión de `CACHE` en `web/sw.js` al publicar cambios. |
| `pytest -m pg` no encuentra `muevete_test` | El volumen se creó con una imagen anterior a `db/initdb`. Créala a mano: `docker compose exec db psql -U muevete -c "CREATE DATABASE muevete_test"`. |
| Telegram no llega | El webhook debe apuntar a una URL **HTTPS pública** y `TELEGRAM_WEBHOOK_SECRET` debe coincidir. `--info` muestra el último error que vio Telegram. |
| Docker Desktop en Windows: `docker compose` lento la primera vez | Está descargando las imágenes base (`python:3.12-slim`, `nginx:1.27-alpine`, `postgres:16-alpine`); las siguientes construcciones usan caché. |

---

## 8. Seguridad mínima antes de publicar
- [ ] `ID_SALT` largo y aleatorio (`openssl rand -hex 32`). No lo cambies después.
- [ ] `ADMIN_API_KEY` fuerte; solo la conoce quien modera.
- [ ] `POSTGRES_PASSWORD` distinta de `muevete` y Postgres **no** publicado a internet.
- [ ] HTTPS con proxy inverso; `CORS_ORIGINS` restringido a tu dominio si la API se expone aparte.
- [ ] `.env` y `backend/.env` fuera del repo (ya están en `.gitignore`). Nunca commitees tokens.
- [ ] Copia de seguridad programada (`pg_dump`, sección 5).

## Checklist de despliegue
- [ ] `cp .env.example .env` y claves ajustadas.
- [ ] `docker compose up -d --build` → `docker compose ps` muestra los 3 servicios `healthy`.
- [ ] `curl http://localhost/health` responde `{"ok":true}`.
- [ ] La web crea un reporte y sobrevive a recargar.
- [ ] (Opcional) Gemini probado: `LLM_PROVIDER=gemini` y una pregunta en el asistente.
- [ ] (Opcional) Webhook de Telegram registrado y `--info` sin errores.
