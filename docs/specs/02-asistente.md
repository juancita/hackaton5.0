# 02 · Asistente conversacional

## Objetivo
Un asistente que:
- mantiene el hilo de la conversación;
- ofrece una **experiencia guiada** (un paso por mensaje) o **manual** (texto libre);
- pule sus respuestas con un LLM (Gemini Flash) intercambiable;
- funciona igual desde web, Telegram o WhatsApp.

## Estado actual
- `web/js/ai.js:87` `responder()` no tiene estado. Si falta el origen pregunta "¿Desde dónde sales?", pero la respuesta siguiente no se enlaza con esa pregunta.
- `web/js/ai.js:15` tiene un LLM desactivado (`claude-sonnet-5`, sin endpoint).
- Solo existe el chat web. WhatsApp está simulado y Telegram no existe.

## Requisitos funcionales
### R1 · Estado por conversación
- La clave es `(canal, user_id)`. El estado es `{modo, paso, origen_id, destino_id, prioridad, candidatos[], opciones[], updated_at}`. `opciones` son las últimas opciones mostradas: a ellas se refiere un botón, un número o el texto de la opción.
- El TTL es de 30 min sin actividad; pasado ese tiempo, el estado vuelve a `INICIO`.

### R2 · Máquina de estados
```
INICIO ──(🧭 Ruta guiada)──▶ PASO_ORIGEN ─▶ PASO_DESTINO ─▶ PASO_PRIORIDAD ─▶ RESULTADO
   │                              ▲ ambiguo: lista numerada, responde el # o el nombre
   ├──(✍️ Escribir mi viaje)──▶ MANUAL  (texto libre; pregunta solo lo que falta)
   └──(⚠️ Reportar novedad)──▶ REPORTE (texto libre con qué pasa y dónde) ─▶ INICIO
RESULTADO ─▶ 🔁 Buscar otra ruta → PASO_ORIGEN/MANUAL · 🔀 Ver alternativas · ⚠️ Reportar novedad · 🏠 Menú principal
Todos los pasos de una búsqueda llevan ✖️ Cancelar → INICIO
```
- **INICIO (menú):** "¿Qué quieres hacer? Elige una opción 👇" con las tres opciones y una línea que explica cada una. Si el primer mensaje ya trae una ruta completa ("de Meissen a Paraíso"), se pasa directo a manual y se responde con la ruta.
- **Paso 1:** "¿Desde dónde sales?" · **Paso 2:** "¿A dónde te diriges?" · **Paso 3:** "¿Qué es lo más importante en este viaje?" ⚡ Llegar rápido · 💰 Lo más barato · 🔄 Menos transbordos.
- **Preguntas cerradas (INICIO, paso 3, RESULTADO):** solo valen sus opciones (botón, número o texto de la opción) y los comandos globales. Si no, se responde "No entendí esa respuesta 🙈 Por favor toca una de las opciones…", se recuerda que se puede cancelar y se repite la pregunta. Excepción: en INICIO y RESULTADO, un viaje o un reporte escrito ("de Lucero a Paraíso", "hay un derrumbe en Paraíso") se atiende directamente.
- **RESULTADO:** "¿Qué quieres hacer ahora? Elige una opción 👇". "Ver alternativas" solo aparece si hay más de una opción de ruta.
- En cada paso de lugar se usa `PlaceService.resolve()`:
  - `exacto`: se avanza al paso siguiente;
  - `ambiguo`: se muestran hasta 5 candidatos numerados y se guardan en `candidatos`;
  - `ninguno`: "No reconozco ese lugar" más los populares.
- Si el origen es igual al destino, se vuelve a pedir el destino.
- **MANUAL:** portar `interpretar()` (`de X a Y`, `voy a Y`, `estoy en X`, prioridad por palabras clave). Lo que falte se pregunta, y lo que ya se tiene se conserva.

### R3 · Comandos globales, válidos en cualquier paso
`cancelar` / `salir` / ✖️ Cancelar → "Listo, cancelé la búsqueda" + INICIO · `menu` / `reiniciar` / `inicio` / 🏠 Menú principal → INICIO · `guiada` · `manual` · `ayuda`.

### R4 · Reportes en cualquier momento
Si el texto es un reporte (`detectarReporte`, `web/js/ai.js:73`), se registra con `ReportService` usando la identidad del canal. Se responde confirmando el registro **y se conserva el paso** en el que iba el usuario (se le recuerda la pregunta pendiente).

### R4b · Últimos incidentes
📋 Últimos incidentes (menú) o `incidentes` / `novedades`: lista los 10 más recientes (sin los rechazados) con tipo, tramo, hace cuánto y estado (✅ verificado · 🟠 activo con % de confianza · ⚪ ya pasó). Luego vuelve al menú.

