# Fuentes de datos oficiales — Muévete CB

> El reto (IMG_0473) exige **consumir y argumentar** fuentes de datos abiertas.
> Este documento lista cada fuente, cómo la consumimos y cómo extenderla.
> Todas fueron **verificadas en vivo** el 24/09/2026.

## Resumen de estrategia
- **Sistema FORMAL** → datos oficiales abiertos, consumidos **en vivo** (con caché offline).
- **Sistema INFORMAL** (jeeps, colectivos, veredales) → **no existe en ninguna fuente oficial**;
  es nuestra capa comunitaria curada + reporte ciudadano. **Ese es el diferenciador.**

## Fuente primaria (EN VIVO): ArcGIS REST de TransMilenio
Es el servicio GIS oficial que alimenta a Moovit/Google Transit. Devuelve **GeoJSON**,
tiene **CORS habilitado** (`access-control-allow-origin`) y permite filtrar por
**bounding box** de Ciudad Bolívar.

Base: `https://gis.transmilenio.gov.co/arcgis/rest/services`

| Capa | Endpoint (FeatureServer) | Uso |
|------|--------------------------|-----|
| Paraderos Zonales SITP | `Zonal/consulta_paraderos_zonales/FeatureServer/0` | Paraderos formales en el mapa |
| Estaciones Troncales TM | `Troncal/consulta_estaciones_troncales/FeatureServer/0` | Estaciones troncales |
| Rutas Zonales SITP | `Zonal/consulta_rutas_zonales/FeatureServer/0` | (futuro) trazado de rutas |
| Pilonas / Cable | `Troncal/...` , `PILONAS_P` | (futuro) TransMiCable |

**Ejemplo de consulta** (paraderos dentro de Ciudad Bolívar, en GeoJSON WGS84):
```
GET {base}/Zonal/consulta_paraderos_zonales/FeatureServer/0/query
  ?where=1=1
  &geometry=-74.20,4.48,-74.11,4.62
  &geometryType=esriGeometryEnvelope&inSR=4326&outSR=4326
  &spatialRel=esriSpatialRelIntersects
  &outFields=*&f=geojson
```
Devuelve ~400 paraderos con campos: `nombre, via, direccion_bandera, localidad,
zona_sitp, longitud, latitud`. Implementado en [`web/js/datasources.js`](../web/js/datasources.js).

## Fuente de catálogo: Datos Abiertos de Colombia (datos.gov.co / Socrata)
Portal nacional. Muchos datasets de movilidad están **federados** desde el ArcGIS anterior
(por eso los consumimos directo en ArcGIS, que sí es tabular/GeoJSON).

Datasets relevantes (IDs Socrata verificados):
| ID | Nombre |
|----|--------|
| `5vx6-w87b` | Paraderos Zonales del SITP |
| `rcux-r2n5` | Rutas Zonales del SITP |
| `9gxw-u4nv` | Paraderos SITP Bogotá D.C. |
| `nysb-4689` | **GTFS SITP** (para horarios reales — próximo paso) |
| `2eb4-pj4y` | Estaciones Troncales de Transmilenio |
| `cmn3-cbi7` | Rutas Troncales de Transmilenio |
| `34pw-fg5j` | Pilonas Cable |
| `kf4y-mmxf` | Polígonos Infraestructura Transmicable |

API de catálogo (para descubrir más):
```
https://api.us.socrata.com/api/catalog/v1?domains=www.datos.gov.co&q=SITP
```

## Cámaras de fotodetección (Secretaría Distrital de Movilidad)
Ciudad Bolívar cuenta con **cámaras de fotodetección electrónica (fotocomparendos)** ya
instaladas en semáforos y corredores (Av. Villavicencio, Av. Boyacá, Autopista Sur, etc.),
operadas por la Secretaría de Movilidad. En el prototipo se muestran **solo como marcadores de
referencia en el mapa** (`CAMARAS` en [`data.js`](../web/js/data.js) y `GET /network` del backend);
la detección de congestión con visión por computador se retiró (ver [spec 04](specs/04-mapa-camaras.md)).

## Datos Abiertos de Bogotá (Bogotá Abierta) e IDECA
- **IDECA** (`https://www.ideca.gov.co/`): Infraestructura de Datos Espaciales del Distrito;
  cartografía base y capas de referencia del territorio. TransMilenio expone una capa
  `consulta_informacion_basica_IDECA` en su propio ArcGIS.
- **Bogotá Abierta**: portal distrital con equipamientos, movilidad y POI locales.

## Moovit / Google Maps Transit
Referencia de **interoperabilidad**: ambos consumen el **GTFS** oficial del SITP. Nuestra
hoja de ruta es ingerir el GTFS (`nysb-4689`) para horarios exactos, manteniendo la capa
informal encima.

## Cómo agregar/otra fuente
1. Añade la entrada en `FUENTES` dentro de [`datasources.js`](../web/js/datasources.js).
2. Si es ArcGIS FeatureServer → reutiliza `fetchArcgis` (ya filtra por bbox de CB).
3. Si es Socrata tabular → agrega un `fetchSocrata` (`{dominio}/resource/{id}.json?$where=...`).
4. Normaliza al formato `{ id, nombre, lat, lng, tipo, fuente, oficial }`.

## Nota sobre robustez
La app **nunca depende** de que la fuente responda: si falla, usa caché; si no hay caché,
usa la semilla curada. El badge de estado (🟢/🟡/⚪) es honesto ante el jurado.
