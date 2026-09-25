/*
 * ai.js — Capa de "agente": entiende lenguaje natural.
 * ---------------------------------------------------------------------------
 * HÍBRIDO A PRUEBA DE FALLOS:
 *   1) SIEMPRE intenta entender localmente (regex + alias). Funciona OFFLINE.
 *   2) Si hay señal y hay API key configurada, usa un LLM (Claude) para
 *      conversación más natural y explicaciones. Si falla, cae al modo local.
 *
 * Esto es clave para la rúbrica de VIABILIDAD: el demo no se cae si no hay wifi.
 */

const AI = (() => {
  // Config opcional del LLM (se deja vacío; en el evento se puede pegar una key
  // o usar un proxy). NUNCA hardcodear claves reales en un repo público.
  const LLM = {
    habilitado: false,
    endpoint: '', // p.ej. un proxy propio hacia la API de Claude
    modelo: 'claude-sonnet-5',
  };

  // --- Interpretación local del mensaje ---
  function interpretar(texto) {
    const t = texto.toLowerCase();
    let prioridad = 'rapido';
    if (/(barat|econom|plata|menos plata|cuesta menos)/.test(t)) prioridad = 'barato';
    if (/(transbordo|cambios|directo|sin cambiar)/.test(t)) prioridad = 'transbordos';

    // Patrones "de X a Y", "desde X hasta Y", "para ir a Y estoy en X"
    let origen = null, destino = null;
    let m = t.match(/(?:de|desde)\s+(.+?)\s+(?:a|hasta|para|hacia)\s+(.+)/);
    if (m) { origen = Engine.resolver(m[1]); destino = Engine.resolver(m[2]); }
    if (!destino) {
      m = t.match(/(?:ir|llegar|voy)\s+(?:a|hasta|hacia)\s+(.+)/);
      if (m) destino = Engine.resolver(m[1]);
    }
    if (!origen) {
      m = t.match(/(?:estoy|salgo)\s+(?:en|de|desde)\s+(.+)/);
      if (m) origen = Engine.resolver(m[1]);
    }
    return { origen, destino, prioridad };
  }

  // --- Respuesta en lenguaje natural sobre una ruta ---
  function explicar(op) {
    if (!op) return 'No encontré una ruta para eso. ¿Puedes darme el barrio de origen y destino?';
    const modos = window.DB.MODOS;
    const pasos = op.tramos.map((tr, i) => {
      const m = modos[tr.modo];
      const nOr = (Engine.nodoPorId[tr.desde] || {}).nombre;
      const nDe = (Engine.nodoPorId[tr.hasta] || {}).nombre;
      const costo = tr.cop > 0 ? ` · $${tr.cop.toLocaleString('es-CO')}` : '';
      const alerta = tr.motivo ? ` ⚠️ ${tr.motivo}` : '';
      return `${i + 1}. ${m.icono} ${m.nombre} (${tr.ruta}): ${nOr} → ${nDe} · ${Math.round(tr.min)} min${costo}${alerta}`;
    });
    const sello = op.usaInformal
      ? '\n💡 Esta ruta usa transporte comunitario (informal) que no aparece en las apps tradicionales.'
      : '';
    return (
      `🚀 ${op.etiqueta}: ~${op.totalMin} min · $${op.totalCop.toLocaleString('es-CO')} · ${op.transbordos} transbordo(s)\n\n` +
      pasos.join('\n') + sello
    );
  }

  // --- Detección de intención de REPORTE (tipo Waze por WhatsApp) ---
  const PALABRAS_TIPO = {
    derrumbe: ['derrumbe', 'deslizamiento', 'se cayo', 'se vino'],
    bloqueo: ['bloqueo', 'bloquead', 'manifestacion', 'cerrada', 'cierre', 'protesta'],
    trancon: ['trancon', 'trancón', 'trafico', 'tráfico', 'atasco', 'pegado'],
    lleno: ['lleno', 'no para', 'no pasa lleno', 'repleto'],
    sinservicio: ['no hay servicio', 'sin servicio', 'no esta pasando', 'no está pasando', 'no sube', 'no subio', 'varado'],
    novedad: ['novedad', 'cambio', 'aviso'],
  };
  function detectarReporte(t) {
    if (!/report|hay un|hay una|se var|no está pasando|no esta pasando|no sube|bloque|derrumbe|trancon|trancón/.test(t)) return null;
    let tipo = 'novedad';
    for (const [k, arr] of Object.entries(PALABRAS_TIPO)) if (arr.some((w) => t.includes(w))) { tipo = k; break; }
    // Buscar un lugar mencionado y un tramo que lo toque
    let lugar = null;
    for (const [alias, id] of Object.entries(window.DB.ALIAS)) if (t.includes(alias)) { lugar = id; break; }
    if (!lugar) return null;
    const tr = window.DB.TRAMOS.find((x) => x.de === lugar || x.a === lugar);
    if (!tr) return null;
    return { tipo, tramo: tr };
  }

  // --- Punto de entrada del chat ---
  async function responder(texto, canal = 'whatsapp', autor = 'Vecino/a') {
    const intent = interpretar(texto);
    const t = texto.toLowerCase();

    // Saludos / ayuda
    if (/^(hola|buenas|hey|hi|buenos dias|buenas tardes)/.test(t)) {
      return { tipo: 'texto', texto: '¡Hola! Soy tu asistente de Muévete CB 🚡. Puedo:\n• Buscar rutas: "de Meissen a Paraíso"\n• Recibir reportes: "reporto un derrumbe en Paraíso"\nDime, ¿en qué te ayudo?' };
    }

    // ¿Es un reporte ciudadano?
    const rep = detectarReporte(t);
    if (rep) {
      // Los reportes solo se guardan en el servidor: sin conexión no hay dónde registrarlo
      const tt = Reports.TIPOS[rep.tipo];
      return { tipo: 'texto', texto: `Entendí que reportas *${tt.label}*, pero ahora no hay conexión con el servidor y no puedo guardarlo 😕. Inténtalo en un momento o usa la pestaña Reportar.` };
    }

    if (intent.origen && intent.destino) {
      const ops = Engine.opciones(intent.origen, intent.destino);
      if (!ops.length) return { tipo: 'texto', texto: 'No encontré ruta entre esos puntos 😕. Prueba con barrios cercanos.' };
      const elegida = ops.find((o) => o.prioridad === intent.prioridad) || ops[0];
      // Si hay LLM, lo usamos para pulir; si no, respuesta local.
      let txt = explicar(elegida);
      if (LLM.habilitado) {
        try { txt = await pulirConLLM(texto, elegida, txt); } catch (e) { /* cae a local */ }
      }
      return { tipo: 'ruta', texto: txt, opcion: elegida, todas: ops };
    }

    if (intent.destino && !intent.origen) {
      return { tipo: 'texto', texto: `¿Desde dónde sales para llegar a ${(Engine.nodoPorId[intent.destino] || {}).nombre}?` };
    }

    return { tipo: 'texto', texto: 'Cuéntame tu *origen* y *destino*. Ej: "de Sierra Morena al Hospital Meissen".' };
  }

  // --- Integración LLM opcional (esqueleto listo para el evento) ---
  async function pulirConLLM(pregunta, ruta, textoLocal) {
    const prompt =
      `Eres un asistente de movilidad de Ciudad Bolívar, Bogotá. Responde breve, cálido y en español ` +
      `colombiano. Pregunta del usuario: "${pregunta}". Ruta calculada (no la cambies, solo explícala ` +
      `de forma amable y clara):\n${textoLocal}`;
    const r = await fetch(LLM.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: LLM.modelo, prompt }),
    });
    const data = await r.json();
    return data.texto || textoLocal;
  }

  return { responder, interpretar, explicar, LLM };
})();

window.AI = AI;
