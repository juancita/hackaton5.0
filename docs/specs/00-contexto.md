# 00 · Contexto y arquitectura objetivo

## Estado actual
Muévete CB es una PWA estática en JS plano (`web/`). No hay un backend real: `backend/README.md` solo describe un diseño.

| Módulo | Archivo | Qué hace hoy |
|---|---|---|
| Datos semilla | `web/js/data.js` | `MODOS`, `PARADEROS` (17), `TRAMOS`, `CAMARAS` (4), `ALIAS` |
| Motor de rutas | `web/js/engine.js` | Dijkstra con 3 prioridades (`rapido`, `barato`, `transbordos`) y penalizaciones |
| Asistente | `web/js/ai.js` | Regex sin estado. Tiene un stub de LLM (Claude) desactivado |
| Reportes | `web/js/reports.js`, `web/js/realtime.js` | Incidentes en localStorage y BroadcastChannel. Los votos no tienen efecto |
| Cámaras | `web/js/edge.js` | Simulación y COCO-SSD con la webcam |
| UI | `web/js/app.js`, `web/index.html` | Pestañas plan / chat / mapa / reportar / cámara |

Problemas:
- Todo vive en el navegador.
- El chat no recuerda la conversación.
- Cualquiera puede borrar reportes.
- Ningún reporte pesa más que otro.

## Arquitectura objetivo (hexagonal)
```
          Adaptadores de ENTRADA                     Adaptadores de SALIDA
  ┌───────────────┐                             ┌──────────────────────────┐
  │ REST (FastAPI)│──┐                       ┌─▶│ GeminiRefiner / Noop     │ ResponseRefiner
  │ /chat/web     │──┤   ┌───────────────┐   ├─▶│ PgIncidentRepository     │ IncidentRepository
  │ Telegram hook │──┼──▶│    DOMINIO    │───┼─▶│ PgReporterRepository     │ ReporterRepository
  │ WhatsApp hook │──┘   │ PlaceService  │   ├─▶│ MemoryConversationStore  │ ConversationStore
  └───────────────┘      │ RoutingService│   └─▶│ JsonCatalog              │ NetworkCatalog
     ChatPort /          │ PlanTrip      │      └──────────────────────────┘
     TripPort /          │ ReportService │               │
     ReportPort          │ Assistant     │          PostgreSQL (Docker)
                         └───────────────┘
```
- El **dominio** no conoce el canal, ni la base de datos, ni el LLM.
- Cada canal traduce su payload a `InboundMessage` y muestra el `OutboundMessage` como pueda.
- El puerto de dominio central es `PlanTripUseCase(origen, destino, prioridad) -> TripPlan`: se entra con un punto de entrada y un punto de salida, y se recibe toda la información.

## Infraestructura
Tres contenedores orquestados por `docker-compose.yml`: `web` (nginx: PWA + proxy de la API), `backend` (FastAPI, aplica migraciones al arrancar) y `db` (PostgreSQL 16 con volumen persistente). Guía en [../DESPLIEGUE.md](../DESPLIEGUE.md).

## Glosario
- **Paradero / lugar:** un nodo del grafo, como un barrio, una estación o un punto de interés.
- **Tramo:** una arista entre dos paraderos con un modo de transporte (formal o informal).
- **Incidente:** una afectación vigente sobre un tramo (trancón, derrumbe…). Se forma con uno o más reportes.
- **Reporte:** la señal de un reportero sobre un incidente, con un peso según su rol y su reputación.
- **Reportero:** una identidad anónima derivada del canal (Telegram, WhatsApp o web). No se crea cuenta.
- **Canal:** `web`, `telegram` o `whatsapp`.

## Índice de specs
1. [Sugerencias de lugares](01-sugerencias-lugares.md)
2. [Asistente](02-asistente.md)
3. [Rutas](03-rutas.md)
4. [Mapa y cámaras](04-mapa-camaras.md)
5. [Reportes y roles](05-reportes-roles.md)
