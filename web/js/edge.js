/*
 * edge.js — Computación en el BORDE (Edge AI) con cámaras
 * ===========================================================================
 * DOS modos:
 *
 * A) CÁMARAS SIMULADAS (siempre disponibles): nodos "semáforo inteligente" en
 *    puntos críticos que detectan congestión y publican incidentes al mapa vivo,
 *    igual que un ciudadano. Simula visión por computador desplegada en el borde.
 *
 * B) CÁMARA REAL (PoC demostrable): usa la webcam + TensorFlow.js (COCO-SSD)
 *    para detectar vehículos y personas EN EL DISPOSITIVO (edge, sin nube: solo
 *    se transmite el conteo/evento, nunca el video). Calcula un índice de
 *    congestión y, si supera el umbral, publica un incidente automático.
 *
 * Por qué "edge" y no nube (argumento para el jurado):
 *   - Privacidad: el video no sale del dispositivo, solo el dato.
 *   - Ancho de banda: en la ladera la conectividad es débil; enviar video sería inviable.
 *   - Latencia: la detección es inmediata, local.
 *   - Costo: no requiere servidores de inferencia.
 */

const Edge = (() => {
  const { CAMARAS } = window.DB;
  let simTimer = null;
  let modelo = null;
  let camaraActiva = false;

  // ---------- A) Simulación de cámaras edge ----------
  function iniciarSimulacion(intervaloMs = 12000) {
    detenerSimulacion();
    simTimer = setInterval(() => {
      const cam = CAMARAS[Math.floor(Math.random() * CAMARAS.length)];
      // "Detecta" un nivel de congestión aleatorio
      const nivel = Math.random();
      let tipo = null;
      if (nivel > 0.85) tipo = 'trancon';
      else if (nivel > 0.7) tipo = 'lleno';
      if (!tipo) return; // la mayoría de ciclos: flujo normal
      emitirDesdeCamara(cam, tipo, `Congestión detectada (índice ${(nivel * 100).toFixed(0)}%)`);
    }, intervaloMs);
    return true;
  }
  function detenerSimulacion() { if (simTimer) clearInterval(simTimer); simTimer = null; }

  function emitirDesdeCamara(cam, tipo, nota) {
    Reports.reportar({
      tipo, deId: cam.tramo.de, aId: cam.tramo.a, modo: cam.tramo.modo,
      nota, canal: 'edge', autor: cam.nombre,
    });
  }

  // ---------- B) Cámara real con visión por computador (TensorFlow.js) ----------
  const VEHICULOS = ['car', 'bus', 'truck', 'motorcycle', 'bicycle'];

  async function cargarModelo(onStatus) {
    if (modelo) return modelo;
    if (typeof cocoSsd === 'undefined') { onStatus && onStatus('Modelo no disponible (sin conexión para descargarlo la primera vez).'); return null; }
    onStatus && onStatus('Cargando modelo de visión (una sola vez)…');
    modelo = await cocoSsd.load({ base: 'lite_mobilenet_v2' }); // ligero para gama baja
    onStatus && onStatus('Modelo listo. Analizando en el dispositivo (edge).');
    return modelo;
  }

  /*
   * iniciarCamaraReal(videoEl, camId, onFrame, onStatus)
   *   videoEl : <video> donde se muestra la webcam
   *   camId   : id de la cámara del catálogo a la que se asocia el incidente
   *   onFrame : callback({vehiculos, personas, indice, detecciones}) por frame
   */
  async function iniciarCamaraReal(videoEl, camId, onFrame, onStatus) {
    const cam = CAMARAS.find((c) => c.id === camId) || CAMARAS[0];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      videoEl.srcObject = stream;
      await videoEl.play();
    } catch (e) { onStatus && onStatus('No se pudo abrir la cámara: ' + e.message); return; }

    const m = await cargarModelo(onStatus);
    if (!m) return;

    camaraActiva = true;
    let ultimaEmision = 0;

    async function loop() {
      if (!camaraActiva) return;
      let detecciones = [];
      try { detecciones = await m.detect(videoEl); } catch (e) {}
      const vehiculos = detecciones.filter((d) => VEHICULOS.includes(d.class) && d.score > 0.5).length;
      const personas = detecciones.filter((d) => d.class === 'person' && d.score > 0.5).length;
      // Índice de congestión simple: vehículos pesan más que personas
      const indice = Math.min(100, vehiculos * 18 + personas * 6);
      onFrame && onFrame({ vehiculos, personas, indice, detecciones });

      // Si hay congestión sostenida, publica un incidente (máx. 1 cada 20s)
      if (indice >= 60 && Date.now() - ultimaEmision > 20000) {
        ultimaEmision = Date.now();
        const tipo = indice >= 80 ? 'trancon' : 'lleno';
        emitirDesdeCamara(cam, tipo, `Cámara edge: ${vehiculos} vehículos detectados (índice ${indice.toFixed(0)}%)`);
        onStatus && onStatus(`⚠️ Congestión reportada automáticamente por ${cam.nombre}`);
      }
      requestAnimationFrame(loop);
    }
    loop();
  }

  function detenerCamaraReal(videoEl) {
    camaraActiva = false;
    if (videoEl && videoEl.srcObject) {
      videoEl.srcObject.getTracks().forEach((t) => t.stop());
      videoEl.srcObject = null;
    }
  }

  return { iniciarSimulacion, detenerSimulacion, iniciarCamaraReal, detenerCamaraReal, emitirDesdeCamara };
})();

window.Edge = Edge;
