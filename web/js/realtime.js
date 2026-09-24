/*
 * realtime.js — Sincronización en tiempo real HÍBRIDA (tipo Waze)
 * ===========================================================================
 * Cada incidente (derrumbe, trancón, bloqueo…) se propaga al
 * instante a TODOS los usuarios conectados y aparece en el mapa de todos.
 *
 * Capa 1 (DEMO GARANTIZADO, offline):
 *    - Pub/sub en la misma página (paneles del simulador).
 *    - BroadcastChannel  → sincroniza pestañas y ventanas del mismo navegador.
 *    - localStorage + evento 'storage' → sincroniza y persiste (y navegadores
 *      sin BroadcastChannel). Estado compartido para quien entra tarde.
 *
 * Capa 2 (PRODUCCIÓN, opcional): adaptador a un backend (WebSocket/Firebase).
 *    Ver backend/README.md. Si se configura, se refleja también allá.
 */

const Realtime = (() => {
  const STORE_KEY = 'muevecb_incidentes';
  const CANAL = 'muevecb_rt';
  const suscriptores = [];
  let bc = null;
  try { bc = new BroadcastChannel(CANAL); } catch (e) { bc = null; }

  // --- Adaptador de backend (opcional, se activa si se define) ---
  const backend = { habilitado: false, enviar: null }; // ver conectarBackend()

  function leerStore() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY)) || []; } catch (e) { return []; }
  }
  function escribirStore(lista) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(lista)); } catch (e) {}
  }

  function notificar(evento) {
    suscriptores.forEach((fn) => { try { fn(evento); } catch (e) {} });
  }

  // Incidentes vigentes (no vencidos). vidaMin viene del tipo (reports.js).
  function vigentes() {
    const ahora = Date.now();
    return leerStore().filter((i) => ahora - i.ts < (i.vidaMin || 60) * 60000);
  }

  // Publica un incidente nuevo y lo propaga a todos los canales
  function publicar(incidente) {
    const inc = { id: incidente.id || (Date.now() + '-' + Math.random().toString(36).slice(2)),
      votos: 0, ...incidente, ts: incidente.ts || Date.now() };
    const lista = leerStore();
    if (lista.some((x) => x.id === inc.id)) return inc; // dedupe
    lista.unshift(inc);
    escribirStore(lista);
    const evento = { action: 'add', incidente: inc, lista: vigentes() };
    notificar(evento);
    if (bc) bc.postMessage(evento);
    if (backend.habilitado && backend.enviar) { try { backend.enviar(evento); } catch (e) {} }
    return inc;
  }

  function votar(id) {
    const lista = leerStore();
    const i = lista.find((x) => x.id === id);
    if (!i) return;
    i.votos = (i.votos || 0) + 1;
    escribirStore(lista);
    const evento = { action: 'update', incidente: i, lista: vigentes() };
    notificar(evento);
    if (bc) bc.postMessage(evento);
  }

  function eliminar(id) {
    escribirStore(leerStore().filter((x) => x.id !== id));
    const evento = { action: 'remove', id, lista: vigentes() };
    notificar(evento);
    if (bc) bc.postMessage(evento);
  }

  function limpiarTodo() {
    escribirStore([]);
    const evento = { action: 'reset', lista: [] };
    notificar(evento);
    if (bc) bc.postMessage(evento);
  }

  function suscribir(fn) { suscriptores.push(fn); return () => {
    const i = suscriptores.indexOf(fn); if (i >= 0) suscriptores.splice(i, 1);
  }; }

  // Recibir eventos de otras pestañas/ventanas
  if (bc) bc.onmessage = (e) => notificar({ ...e.data, remoto: true });
  window.addEventListener('storage', (e) => {
    if (e.key === STORE_KEY) notificar({ action: 'sync', lista: vigentes(), remoto: true });
  });

  // Enganche opcional de backend real (producción)
  function conectarBackend(fnEnviar, fnRecibir) {
    backend.habilitado = true; backend.enviar = fnEnviar;
    if (fnRecibir) fnRecibir((evento) => notificar({ ...evento, remoto: true }));
  }

  return { publicar, votar, eliminar, limpiarTodo, suscribir, vigentes, conectarBackend };
})();

window.Realtime = Realtime;
