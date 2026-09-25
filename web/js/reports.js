/*
 * reports.js — Reporte ciudadano en tiempo real (tipo Waze)
 * ===========================================================================
 * Catálogo de tipos de novedad y cálculo del tramo más cercano a una ubicación.
 * Crear, listar y calificar reportes lo hace SIEMPRE el backend (FastAPI + Postgres,
 * ver api.js): de ahí salen el feed, el mapa y las penalizaciones de las rutas.
 */

const Reports = (() => {
  const TIPOS = {
    derrumbe:    { label: 'Derrumbe / cierre vial', icono: '⛰️', color: '#8e44ad', bloquea: true,  factor: null, vidaMin: 120, sev: 5 },
    bloqueo:     { label: 'Bloqueo / manifestación', icono: '🚧', color: '#e74c3c', bloquea: true,  factor: null, vidaMin: 120, sev: 5 },
    trancon:     { label: 'Trancón fuerte',          icono: '🐢', color: '#e67e22', bloquea: false, factor: 1.8,  vidaMin: 60,  sev: 3 },
    lleno:       { label: 'Muy lleno / no para',     icono: '🧍', color: '#f1c40f', bloquea: false, factor: 1.4,  vidaMin: 45,  sev: 2 },
    sinservicio: { label: 'Sin servicio',            icono: '⛔', color: '#c0392b', bloquea: true,  factor: null, vidaMin: 90,  sev: 4 },
    novedad:     { label: 'Novedad / cambio',        icono: 'ℹ️', color: '#3498db', bloquea: false, factor: 1.2,  vidaMin: 120, sev: 1 },
  };

  function nodo(id) { return Engine.nodoPorId[id]; }

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

  return { TIPOS, RADIO_M: 1500, tramoCercano };
})();

window.Reports = Reports;
