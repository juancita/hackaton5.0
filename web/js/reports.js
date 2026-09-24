/*
 * reports.js — Reporte ciudadano en tiempo real (tipo Waze)
 * ===========================================================================
 * Un reporte se convierte en un INCIDENTE geolocalizado que:
 *   1) se propaga a todos vía Realtime (mapa vivo + notificaciones), y
 *   2) PENALIZA o BLOQUEA tramos del grafo → el motor recalcula rutas.
 *
 * El mismo modelo sirve para reportes de personas (WhatsApp/web) y para
 * eventos automáticos de las cámaras edge (ver edge.js): todos son incidentes.
 */

const Reports = (() => {
  const TIPOS = {
    derrumbe:    { label: 'Derrumbe / cierre vial', icono: '⛰️', color: '#8e44ad', bloquea: true,  factor: null, vidaMin: 180, sev: 5 },
    bloqueo:     { label: 'Bloqueo / manifestación', icono: '🚧', color: '#e74c3c', bloquea: true,  factor: null, vidaMin: 120, sev: 5 },
    trancon:     { label: 'Trancón fuerte',          icono: '🐢', color: '#e67e22', bloquea: false, factor: 1.8,  vidaMin: 60,  sev: 3 },
    lleno:       { label: 'Muy lleno / no para',     icono: '🧍', color: '#f1c40f', bloquea: false, factor: 1.4,  vidaMin: 45,  sev: 2 },
    sinservicio: { label: 'Sin servicio',            icono: '⛔', color: '#c0392b', bloquea: true,  factor: null, vidaMin: 90,  sev: 4 },
    novedad:     { label: 'Novedad / cambio',        icono: 'ℹ️', color: '#3498db', bloquea: false, factor: 1.2,  vidaMin: 180, sev: 1 },
  };

  function nodo(id) { return Engine.nodoPorId[id]; }

  // Punto medio del tramo para ubicar el incidente en el mapa
  function geoDeTramo(deId, aId) {
    const a = nodo(deId), b = nodo(aId);
    return { lat: (a.lat + b.lat) / 2, lng: (a.lng + b.lng) / 2 };
  }

  // Crea y publica un incidente a partir de un tramo (de un reporte o cámara)
  function reportar({ tipo, deId, aId, modo, nota, canal, autor }) {
    const t = TIPOS[tipo] || TIPOS.novedad;
    const geo = geoDeTramo(deId, aId);
    return Realtime.publicar({
      tipo, deId, aId, modo,
      nota: nota || '',
      canal: canal || 'web',       // 'whatsapp' | 'web' | 'edge'
      autor: autor || 'Ciudadano',
      lat: geo.lat, lng: geo.lng,
      vidaMin: t.vidaMin,
      sev: t.sev,
    });
  }

  // Traduce incidentes vigentes en penalizaciones para el motor de rutas
  function aplicarAlMotor() {
    const pen = {};
    Realtime.vigentes().forEach((i) => {
      const t = TIPOS[i.tipo]; if (!t) return;
      pen[`${i.deId}|${i.aId}|${i.modo}`] = {
        bloqueado: t.bloquea, factor: t.factor || 1,
        motivo: `${t.icono} ${t.label}${i.nota ? ': ' + i.nota : ''}${i.canal === 'edge' ? ' (cámara fotodetección)' : ''}`,
      };
    });
    Engine.setPenalizaciones(pen);
    return pen;
  }

  // Recalcula penalizaciones automáticamente ante cualquier cambio en tiempo real
  Realtime.suscribir(() => aplicarAlMotor());

  return { TIPOS, reportar, aplicarAlMotor, geoDeTramo };
})();

window.Reports = Reports;
