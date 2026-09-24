# 01 · Sugerencias de origen y destino

## Objetivo
Cuando alguien escribe un origen o un destino (en el formulario o en el chat), sugerirle los lugares que coinciden. Por ejemplo, `Mei` → **Meissen**, **Hospital Meissen**.

## Estado actual
- `web/js/app.js:41-42` llena un `<datalist>` nativo con `PARADEROS`. No usa alias y no tiene orden de relevancia.
- `Engine.resolver` (`web/js/engine.js:128`) devuelve **un** id o `null`. No distingue los casos ambiguos.

## Requisitos funcionales
1. Buscar por nombre y por alias, sin distinguir mayúsculas ni tildes (`paraiso` = `Paraíso`).
2. Ordenar los resultados por relevancia:
   1. el nombre empieza por el texto;
   2. una palabra del nombre empieza por el texto;
   3. un alias empieza por el texto;
   4. el nombre o un alias contienen el texto.
   A igual relevancia, ordenar por nombre.
3. No repetir lugares y respetar `limit` (por defecto 8, máximo 20).
4. Si el texto tiene menos de 2 caracteres, devolver los lugares populares (tipo `portal`, `salud` y `cable`).
5. `resolve(texto)` devuelve:
   - `exacto` si el nombre o el alias coinciden completos, o si hay un único candidato;
   - `ambiguo` con los candidatos si hay varios;
   - `ninguno` si no hay coincidencias.

## Contrato API
`GET /places/suggest?q=Mei&limit=8`
```json
[
  {"id":"meissen","nombre":"Meissen","tipo":"barrio","zona":"baja","lat":4.588,"lng":-74.149,"via":"nombre"},
  {"id":"hospital","nombre":"Hospital Meissen","tipo":"salud","zona":"baja","lat":4.59,"lng":-74.147,"via":"nombre"}
]
```
`GET /places/resolve?q=juan`
```json
{"estado":"exacto","lugar":{"id":"juanpablo", "...": "..."},"candidatos":[]}
```

## Reglas de dominio
- `normalize()`: minúsculas, NFD sin marcas diacríticas, espacios colapsados y trim.
- `via = "alias"` cuando el lugar entró solo por un alias (por ejemplo, `mercado` → Plaza de mercado Perdomo).

## Casos borde
- Una cadena vacía o solo espacios devuelve los lugares populares.
- Un texto que no coincide con nada devuelve `[]`.
- Un alias que apunta a un id inexistente se ignora.

## Criterios de aceptación
- **Dado** `q=Mei`, **cuando** consulto, **entonces** el primer resultado es `meissen` y `hospital` también aparece.
- **Dado** `q=parai`, **entonces** aparece `paraiso` aunque el nombre tiene tilde.
- **Dado** `q=mercado`, **entonces** aparece `plaza` con `via="alias"`.
- **Dado** `q=me` en `resolve`, **entonces** el estado es `ambiguo`.

## Fuera de alcance
Geocodificación de direcciones libres y paraderos oficiales de ArcGIS como origen o destino.