### R4c · Ubicación y mapa de la ruta
- **Ubicación:** 📍 Usar mi ubicación aparece al pedir el origen (Telegram la pide con `request_location`; en la web usa la geolocalización del navegador; en WhatsApp se comparte con 📎). Si el paradero más cercano está a ≤ 2.5 km, ese es el origen y se salta al destino; si no, se guarda pero se sigue pidiendo el origen. La ubicación se conserva al cancelar y sale en el mapa.
- **Mapa:** el resultado trae `mapa {ruta, ubicacion?, google_maps}`. `ruta` codifica los tramos recorridos (`<origen>:<i>.<j>…`, índices de `network.tramos`) y `GET /mapas/ruta.jpg?r=<ruta>&u=<lat,lng>` dibuja la imagen sobre OpenStreetMap: trazado real por modo (informal punteado), A, B, transbordos, "Estás aquí" y leyenda. `google_maps` es un enlace de direcciones que pasa por los transbordos (y sale de la ubicación si está a < 5 km).
- En el resultado, si aún no hay ubicación, se ofrece 📍 Marcar mi ubicación; al recibirla se reenvía el resultado con el mapa actualizado.

### R5 · Pulido con LLM (puerto universal)
- `ResponseRefiner.refine(RefineContext) -> str`, con `RefineContext {mensaje_usuario, texto_base, hechos (dict), canal}`.
- `GeminiRefiner` usa el SDK `google-genai`, con el modelo tomado de `GEMINI_MODEL` (Flash).
  - Instrucción: "No cambies cifras, nombres de rutas, tiempos ni precios. Español colombiano, cálido y breve. Sin markdown si el canal es WhatsApp o Telegram."
  - Timeout de 4 s. Si falla, da error o devuelve vacío, se usa `texto_base`.
- Solo se pule cuando hay contenido que explicar (resultado de ruta o reporte). Las preguntas de los pasos no se pulen, para que sean deterministas y rápidas.
- Con `LLM_PROVIDER=none` se usa `NoopRefiner`. Otros proveedores (Claude, OpenAI…) se agregan escribiendo un adaptador nuevo.

### R6 · Puertos de entrada por canal
`ChatPort.handle(InboundMessage) -> OutboundMessage`.
- `InboundMessage {canal, user_id, texto, nombre?, ubicacion?: (lat, lng)}`.
- `OutboundMessage {texto, texto_base, opciones_rapidas[{id,label}], paso, modo, plan?: TripPlan, reporte?: IncidentView, mapa?: {ruta, ubicacion?, google_maps}}`. Siempre lleva toda la información.

Adaptadores:
| Canal | Endpoint | Identidad | Render |
|---|---|---|---|
| Web | `POST /chat/web` | header `X-Client-Id` | Devuelve el `OutboundMessage` completo; la web muestra la imagen del mapa y el enlace |
| Telegram | `POST /webhooks/telegram` | `message.from.id` | Responde en el cuerpo del webhook (sin llamadas salientes): `sendMessage` + teclado, o `sendPhoto` con el mapa y el enlace a Google Maps como pie de foto (HTML). Si el texto pasa de 1024 caracteres, `sendMessage` con el mapa como vista previa grande. La imagen se genera antes de responder; si falla, sale solo el texto |
| WhatsApp | `GET/POST /webhooks/whatsapp` | `contacts[0].wa_id` | Imagen del mapa + texto con el enlace y la lista numerada (Cloud API) |

## Contrato API (web)
`POST /chat/web` con el header `X-Client-Id: 5b2c…` y body `{"texto":"hola"}`
```json
{"texto":"¡Hola! Soy tu asistente…","texto_base":"…","paso":"inicio","modo":null,
 "opciones_rapidas":[{"id":"1","label":"Guiada"},{"id":"2","label":"Manual"}],"plan":null,"reporte":null}
```

## Casos borde
- Un número fuera de rango al elegir un candidato se trata como texto y se vuelve a resolver.
- Si se reciben mensajes vacíos, stickers o audio por webhook, se responde "Por ahora solo entiendo texto".
- Los updates de Telegram sin `message.text` se ignoran con 200.
- La verificación de WhatsApp (`hub.verify_token`) debe coincidir con `WHATSAPP_VERIFY_TOKEN`; si no coincide, se responde 403.

## Criterios de aceptación
- **Flujo guiado:** `hola` → `1` → `Mei` (ambiguo) → `1` (Meissen) → `paraiso` → `2`. El resultado es una ruta Meissen→Paraíso con prioridad barato.
- **Flujo manual:** `manual` → `voy a paraíso` → pregunta el origen → `meissen` → ruta, sin volver a pedir el destino.
- **Reporte a mitad del flujo:** en el paso 2 escribo `reporto trancón en perdomo`. Se registra y me vuelve a preguntar "¿A dónde te diriges?".
- Si el refiner lanza una excepción, `texto == texto_base`.
- El mismo mensaje por Telegram o por web produce el mismo `texto_base`.

## Fuera de alcance
Audio y voz, imágenes, persistir las conversaciones en la BD (quedan en memoria), y plantillas de WhatsApp aprobadas por Meta.
