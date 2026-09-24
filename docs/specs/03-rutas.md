# 03 · Rutas

## Objetivo
Calcular rutas multimodales (formales e informales) en el backend. Todos los canales usan la misma función, y el formulario "¿a dónde vas?" autocompleta con [01](01-sugerencias-lugares.md).

## Estado actual
- `web/js/engine.js` es el Dijkstra en el cliente, con `opciones()` para 3 prioridades y deduplicación por firma de rutas.
- Formulario en `web/index.html:31-44` y `buscar()` en `web/js/app.js:47`. Usa `<datalist>` para los lugares.

## Requisitos funcionales
1. `RoutingService` es un port fiel de `engine.js`:
   - grafo no dirigido;
   - espera = `freqMin/2`;
   - costo según la prioridad: `rapido` = tiempo; `barato` = `cop + tiempo·5`; `transbordos` = `tiempo + 100`;
   - se agrupan los tramos consecutivos con la misma ruta y modo.
2. `PlanTripUseCase(origen_id, destino_id, prioridad?) -> TripPlan` es el **puerto de dominio** que usan REST y el asistente.
3. Las penalizaciones vienen de los incidentes vigentes ponderados por confianza (ver [05](05-reportes-roles.md)).
4. `recomendada` es el índice de la opción con la prioridad pedida; si no existe, 0.
5. **Frontend:** autocompletado con debounce de 200 ms contra `/places/suggest`. Si la API no responde, se filtra `DB.PARADEROS` en local.

## Contrato API
`POST /routes`
```json
{"origen_id":"meissen","destino_id":"paraiso","prioridad":"rapido"}
```
Respuesta `200` (valores ilustrativos):
```json
{"origen":{"id":"meissen","nombre":"Meissen"},"destino":{"id":"paraiso","nombre":"Paraíso Alto"},
 "opciones":[{"etiqueta":"La más rápida","prioridad":"rapido","totalMin":43,"totalCop":4450,"transbordos":2,
   "usaInformal":true,"alertas":[],"tramos":[{"modo":"sitp","ruta":"C15","desde":"meissen","hasta":"tunal",
   "min":16,"cop":2950,"espera":6,"motivo":null,"paradas":["meissen","tunal"]}]}],
 "recomendada":0,"incidentes_aplicados":[]}
```
Errores:
- `404` si el id del lugar no existe;
- `422` si el origen es igual al destino o la prioridad no es válida;
- `200` con `opciones: []` si no hay camino.

`GET /network` devuelve `{modos, paraderos, tramos, camaras}` para pintar el mapa.

## Casos borde
- Un tramo bloqueado se excluye del grafo. Si esto desconecta al destino, `opciones` sale vacía.
- Los ids se pueden recibir en mayúsculas o con espacios; se normalizan.

## Criterios de aceptación
- Para Meissen→Paraíso, la secuencia de rutas de la opción `rapido` es igual a la de `engine.js`.
- Un trancón verificado en un tramo aumenta `totalMin` de las opciones que lo usan.
- Un incidente con confianza < 0.4 no cambia la respuesta.

## Fuera de alcance
Horarios reales por hora del día, GTFS y ruteo sobre la red vial de OSM.
