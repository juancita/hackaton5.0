# Muévete CB 🚡🚌

**Asistente inteligente de movilidad para Ciudad Bolívar** — Hackathon Colombia 5.0
(MinTIC · TEVEANDINA · Universidad Distrital Francisco José de Caldas)

Integra en un solo punto el transporte **formal** (TransMiCable, SITP) y el
**informal** (jeeps, colectivos, rutas veredales) que hoy solo vive en el
"boca a boca", con un **mapa vivo tipo Waze**, **reporte ciudadano en tiempo real**
y un **asistente guiado** con IA. Funciona por **web**, **WhatsApp** y **Telegram**, incluso **sin internet**.

---

## 🎯 El diferenciador
Todos pueden consultar el SITP en Google Maps. **Nadie tiene mapeado el transporte
informal** ni un sistema colaborativo en tiempo real para la ladera. Esa es la brecha
del reto y es nuestro corazón:
1. **Digitalizamos lo informal** (jeeps de Quiba, colectivos a Paraíso, veredales).
2. **Tiempo real tipo Waze**: la comunidad reporta y todos ven al instante.
3. **Reportes con reputación**: cada vecino gana peso cuando sus reportes resultan ciertos; los admin validan. Sin crear cuenta.
4. **Inclusión real**: WhatsApp, Telegram y web con el mismo cerebro (backend hexagonal con puertos por canal).
5. **Offline-first**: en las zonas altas no hay señal; la app igual funciona.

## ✅ Las 5 capacidades del reto → cómo las cubrimos
| # | Capacidad requerida | Implementación |
|---|---------------------|----------------|
| 1 | Integración formal + informal | Grafo multimodal + **datos oficiales en vivo** (`data.js`, `datasources.js`) |
| 2 | Agente de recomendación IA | Asistente guiado/manual con estado + Gemini Flash opcional (`backend/app/domain/assistant.py`) |
| 3 | Visualización geográfica | **Mapa vivo Leaflet tipo Waze** + esquema offline (`app.js`) |
| 4 | Reporte ciudadano en tiempo real | Incidentes con confianza por reputación en Postgres + bus en tiempo real (`reports.py`, `realtime.js`) |
| 5 | Canal de bajo umbral | **PWA + WhatsApp + Telegram** (mismo backend) |

## 🚀 Cómo correr
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
docs/                📚 Documentación del proyecto (empieza por aquí)
  specs/             Specs por funcionalidad (sugerencias, asistente, rutas, mapa, reportes)
  ARQUITECTURA.md    Cómo está montado todo
  FUENTES_DATOS.md   Fuentes oficiales consumidas y cómo extenderlas
  ESTRATEGIA.md      Estrategia atada a la rúbrica
  PITCH.md           Guion del pitch de 5 min
  GUIA_EQUIPO.md     Cómo trabaja el equipo
backend/             API FastAPI hexagonal: rutas, asistente, reportes (Postgres), webhooks
docker-compose.yml   PostgreSQL (+ API opcional)
whatsapp/flujo.md    Diseño del bot de WhatsApp
CONTRIBUTING.md      Flujo de Git para trabajar en paralelo
```

## 👥 Para el equipo
Empieza por **[docs/GUIA_EQUIPO.md](docs/GUIA_EQUIPO.md)** y **[CONTRIBUTING.md](CONTRIBUTING.md)**.
La arquitectura completa está en **[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)**.

## 🏆 Por qué gana
- **Innovación (20%)**: informal + tiempo real Waze + reportes con reputación = combinación no obvia.
- **Viabilidad (20%)**: offline, gama baja, costo casi cero, datos oficiales reales.
- **Pertinencia (25%)**: datos y actores reales de Ciudad Bolívar.
- **Impacto (20%)**: minutos devueltos × miles de personas; escalable y sostenible.
- **Presentación (15%)**: demo en vivo a prueba de fallos (funciona en modo avión).
