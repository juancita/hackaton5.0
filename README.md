# Muévete CB 🚡🚌

**Asistente inteligente de movilidad para Ciudad Bolívar** — Hackathon Colombia 5.0
(MinTIC · TEVEANDINA · Universidad Distrital Francisco José de Caldas)

Integra en un solo punto el transporte **formal** (TransMiCable, SITP) y el
**informal** (jeeps, colectivos, rutas veredales) que hoy solo vive en el
"boca a boca", con un **mapa vivo de la comunidad**, **reporte ciudadano en tiempo real**
y un **asistente guiado** con IA. Funciona por **web**, **WhatsApp** y **Telegram**, incluso **sin internet**.

---

## 🎯 El diferenciador
Todos pueden consultar el SITP en Google Maps. **Nadie tiene mapeado el transporte
informal** ni un sistema colaborativo en tiempo real para la ladera. Esa es la brecha
del reto y es nuestro corazón:
1. **Digitalizamos lo informal** (jeeps de Quiba, colectivos a Paraíso, veredales).
2. **Mapa vivo en tiempo real**: la comunidad reporta y todos ven al instante.
3. **Reportes con reputación**: cada vecino gana peso cuando sus reportes resultan ciertos; los admin validan. Sin crear cuenta.
4. **Inclusión real**: WhatsApp, Telegram y web con el mismo cerebro (backend hexagonal con puertos por canal).
5. **Offline-first**: en las zonas altas no hay señal; la app igual funciona.

## ✅ Las 5 capacidades del reto → cómo las cubrimos
| # | Capacidad requerida | Implementación |
|---|---------------------|----------------|
| 1 | Integración formal + informal | Grafo multimodal + **datos oficiales en vivo** (`data.js`, `datasources.js`) |
| 2 | Agente de recomendación IA | Asistente guiado/manual con estado + Gemini Flash opcional (`backend/app/domain/assistant.py`) |
| 3 | Visualización geográfica | **Mapa vivo Leaflet con reportes de la comunidad** + esquema offline (`app.js`) |
| 4 | Reporte ciudadano en tiempo real | Incidentes con confianza por reputación en Postgres + bus en tiempo real (`reports.py`, `realtime.js`) |
| 5 | Canal de bajo umbral | **PWA + WhatsApp + Telegram** (mismo backend) |

## 🚀 Cómo correr

### Opción A — Todo con Docker (recomendada, cualquier máquina)
```bash
cp .env.example .env              # opcional: ADMIN_API_KEY, ID_SALT, GEMINI_API_KEY…
docker compose up -d --build      # db (Postgres) + backend (API) + web (nginx)
```
- **App:** http://localhost · **Sala en vivo:** http://localhost/simulador.html · **API (Swagger):** http://localhost:8080/docs
- Guía completa (variables, servidor, Railway, operación, problemas): **[docs/DESPLIEGUE.md](docs/DESPLIEGUE.md)**.

### Opción B — Solo el front, sin instalar nada
```bash
cd web
python3 -m http.server 8000     # abrir http://localhost:8000
```
El front funciona solo (offline, sin build). Si además levantas el **backend** en el puerto 8080
(ver [backend/README.md](backend/README.md)), la app lo usa automáticamente para sugerencias,
el asistente con pasos y los reportes guardados en PostgreSQL.
- **App:** http://localhost:8000/index.html
- **Sala en vivo (multiusuario):** http://localhost:8000/simulador.html
- **API (Swagger):** http://localhost:8080/docs

