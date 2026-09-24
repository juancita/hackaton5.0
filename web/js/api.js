/*
 * api.js — Cliente del backend (FastAPI, ver backend/README.md).
 * ---------------------------------------------------------------------------
 * Cada llamada tiene timeout corto y, si falla, devuelve null para que la app
 * caiga a su lógica local (engine.js / ai.js / realtime.js). El demo no se cae sin red.
 *
 * Identidad sin cuenta: se genera un client_id una sola vez y se envía en X-Client-Id.
 * URL del backend: localStorage 'muevecb_api' o window.MUEVECB_API (por defecto http://localhost:8080).
 */

const API = (() => {
  const base = (() => {
    try { return localStorage.getItem('muevecb_api') || window.MUEVECB_API || 'http://localhost:8080'; }
    catch (e) { return window.MUEVECB_API || 'http://localhost:8080'; }
  })();

  const clientId = (() => {
    const KEY = 'muevecb_client_id';
    try {
      let id = localStorage.getItem(KEY);
      if (!id) { id = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random(); localStorage.setItem(KEY, id); }
      return id;
    } catch (e) { return 'anon-' + Math.random().toString(36).slice(2); }
  })();

  async function llamar(metodo, ruta, body, ms = 2500) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), ms);
    try {
      const r = await fetch(base + ruta, {
        method: metodo,
        headers: { 'Content-Type': 'application/json', 'X-Client-Id': clientId },
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
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
    suggest: async (q) => ok(await llamar('GET', `/places/suggest?q=${encodeURIComponent(q)}&limit=8`, null, 1500)),
    // El asistente puede tardar más si el LLM pule la respuesta
    chat: async (texto) => ok(await llamar('POST', '/chat/web', { texto }, 8000)),
    reportar: (body) => llamar('POST', '/incidents', body),
    votar: (id, valor = 'confirma') => llamar('POST', `/incidents/${encodeURIComponent(id)}/votos`, { valor }),
  };
})();

window.API = API;
