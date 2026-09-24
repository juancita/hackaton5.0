/*
 * api.js — Cliente del backend (FastAPI, ver backend/README.md).
 * ---------------------------------------------------------------------------
 * Cada llamada tiene timeout corto y, si falla, devuelve null para que la app
 * caiga a su lógica local (engine.js / ai.js / realtime.js). El demo no se cae sin red.
 *
 * Identidad sin cuenta: se genera un client_id una sola vez y se envía en X-Client-Id.
 * Modo admin: la clave se guarda solo en esta pestaña (sessionStorage) y va en X-Admin-Key.
 * URL del backend: localStorage 'muevecb_api', window.MUEVECB_API o, por defecto, el mismo
 * host desde el que se abrió la app en el puerto 8080 (sirve en toda la red local).
 */

const API = (() => {
  const porDefecto = location.protocol.startsWith('http')
    ? `${location.protocol}//${location.hostname}:8080`
    : 'http://localhost:8080';
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

  async function llamar(metodo, ruta, body, ms = 3000) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), ms);
    const headers = { 'Content-Type': 'application/json', 'X-Client-Id': clientId };
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
    rutas: (origen_id, destino_id, prioridad) => llamar('POST', '/routes', { origen_id, destino_id, prioridad }),
    // El asistente puede tardar más: el LLM interpreta el mensaje y pule la respuesta
    chat: async (texto) => ok(await llamar('POST', '/chat/web', { texto }, 30000)),
    incidentes: async () => ok(await llamar('GET', '/incidents')),
    reportar: (body) => llamar('POST', '/incidents', body),
    votar: (id, valor) => llamar('POST', `/incidents/${encodeURIComponent(id)}/votos`, { valor }),
    perfil: async () => ok(await llamar('GET', '/reporters/me')),
    verificar: (id) => llamar('POST', `/admin/incidents/${encodeURIComponent(id)}/verificar`),
    rechazar: (id) => llamar('POST', `/admin/incidents/${encodeURIComponent(id)}/rechazar`),
    limpiar: () => llamar('DELETE', '/admin/incidents'),
  };
})();

window.API = API;