## 🗂️ Estructura
```
web/                 Prototipo funcional (PWA offline)
  index.html         App: Rutas · Asistente · Mapa · Reportar
  simulador.html     Sala en vivo: 3–6 usuarios reportando a la vez
  css/styles.css
  js/data.js         Datos semilla: paraderos, rutas formal+informal, cámaras (solo marcadores)
  js/datasources.js  Fuentes OFICIALES en vivo (ArcGIS TM / datos.gov.co / IDECA)
  js/engine.js       Motor de rutas (grafo multimodal + Dijkstra)
  js/ai.js           Asistente de lenguaje natural (local + LLM opcional)
  js/realtime.js     Sincronización en tiempo real híbrida (Waze)
  js/reports.js      Reportes ciudadanos / incidentes geolocalizados
  js/api.js          Cliente del backend (con respaldo local si no responde)
  js/app.js          Interfaz principal
  js/sim.js          Lógica de la Sala en vivo
  sw.js              Service worker (offline)
  Dockerfile         Imagen de la web (nginx + proxy de la API)
  nginx.conf         Configuración de nginx (estáticos + proxy)
docs/                📚 Documentación del proyecto (empieza por aquí)
  specs/             Specs por funcionalidad (sugerencias, asistente, rutas, mapa, reportes)
  ARQUITECTURA.md    Cómo está montado todo
  DESPLIEGUE.md      Cómo desplegarlo en cualquier máquina (Docker, servidor, Railway)
  FUENTES_DATOS.md   Fuentes oficiales consumidas y cómo extenderlas
  ESTRATEGIA.md      Estrategia atada a la rúbrica
  PITCH.md           Guion del pitch de 5 min
  GUIA_EQUIPO.md     Cómo trabaja el equipo
backend/             API FastAPI hexagonal: rutas, asistente, reportes (Postgres), webhooks
  Dockerfile         Imagen del backend (python 3.12-slim)
  docker-entrypoint.sh  Espera la BD, migra (alembic) y arranca uvicorn
db/                  Imagen de PostgreSQL 16 (crea también la base de pruebas)
docker-compose.yml   Los 3 servicios en contenedores: db (Postgres), backend (API), web (nginx)
.env.example         Variables del compose (puertos, claves); cópialo a .env
Dockerfile           Imagen única API + web que usa Railway (no la usa compose)
railway.json         Configuración del despliegue en Railway
whatsapp/flujo.md    Diseño del bot de WhatsApp
CONTRIBUTING.md      Flujo de Git para trabajar en paralelo
```

## 🐳 Servicios en Docker
| Servicio | Imagen | Qué hace | URL |
|---|---|---|---|
| web | `web/Dockerfile` | nginx sirve la PWA y reenvía la API al backend (mismo origen) | http://localhost (`WEB_PORT`, por defecto 80) |
| backend | `backend/Dockerfile` | FastAPI; espera la BD, aplica migraciones y arranca | http://localhost:8080 · Swagger en `/docs` |
| db | `db/Dockerfile` | PostgreSQL 16 con volumen persistente `muevete-cb-pgdata` | `localhost:5432`, usuario/clave/base `muevete` |

Comandos del día a día: `docker compose ps` · `docker compose logs -f backend` · `docker compose down` (con `-v` borra los datos).
Si el 80 o el 5432 están ocupados, cambia `WEB_PORT` / `PG_PORT` en `.env`. Todo lo demás está en **[docs/DESPLIEGUE.md](docs/DESPLIEGUE.md)**.

## 👥 Para el equipo
Empieza por **[docs/GUIA_EQUIPO.md](docs/GUIA_EQUIPO.md)** y **[CONTRIBUTING.md](CONTRIBUTING.md)**.
La arquitectura completa está en **[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)**.

## 🏆 Por qué gana
- **Innovación (20%)**: informal + mapa vivo en tiempo real + reportes con reputación = combinación no obvia.
- **Viabilidad (20%)**: offline, gama baja, costo casi cero, datos oficiales reales.
- **Pertinencia (25%)**: datos y actores reales de Ciudad Bolívar.
- **Impacto (20%)**: minutos devueltos × miles de personas; escalable y sostenible.
- **Presentación (15%)**: demo en vivo a prueba de fallos (funciona en modo avión).

## 🆕 Módulo de conductores, login por celular y cámaras
- [docs/MODULO_CONDUCTORES.md](docs/MODULO_CONDUCTORES.md) — conductores informales, cupos, "ya salí", desvíos, tendencia de horarios, cámaras de fotodetección.
- [docs/DATOS_Y_PRIVACIDAD.md](docs/DATOS_Y_PRIVACIDAD.md) — Ley 1581 (Habeas Data), qué datos guardamos y cómo.

## 📊 Tablero de movilidad (modo administrador)
Pestaña **Admin** → clave → **Tablero de movilidad**: indicadores, consultas por hora, flujos barrio → salida →
destino final en el mapa, rutas informales (ocupación, cortes), mapa de calor, reportes por canal y el
**análisis de la IA** (Gemini redacta el resumen con las cifras ya calculadas). Es la demo del producto que se
vende a las entidades. Los datos del demo son simulados: `bash scripts/reset_demo.sh` los regenera.
Preguntas difíciles del jurado: [docs/PREGUNTAS_JURADO.md](docs/PREGUNTAS_JURADO.md).
