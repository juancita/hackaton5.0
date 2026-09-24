/*
 * engine.js — Motor de rutas multimodal (corre 100% en el celular, OFFLINE)
 * -------------------------------------------------------------------------
 * Construye un grafo con los tramos formales + informales y calcula la mejor
 * ruta con Dijkstra. Soporta 3 prioridades: rápido, barato, menos transbordos.
 * Los reportes ciudadanos (bloqueos/demoras) penalizan tramos en tiempo real.
 */

const Engine = (() => {
  const { PARADEROS, TRAMOS, MODOS, ALIAS } = window.DB;
  const nodoPorId = Object.fromEntries(PARADEROS.map((p) => [p.id, p]));

  // Reportes activos: mapa "de|a|modo" -> factor de penalización o bloqueo
  let penalizaciones = {}; // { claveTramo: { bloqueado:bool, factor:num, motivo:str } }

  function claveTramo(t) { return `${t.de}|${t.a}|${t.modo}`; }

  function setPenalizaciones(mapa) { penalizaciones = mapa || {}; }

  // Construye lista de adyacencia (no dirigido: cada tramo va en ambos sentidos).
  // modos: medios permitidos (Set o array); null = todos. Caminar siempre se permite.
  function construirGrafo(modos) {
    const adj = {};
    const permitidos = modos ? new Set(modos) : null;
    PARADEROS.forEach((p) => (adj[p.id] = []));
    TRAMOS.forEach((t) => {
      if (permitidos && t.modo !== 'caminando' && !permitidos.has(t.modo)) return;
      const pen = penalizaciones[claveTramo(t)] || penalizaciones[`${t.a}|${t.de}|${t.modo}`];
      if (pen && pen.bloqueado) return; // tramo caído por reporte ciudadano
      const factor = pen ? pen.factor || 1 : 1;
      const espera = t.freqMin ? t.freqMin / 2 : 0; // espera promedio = mitad de la frecuencia
      const base = { ...t, min: t.min * factor, espera, motivo: pen ? pen.motivo : null };
      adj[t.de].push({ ...base, hacia: t.a });
      adj[t.a].push({ ...base, hacia: t.de, de: t.a, a: t.de });
    });
    return adj;
  }

  // Costo de una arista según la prioridad elegida
  // informal=true: el informal pesa la mitad (opción "Con transporte informal")
  function costoArista(arista, prioridad, informal = false) {
    const tiempo = arista.min + arista.espera;
    let c = tiempo; // 'rapido' (por defecto)
    if (prioridad === 'barato') c = arista.cop + tiempo * 5; // pondera plata
    else if (prioridad === 'transbordos') c = tiempo + 100; // penaliza cada salto
    return informal && !MODOS[arista.modo].formal ? c / 2 : c;
  }

  // Dijkstra
  function mejorRuta(origenId, destinoId, prioridad = 'rapido', modos = null, informal = false) {
    if (origenId === destinoId) return null;
    const adj = construirGrafo(modos);
    const dist = {}, prev = {}, prevArista = {};
    PARADEROS.forEach((p) => (dist[p.id] = Infinity));
    dist[origenId] = 0;
    const pq = [[0, origenId]];

    while (pq.length) {
      pq.sort((a, b) => a[0] - b[0]);
      const [d, u] = pq.shift();
      if (u === destinoId) break;
      if (d > dist[u]) continue;
      (adj[u] || []).forEach((ar) => {
        const nd = d + costoArista(ar, prioridad, informal);
        if (nd < dist[ar.hacia]) {
          dist[ar.hacia] = nd;
          prev[ar.hacia] = u;
          prevArista[ar.hacia] = ar;
          pq.push([nd, ar.hacia]);
        }
      });
    }

    if (dist[destinoId] === Infinity) return null;

    // Reconstruir camino
    const pasos = [];
    let cur = destinoId;
    while (cur !== origenId) {
      const ar = prevArista[cur];
      pasos.unshift(ar);
      cur = prev[cur];
    }
    return resumir(pasos, origenId, destinoId);
  }

  // Agrupa pasos consecutivos de la misma ruta y calcula totales
  function resumir(pasos, origenId, destinoId) {
    const tramos = [];
    pasos.forEach((ar) => {
      const ultimo = tramos[tramos.length - 1];
      if (ultimo && ultimo.ruta === ar.ruta && ultimo.modo === ar.modo) {
        ultimo.hasta = ar.a;
        ultimo.min += ar.min;
        ultimo.cop += ar.cop;
        ultimo.paradas.push(ar.a);
      } else {
        tramos.push({
          modo: ar.modo, ruta: ar.ruta, desde: ar.de, hasta: ar.a,
          min: ar.min + ar.espera, cop: ar.cop, espera: ar.espera,
          motivo: ar.motivo, paradas: [ar.de, ar.a],
        });
      }
    });
    const totalMin = Math.round(tramos.reduce((s, t) => s + t.min, 0));
    const totalCop = tramos.reduce((s, t) => s + t.cop, 0);
    const transbordos = Math.max(0, tramos.length - 1);
    const usaInformal = tramos.some((t) => !MODOS[t.modo].formal && t.modo !== 'caminando');
    return {
      origen: origenId, destino: destinoId,
      tramos, totalMin, totalCop, transbordos, usaInformal,
      alertas: tramos.filter((t) => t.motivo).map((t) => t.motivo),
    };
  }

  // Devuelve varias opciones (rápida, económica, menos transbordos) sin duplicados, y luego,
  // por cada medio que usa la primera, la mejor ruta "Sin <medio>" para poder escoger otra,
  // y una "Con transporte informal" si ninguna lo usa.
  function opciones(origenId, destinoId, modos = null, preferida = 'rapido') {
    const vistos = new Set();
    const res = [];
    const agregar = (r, etiqueta, prio) => {
      if (!r) return;
      const firma = r.tramos.map((t) => t.ruta).join('>');
      if (vistos.has(firma)) return;
      vistos.add(firma);
      res.push({ ...r, etiqueta, prioridad: prio });
    };
    [['rapido', 'La más rápida'], ['barato', 'La más económica'], ['transbordos', 'Menos transbordos']]
      .forEach(([prio, etiqueta]) => agregar(mejorRuta(origenId, destinoId, prio, modos), etiqueta, prio));
    if (!res.length) return res;
    const todos = modos ? [...modos] : Object.keys(MODOS);
    [...new Set(res[0].tramos.map((t) => t.modo).filter((m) => m !== 'caminando'))].forEach((m) => {
      agregar(mejorRuta(origenId, destinoId, preferida, todos.filter((x) => x !== m)), `Sin ${MODOS[m].nombre}`, preferida);
    });
    // Que el transporte informal (jeeps, colectivos, veredales) también salga como alternativa
    if (!res.some((o) => o.usaInformal)) {
      const r = mejorRuta(origenId, destinoId, preferida, modos, true);
      if (r && r.usaInformal) agregar(r, 'Con transporte informal', preferida);
    }
    return res;
  }

  // Resolver texto -> id de paradero (usa alias y coincidencia parcial)
  function resolver(texto) {
    if (!texto) return null;
    const t = texto.toLowerCase().trim();
    if (ALIAS[t]) return ALIAS[t];
    for (const [alias, id] of Object.entries(ALIAS)) {
      if (t.includes(alias)) return id;
    }
    const p = PARADEROS.find((p) => p.nombre.toLowerCase().includes(t));
    return p ? p.id : null;
  }

  return { mejorRuta, opciones, resolver, setPenalizaciones, nodoPorId, claveTramo };
})();

window.Engine = Engine;
