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

  const clientId = (() => {
    const KEY = 'muevecb_client_id';
    // crypto.randomUUID solo existe en contextos seguros (https / localhost); en la IP de la LAN no.
    const nuevo = () => (window.crypto && crypto.randomUUID
      ? crypto.randomUUID()
      : 'c-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12));
    try {
      let id = localStorage.getItem(KEY);
      if (!id) { id = nuevo(); localStorage.setItem(KEY, id); }
      return id;
    } catch (e) { return nuevo(); }
  })();

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
    clientId,
    get esAdmin() { return !!adminKey; },
    setAdminKey,
    salud: async () => !!ok(await llamar('GET', '/health', null, 2000)),
    suggest: async (q) => ok(await llamar('GET', `/places/suggest?q=${encodeURIComponent(q)}&limit=8`, null, 1500)),
    rutas: (origen_id, destino_id, prioridad, modos) => llamar('POST', '/routes', { origen_id, destino_id, prioridad, modos }),
    // El asistente puede tardar más: el LLM interpreta el mensaje y pule la respuesta
    chat: async (texto) => ok(await llamar('POST', '/chat/web', { texto }, 30000)),
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
