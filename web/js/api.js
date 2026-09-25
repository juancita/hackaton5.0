/*
 * api.js — Cliente del backend (FastAPI, ver backend/README.md).
 * ---------------------------------------------------------------------------
 * Cada llamada tiene timeout corto y, si falla, devuelve null para que la app
 * caiga a su lógica local (engine.js / ai.js) para rutas y chat. Los reportes, votos y
 * estrellas existen solo en el servidor (FastAPI + Postgres).
 *
 * Identidad sin cuenta: se genera un client_id una sola vez y se envía en X-Client-Id.
 * Modo admin: la clave se guarda solo en esta pestaña (sessionStorage) y va en X-Admin-Key.
 * URL del backend: localStorage 'muevecb_api', window.MUEVECB_API o, por defecto:
 *  - en desarrollo (web servida en otro puerto, p. ej. 8000): el mismo host en el puerto 8080;
 *  - en producción (Railway) o si la sirve la propia API: el mismo origen.
 */

const API = (() => {
  const porDefecto = !location.protocol.startsWith('http')
    ? 'http://localhost:8080'
    : (location.port && location.port !== '8080')
      ? `${location.protocol}//${location.hostname}:8080`
      : location.origin;
  const base = (() => {
    try { return localStorage.getItem('muevecb_api') || window.MUEVECB_API || porDefecto; }
    catch (e) { return window.MUEVECB_API || porDefecto; }
  })();

  // Identidad: si hay login por celular ('tel:<num>') manda esa (unifica app y Telegram);
  // si no, un id anónimo generado una vez. clientId es mutable: cambia al iniciar/cerrar sesión.
  const KEY_ANON = 'muevecb_client_id';
  const KEY_LOGIN = 'muevecb_login_id';
  const nuevoAnon = () => (window.crypto && crypto.randomUUID
    ? crypto.randomUUID()
    : 'c-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12));
  const anonId = (() => {
    try { let id = localStorage.getItem(KEY_ANON); if (!id) { id = nuevoAnon(); localStorage.setItem(KEY_ANON, id); } return id; }
    catch (e) { return nuevoAnon(); }
  })();
  let clientId = (() => { try { return localStorage.getItem(KEY_LOGIN) || anonId; } catch (e) { return anonId; } })();
  const estaLogueado = () => clientId.startsWith('tel:');

  let adminKey = (() => { try { return sessionStorage.getItem('muevecb_admin') || ''; } catch (e) { return ''; } })();
  function setAdminKey(k) {
    adminKey = k || '';
    try { k ? sessionStorage.setItem('muevecb_admin', k) : sessionStorage.removeItem('muevecb_admin'); } catch (e) {}
  }

  // comoCliente: otra identidad anónima (la sala en vivo simula varios vecinos en un mismo navegador)
  async function llamar(metodo, ruta, body, ms = 3000, comoCliente = null) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), ms);
    const headers = { 'Content-Type': 'application/json', 'X-Client-Id': comoCliente || clientId };
    if (adminKey) headers['X-Admin-Key'] = adminKey;
    try {
      const r = await fetch(base + ruta, {
        method: metodo, headers, body: body ? JSON.stringify(body) : undefined, signal: ctrl.signal,
      });
      const data = await r.json().catch(() => null);
      return { ok: r.ok, status: r.status, data };
    } catch (e) {
      return null; // sin backend: el llamador usa la lógica local
    } finally {
      clearTimeout(t);
    }
  }

  const ok = (r) => (r && r.ok ? r.data : null);

  return {
    base,
    get clientId() { return clientId; },
    get logueado() { return estaLogueado(); },
    get esAdmin() { return !!adminKey; },
    setAdminKey,
    // --- Login por celular (identidad unificada app ↔ Telegram) ---
    login: async (telefono, nombre, modo) => {
      const r = await llamar('POST', '/auth/login', { telefono, nombre, modo }, 6000);
      const data = ok(r);
      if (data && data.client_id) {
        clientId = data.client_id;
        try { localStorage.setItem(KEY_LOGIN, clientId); } catch (e) {}
      }
      return data;
    },
    logout: () => { clientId = anonId; try { localStorage.removeItem(KEY_LOGIN); } catch (e) {} },
    setModo: async (modo) => ok(await llamar('POST', '/me/perfil', { modo }, 4000)),
    // --- Lugares guardados (casa / paradero) ---
    misLugares: async () => ok(await llamar('GET', '/me/lugares', null, 3000)),
    guardarLugar: (body) => llamar('POST', '/me/lugares', body, 4000),
    // --- Conductores / viajes ---
    perfilConductor: (body) => llamar('POST', '/conductores/perfil', body, 4000),
    anunciarViaje: (body) => llamar('POST', '/conductores/viajes', body, 5000),
    misViajes: async () => ok(await llamar('GET', '/conductores/mios', null, 3000)),
    proximos: async (barrio) => ok(await llamar('GET', '/viajes/proximos' + (barrio ? `?barrio=${encodeURIComponent(barrio)}` : ''), null, 3000)),
    reservar: (id, baja_en) => llamar('POST', `/viajes/${encodeURIComponent(id)}/reservar`, baja_en ? { baja_en } : null, 4000),
    cortar: (id, parada_id) => llamar('POST', `/conductores/viajes/${encodeURIComponent(id)}/cortar`, { parada_id }, 4000),
    salir: (id, lat, lng) => llamar('POST', `/conductores/viajes/${encodeURIComponent(id)}/salir`, { lat, lng }, 4000),
    lleno: (id) => llamar('POST', `/conductores/viajes/${encodeURIComponent(id)}/lleno`, null, 4000),
    finalizar: (id) => llamar('POST', `/conductores/viajes/${encodeURIComponent(id)}/finalizar`, null, 4000),
    desvio: (id, nota) => llamar('POST', `/conductores/viajes/${encodeURIComponent(id)}/desvio`, { nota }, 4000),
    horarios: async () => ok(await llamar('GET', '/conductores/horarios', null, 3000)),
    statsRutas: async () => ok(await llamar('GET', '/stats/rutas', null, 3000)),
    // Lectura de una cámara de fotodetección (nivel de congestión 0..1)
    camaraLectura: (id, nivel, vehiculos) => llamar('POST', `/cameras/${encodeURIComponent(id)}/lectura`, { nivel, vehiculos }, 4000),
    salud: async () => !!ok(await llamar('GET', '/health', null, 2000)),
    suggest: async (q) => ok(await llamar('GET', `/places/suggest?q=${encodeURIComponent(q)}&limit=8`, null, 1500)),
    rutas: (origen_id, destino_id, prioridad, modos) => llamar('POST', '/routes', { origen_id, destino_id, prioridad, modos }),
    // El asistente puede tardar más: el LLM interpreta el mensaje y pule la respuesta
    chat: async (texto, ubicacion) => ok(await llamar('POST', '/chat/web', { texto, ...(ubicacion || {}) }, 30000)),
    // Imagen de la ruta que arma el backend (trazado, A/B y ubicación)
    urlMapa: (mapa) => `${base}/mapas/ruta.jpg?${new URLSearchParams({
      r: mapa.ruta, ...(mapa.ubicacion ? { u: mapa.ubicacion.map((v) => v.toFixed(5)).join(',') } : {}) })}`,
    incidentes: async () => ok(await llamar('GET', '/incidents')),
    // { horas } = solo las últimas N horas; { antes } = creados antes de esa fecha ISO (scroll infinito)
    recientes: async ({ horas, antes, limit = 30 } = {}) => ok(await llamar('GET', '/incidents/recent?' + new URLSearchParams({
      limit, ...(horas ? { horas } : {}), ...(antes ? { antes } : {}) }))),
    reportar: (body, comoCliente) => llamar('POST', '/incidents', body, 3000, comoCliente),
    votar: (id, valor, comoCliente) => llamar('POST', `/incidents/${encodeURIComponent(id)}/votos`, { valor }, 3000, comoCliente),
    perfil: async (comoCliente) => ok(await llamar('GET', '/reporters/me', null, 3000, comoCliente)),
    verificar: (id) => llamar('POST', `/admin/incidents/${encodeURIComponent(id)}/verificar`),
    rechazar: (id) => llamar('POST', `/admin/incidents/${encodeURIComponent(id)}/rechazar`),
    limpiar: () => llamar('DELETE', '/admin/incidents'),
  };
})();

window.API = API;
