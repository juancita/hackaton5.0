/*
 * reports.js — Reporte ciudadano en tiempo real (tipo Waze)
 * ===========================================================================
 * Un reporte se convierte en un INCIDENTE geolocalizado que:
 *   1) se propaga a todos vía Realtime (mapa vivo + notificaciones), y
 *   2) PENALIZA o BLOQUEA tramos del grafo → el motor recalcula rutas.
 *
 * El mismo modelo sirve para reportes de WhatsApp, Telegram y web.
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
  // lat/lng: dónde está quien reporta (como Waze); si no llega, el punto medio del tramo.
  function reportar({ tipo, deId, aId, modo, nota, canal, autor, lat, lng }) {
    const t = TIPOS[tipo] || TIPOS.novedad;
    const geo = lat != null && lng != null ? { lat, lng } : geoDeTramo(deId, aId);
    return Realtime.publicar({
      tipo, deId, aId, modo,
      nota: nota || '',
      canal: canal || 'web',       // 'whatsapp' | 'telegram' | 'web'
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
        motivo: `${t.icono} ${t.label}${i.nota ? ': ' + i.nota : ''}`,
      };
    });
    Engine.setPenalizaciones(pen);
    return pen;
  }

  // Tramo más cercano a un punto y su distancia en metros (mismo cálculo que el backend)
  function tramoCercano(lat, lng) {
    const k = 111320, kx = k * Math.cos(lat * Math.PI / 180);
    const xy = ([la, ln]) => [(ln - lng) * kx, (la - lat) * k];
    const distSeg = (p, q) => {
      const [ax, ay] = xy(p), [bx, by] = xy(q), dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
      const t = l2 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / l2)) : 0;
      return Math.hypot(ax + t * dx, ay + t * dy);
    };
    let mejor = null;
    DB.TRAMOS.forEach((tr) => {
      const a = nodo(tr.de), b = nodo(tr.a); if (!a || !b) return;
      const pts = tr.geom || [[a.lat, a.lng], [b.lat, b.lng]];
      for (let i = 0; i < pts.length - 1; i++) {
        const d = distSeg(pts[i], pts[i + 1]);
        if (!mejor || d < mejor.dist) mejor = { tramo: tr, dist: d };
      }
    });
    return mejor;
  }

  // Recalcula penalizaciones automáticamente ante cualquier cambio en tiempo real
  Realtime.suscribir(() => aplicarAlMotor());

  return { TIPOS, RADIO_M: 1500, reportar, aplicarAlMotor, geoDeTramo, tramoCercano };
})();

window.Reports = Reports;
