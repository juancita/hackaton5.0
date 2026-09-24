# Arquitectura técnica — Muévete CB

> Documento para el equipo de desarrollo. Explica cómo está montado todo,
> el flujo de datos y por qué cada decisión ayuda a ganar la rúbrica.

## Visión de 30 segundos
Una **PWA offline-first** (HTML/CSS/JS vainilla) con un **backend FastAPI opcional** que:
1. Consume **datos abiertos oficiales en vivo** (ArcGIS TransMilenio, datos.gov.co, IDECA) y los cachea para offline.
2. Los **cruza con transporte informal** (jeeps, colectivos, veredales) en un grafo multimodal.
3. Recomienda rutas con un **motor local** (Dijkstra) + **capa de IA** para lenguaje natural.
4. Tiene un **mapa vivo tipo Waze** con reportes ciudadanos en **tiempo real**.
5. Pondera los reportes por **reputación** (usuario / admin) y los guarda en PostgreSQL.
6. Funciona por **web** (perfil experto), **WhatsApp** y **Telegram** (asistente guiado paso a paso).

## Principios de diseño (atados a la rúbrica)
- **Offline-first** → viabilidad real en la ladera (zonas altas sin señal).
- **Sin build, sin `npm install`** → cualquier portátil lo corre; cero fricción en el evento.
- **A prueba de fallos** → si cae internet/LLM, el demo sigue funcionando.
- **Datos reales** → pertinencia territorial.

## Diagrama de módulos
```
                         ┌─────────────────────────────────────────┐
                         │                index.html                │
                         │   (Rutas · Asistente · Mapa · Reportar)  │
                         │   api.js → backend si responde           │
                         └───────────────────┬─────────────────────┘
                                             │
        ┌────────────┬──────────────┬────────┴───────┬──────────────┬─────────────┐
        ▼            ▼              ▼                ▼              ▼             ▼
   data.js      datasources.js   engine.js        ai.js        reports.js     api.js
  (semilla:    (fuentes         (grafo multi-    (NLP local,   (incidentes    (backend:
   grafo +      OFICIALES en     modal +          respaldo del  geo + tipos)   sugerencias,
   informal +   vivo + caché     Dijkstra)        asistente)                   chat, reportes;
   cámaras)     + fallback)                                      │             respaldo local)
        │            │              ▲                            │                │
        └────────────┴──────────────┘                            │                │
                                                                 ▼                ▼
                                                            realtime.js  ◄─────────┘
                                                         (bus tiempo real híbrido:
                                                          pub/sub + BroadcastChannel
                                                          + localStorage; adaptador
                                                          de backend opcional)
                                                                 │
                                                                 ▼
                                                          simulador.html
                                                     (Sala en vivo multiusuario)
```

## Flujo de datos clave

### 1) Carga de datos oficiales (`datasources.js`)
```
navigator.onLine? ──sí──► fetch ArcGIS (bbox Ciudad Bolívar, GeoJSON, outSR=4326)
                          └► guarda en localStorage (caché 24h) ──► estado "vivo"
        └──no / falla──► caché disponible? ──sí──► estado "cache"
                                            └no──► semilla (data.js) ──► estado "semilla"
```
El badge superior muestra 🟢 vivo / 🟡 caché / ⚪ semilla. Ver [FUENTES_DATOS.md](FUENTES_DATOS.md).

### 2) Cálculo de rutas (`engine.js`)
- Grafo no dirigido con aristas formales + informales (`TRAMOS` en `data.js`).
- Dijkstra con 3 prioridades: **rápido / barato / menos transbordos**.
- Costo por arista = tiempo + espera (½ de la frecuencia) + penalizaciones por reportes.
- Devuelve opciones deduplicadas y marca `usaInformal` (el diferenciador).

### 3) Tiempo real (`realtime.js`) — HÍBRIDO
- **Demo (garantizado, offline):** `BroadcastChannel` + `localStorage` sincronizan
  pestañas, ventanas y dispositivos en la misma máquina/red. Estado compartido persistente.
- **Producción (opcional):** `Realtime.conectarBackend(enviar, recibir)` engancha un
  WebSocket/Firebase sin tocar el resto. Ver [../backend/README.md](../backend/README.md).
- Un **incidente** = `{ id, tipo, deId, aId, modo, lat, lng, nota, canal, autor, ts, vidaMin, votos }`.

### 4) Reportes ciudadanos (`reports.js`)
- Convierte un reporte ciudadano en incidente geolocalizado y lo publica.
- Traduce incidentes vigentes en **penalizaciones** del grafo → las rutas se recalculan solas.
- Tipos: derrumbe, bloqueo, trancón, lleno, sin servicio, novedad (con severidad y vida útil).

### 5) Backend hexagonal (`backend/`)
- **FastAPI + dominio puro** (`app/domain`): sugerencias de lugares, motor de rutas (port fiel de
  `engine.js`), `PlanTripUseCase` (origen + destino → toda la información), reportes con reputación
  y el asistente con estado (modo guiado o manual).
- **Puertos de entrada** por canal: `/chat/web`, `/webhooks/telegram`, `/webhooks/whatsapp` traducen
  a `InboundMessage`; el dominio responde un `OutboundMessage` completo.
- **Puertos de salida:** `ResponseRefiner` (Gemini Flash o ninguno), repositorios en PostgreSQL
  (Docker) para el feedback, conversaciones en memoria.
- Las cámaras de fotodetección quedan **solo como marcadores** del mapa (la detección se retiró).
- Specs detallados en [`docs/specs/`](specs/00-contexto.md).

### 6) Asistente (`ai.js`)
- **Local (siempre):** interpreta "de X a Y", prioridad y **reportes** en lenguaje natural.
- **LLM (opcional):** si hay endpoint + señal, pule la respuesta con Claude; si falla, cae a local.

## Los dos canales, un cerebro (inclusión)
- **WhatsApp** (Doña Rosa): mismo `engine` + `ai` detrás de un webhook. Ver [../whatsapp/flujo.md](../whatsapp/flujo.md).
- **Web/PWA** (perfil experto): mapa, cámara, más control.
- Ambos publican y leen del **mismo bus de tiempo real** → lo que uno reporta, todos lo ven.

## Cómo correr
```bash
cd web && python3 -m http.server 8000   # http://localhost:8000
```
- App: `index.html` · Sala en vivo: `simulador.html`
- Demo offline: cargar una vez con internet, luego activar **modo avión** y seguir usando.

## Deuda técnica / próximos pasos
- Conectar `Realtime` a un backend real (Firebase Realtime DB es lo más rápido).
- Enriquecer el grafo con horarios GTFS reales (dataset `nysb-4689`).
- Validación comunitaria de rutas informales (flujo JAC).
- Detección de congestión con las cámaras de fotodetección (hoy solo marcadores en el mapa).
