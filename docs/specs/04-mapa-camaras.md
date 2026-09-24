# 04 · Mapa y cámaras (solo marcadores)

## Objetivo
Quitar la detección por cámaras (Edge AI y simulación) y la pestaña de cámara, y **mantener las cámaras solo como marcadores informativos en el mapa**.

## Estado actual
- Datos: `CAMARAS` en `web/js/data.js:96-101`.
- Lógica: `web/js/edge.js` (simulación y COCO-SSD) emite incidentes con `canal:'edge'`.
- UI:
  - pestaña de cámara en `web/index.html:88-106` y su botón en la línea 114;
  - scripts de TF.js y COCO-SSD en `index.html`;
  - en `web/js/app.js`: la lógica de la pestaña en 242-261, los marcadores en `dibujarCamaras` (141-146) y el canal `edge` en listas y toasts (164, 218, 234);
  - el sufijo "(cámara fotodetección)" en `web/js/reports.js:52`;
  - el botón de cámara del simulador en `web/js/sim.js:126-131` y `web/simulador.html:41`;
  - los estilos en `web/css/styles.css:129-134`.

## Requisitos funcionales
1. **Backend:** las cámaras solo se sirven como datos en `GET /network` (`camaras: [{id, nombre, lat, lng, tramo}]`). No generan incidentes, y el canal `edge` no existe en el dominio.
2. **Frontend:**
   - eliminar `edge.js`, la pestaña de cámara, los scripts de TF.js y COCO-SSD, la entrada `edge.js` de `sw.js`, la lógica de la pestaña, el canal `edge`, el botón del simulador y los estilos `.cam-wrap`, `#cam` y `.cam-stats`;
   - **conservar** `dibujarCamaras` con un popup informativo ("📹 Cámara de fotodetección · {nombre}") y su entrada en la leyenda.
3. **Documentación:** ajustar las menciones a Edge AI en `README.md` y `docs/*.md`.

## Contrato API
Ver `GET /network` en [03](03-rutas.md).

## Casos borde
- Si el mapa usa el respaldo en SVG (sin Leaflet), las cámaras no se dibujan. Es aceptable.
- Los incidentes antiguos en localStorage con `canal:'edge'` se muestran como "web".

## Criterios de aceptación
- En `index.html` no queda ninguna referencia a TF.js, COCO-SSD ni `edge.js`, y la consola no muestra errores.
- El mapa muestra los 4 marcadores 📹 con su popup.
- El simulador sigue funcionando sin el botón de cámara.

## Fuera de alcance
Integrar video real de la Secretaría de Movilidad.
