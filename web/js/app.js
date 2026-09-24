/*
 * app.js — Interfaz. Une planeador, asistente, mapa vivo (Waze), reportes y cámara edge.
 * Vainilla JS + Leaflet + TensorFlow.js. Funciona offline (con degradación elegante).
 */
(() => {
  const { PARADEROS, MODOS, TRAMOS, CAMARAS } = window.DB;
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  // ---------- Navegación ----------
  $$('.tabbar button').forEach((b) => b.addEventListener('click', () => {
    $$('.tabbar button').forEach((x) => x.classList.remove('active'));
    $$('.view').forEach((v) => v.classList.remove('active'));
    b.classList.add('active');
    $('#view-' + b.dataset.view).classList.add('active');
    if (b.dataset.view === 'map') abrirMapa();
  }));

  // ---------- Estado de red ----------
  const net = $('#netStatus');
  function pintarRed() {
    net.textContent = navigator.onLine ? '● en línea' : '● offline-ready';
    net.classList.toggle('on', navigator.onLine);
  }
  window.addEventListener('online', pintarRed);
  window.addEventListener('offline', pintarRed);
  pintarRed();

  // ---------- Toasts / notificaciones ----------
  function toast(html, color) {
    const el = document.createElement('div');
    el.className = 'toast';
    if (color) el.style.borderLeftColor = color;
    el.innerHTML = html;
    $('#toasts').appendChild(el);
    setTimeout(() => el.classList.add('show'), 10);
    setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, 5000);
  }

  // ---------- Autocompletar ----------
  const datalist = $('#lugares');
  PARADEROS.forEach((p) => { const o = document.createElement('option'); o.value = p.nombre; datalist.appendChild(o); });

  // ---------- Planeador ----------
  Reports.aplicarAlMotor();
  $('#btnBuscar').addEventListener('click', buscar);
  function buscar() {
    Reports.aplicarAlMotor();
    const oId = Engine.resolver($('#origen').value);
    const dId = Engine.resolver($('#destino').value);
    const cont = $('#resultados');
    if (!oId || !dId) { cont.innerHTML = '<p class="empty">Escribe un origen y un destino válidos 🙏</p>'; return; }
    if (oId === dId) { cont.innerHTML = '<p class="empty">El origen y el destino son iguales 😅</p>'; return; }
    const ops = Engine.opciones(oId, dId);
    if (!ops.length) { cont.innerHTML = '<p class="empty">No encontré ruta entre esos puntos.</p>'; return; }
    cont.innerHTML = ops.map(tarjetaRuta).join('');
  }
  function tarjetaRuta(op) {
    const pasos = op.tramos.map((tr) => {
      const m = MODOS[tr.modo];
      const nOr = Engine.nodoPorId[tr.desde].nombre, nDe = Engine.nodoPorId[tr.hasta].nombre;
      const costo = tr.cop > 0 ? ` · $${tr.cop.toLocaleString('es-CO')}` : '';
      const alerta = tr.motivo ? `<div class="alerta">⚠️ ${tr.motivo}</div>` : '';
      return `<div class="paso"><span class="ico">${m.icono}</span><div>
        <strong>${m.nombre}</strong> · ${tr.ruta}<br>${nOr} → ${nDe} · ${Math.round(tr.min)} min${costo}${alerta}</div></div>`;
    }).join('');
    const badge = op.usaInformal ? '<span class="ruta-badge">＋ informal</span>' : '';
    return `<div class="ruta-card ${op.usaInformal ? 'informal' : ''}">
      <div class="ruta-head"><span class="ruta-etiqueta">${op.etiqueta}</span>${badge}</div>${pasos}
      <div class="totales"><span>⏱ ${op.totalMin} min</span><span>💵 $${op.totalCop.toLocaleString('es-CO')}</span><span>🔁 ${op.transbordos}</span></div>
    </div>`;
  }

  // ---------- Chat (modo WhatsApp) ----------
  const chatBody = $('#chatBody');
  function addMsg(texto, quien) {
    const d = document.createElement('div'); d.className = 'msg ' + quien; d.textContent = texto;
    chatBody.appendChild(d); chatBody.scrollTop = chatBody.scrollHeight;
  }
  async function enviarChat() {
    const input = $('#chatInput'); const t = input.value.trim(); if (!t) return;
    addMsg(t, 'me'); input.value = '';
    const r = await AI.responder(t, 'whatsapp', 'Tú');
    addMsg(r.texto, 'bot');
  }
  $('#chatSend').addEventListener('click', enviarChat);
  $('#chatInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') enviarChat(); });
  addMsg('¡Hola! 👋 Soy tu asistente de Muévete CB.\n• "de Meissen a Paraíso"\n• "reporto un derrumbe en Paraíso"', 'bot');

  // ---------- Fuentes de datos oficiales ----------
  let nodosOficiales = [];
  (async () => {
    const r = await Datasources.cargar();
    nodosOficiales = r.nodos;
    const iconos = { vivo: '🟢', cache: '🟡', semilla: '⚪' };
    $('#dataStatus').textContent = `${iconos[r.estado]} ${r.detalle}`;
    $('#dataStatus').title = 'Fuente de datos oficiales (ArcGIS TransMilenio / datos.gov.co / IDECA)';
    if (mapa) pintarOficiales();
  })();

  // ---------- MAPA VIVO (Leaflet, tipo Waze) ----------
  let mapa = null, capaInc = null, capaOfi = null, usandoSvg = false;
  function abrirMapa() {
    if (usandoSvg) { dibujarSvg(); return; }
    if (mapa) { setTimeout(() => mapa.invalidateSize(), 100); return; }
    if (typeof L === 'undefined') { activarSvgFallback(); return; }
    mapa = L.map('mapa', { zoomControl: true }).setView([4.575, -74.155], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18, attribution: '© OpenStreetMap',
    }).addTo(mapa);
    dibujarRutas();
    dibujarCamaras();
    capaOfi = L.layerGroup().addTo(mapa);
    capaInc = L.layerGroup().addTo(mapa);
    pintarOficiales();
    pintarIncidentes(Realtime.vigentes());
    pintarLeyenda();
    setTimeout(() => mapa.invalidateSize(), 120);
  }
  function activarSvgFallback() {
    usandoSvg = true;
    $('#mapa').style.display = 'none';
    $('#mapaSvg').style.display = 'block';
    dibujarSvg();
    pintarLeyenda();
  }
  function dibujarRutas() {
    TRAMOS.forEach((t) => {
      const a = Engine.nodoPorId[t.de], b = Engine.nodoPorId[t.a];
      L.polyline([[a.lat, a.lng], [b.lat, b.lng]], {
        color: MODOS[t.modo].color, weight: MODOS[t.modo].formal ? 4 : 3,
        opacity: 0.75, dashArray: MODOS[t.modo].formal ? null : '6,6',
      }).addTo(mapa).bindPopup(`${MODOS[t.modo].icono} ${MODOS[t.modo].nombre}<br><b>${t.ruta}</b><br>${a.nombre} → ${b.nombre}`);
    });
    PARADEROS.forEach((p) => {
      L.circleMarker([p.lat, p.lng], { radius: 6, color: '#fff', weight: 2,
        fillColor: p.zona === 'rural' ? '#8B5A2B' : (p.tipo === 'cable' || p.tipo === 'portal' ? '#7B2FF7' : '#1B75BB'),
        fillOpacity: 1 }).addTo(mapa).bindPopup(`<b>${p.nombre}</b><br>Zona ${p.zona}`);
    });
  }
  function dibujarCamaras() {
    CAMARAS.forEach((c) => {
      L.marker([c.lat, c.lng], { icon: L.divIcon({ className: 'cam-icon', html: '📹', iconSize: [26, 26] }) })
        .addTo(mapa).bindPopup(`<b>${c.nombre}</b><br>Cámara de fotodetección (reúso Edge AI)`);
    });
  }
  function pintarOficiales() {
    if (!capaOfi) return;
    capaOfi.clearLayers();
    nodosOficiales.slice(0, 250).forEach((n) => {
      L.circleMarker([n.lat, n.lng], { radius: 3, color: '#1B75BB', weight: 1, fillColor: '#1B75BB', fillOpacity: 0.6 })
        .addTo(capaOfi).bindPopup(`<b>${n.nombre}</b><br><small>${n.fuente}</small>`);
    });
  }
  function pintarIncidentes(lista) {
    $('#incCount').textContent = `${lista.length} alertas activas`;
    if (usandoSvg) { dibujarSvg(); return; }
    if (!capaInc) return;
    capaInc.clearLayers();
    lista.forEach((i) => {
      const t = Reports.TIPOS[i.tipo] || Reports.TIPOS.novedad;
      const icon = L.divIcon({ className: 'inc-icon', html: `<div class="inc-pin" style="--c:${t.color}">${t.icono}</div>`, iconSize: [34, 34] });
      L.marker([i.lat, i.lng], { icon }).addTo(capaInc)
        .bindPopup(`<b>${t.icono} ${t.label}</b><br>${i.nota || ''}<br><small>${i.canal === 'edge' ? '📹 ' : ''}${i.autor} · ${hace(i.ts)}</small>`);
    });
  }
  function pintarLeyenda() {
    $('#mapLegend').innerHTML = Object.values(MODOS)
      .map((m) => `<span class="leg" style="background:${m.color}">${m.icono} ${m.nombre}</span>`).join('')
      + '<span class="leg" style="background:#111">📹 Fotodetección</span>';
  }
  function dibujarSvg() {
    const svg = $('#mapaSvg'); if (!svg) return; svg.innerHTML = '';
    const NS = 'http://www.w3.org/2000/svg';
    TRAMOS.forEach((t) => {
      const a = Engine.nodoPorId[t.de], b = Engine.nodoPorId[t.a];
      const l = document.createElementNS(NS, 'line');
      l.setAttribute('x1', a.x); l.setAttribute('y1', a.y); l.setAttribute('x2', b.x); l.setAttribute('y2', b.y);
      l.setAttribute('stroke', MODOS[t.modo].color); l.setAttribute('stroke-width', MODOS[t.modo].formal ? 0.9 : 0.7);
      if (!MODOS[t.modo].formal) l.setAttribute('stroke-dasharray', '1.5,1');
      svg.appendChild(l);
    });
    PARADEROS.forEach((p) => {
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', p.x); c.setAttribute('cy', p.y); c.setAttribute('r', 1.4);
      c.setAttribute('fill', p.zona === 'rural' ? '#8B5A2B' : '#7B2FF7'); c.setAttribute('stroke', '#fff'); c.setAttribute('stroke-width', '.4');
      svg.appendChild(c);
      const tx = document.createElementNS(NS, 'text'); tx.setAttribute('x', p.x + 2); tx.setAttribute('y', p.y + 0.8);
      tx.setAttribute('class', 'paradero-label'); tx.textContent = p.nombre; svg.appendChild(tx);
    });
    Realtime.vigentes().forEach((i) => {
      const t = Reports.TIPOS[i.tipo]; const a = Engine.nodoPorId[i.deId], b = Engine.nodoPorId[i.aId];
      const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', cx); c.setAttribute('cy', cy); c.setAttribute('r', 2.4);
      c.setAttribute('fill', t.color); c.setAttribute('stroke', '#fff'); c.setAttribute('stroke-width', '.5');
      svg.appendChild(c);
    });
  }

  // ---------- Reportes ----------
  const repTipo = $('#repTipo');
  Object.entries(Reports.TIPOS).forEach(([k, v]) => { const o = document.createElement('option'); o.value = k; o.textContent = `${v.icono} ${v.label}`; repTipo.appendChild(o); });
  const repTramo = $('#repTramo');
  TRAMOS.forEach((t, i) => { const o = document.createElement('option'); o.value = i;
    o.textContent = `${MODOS[t.modo].icono} ${t.ruta}: ${Engine.nodoPorId[t.de].nombre} → ${Engine.nodoPorId[t.a].nombre}`; repTramo.appendChild(o); });
  $('#btnReportar').addEventListener('click', () => {
    const t = TRAMOS[+repTramo.value];
    Reports.reportar({ tipo: repTipo.value, deId: t.de, aId: t.a, modo: t.modo, nota: $('#repNota').value, canal: 'web', autor: 'Tú (web)' });
    $('#repNota').value = '';
  });
  $('#btnLimpiar').addEventListener('click', () => { if (confirm('¿Limpiar todas las alertas? (solo para el demo)')) Realtime.limpiarTodo(); });
  function pintarReportes() {
    const lista = Realtime.vigentes(); const cont = $('#listaReportes');
    if (!lista.length) { cont.innerHTML = '<p class="empty">No hay alertas activas ahora mismo.</p>'; return; }
    cont.innerHTML = lista.map((i) => {
      const t = Reports.TIPOS[i.tipo] || Reports.TIPOS.novedad;
      const canalIco = i.canal === 'whatsapp' ? '💬' : i.canal === 'edge' ? '📹' : '🌐';
      return `<div class="rep-item" style="border-left-color:${t.color}">${t.icono} <strong>${t.label}</strong>
        <br>${Engine.nodoPorId[i.deId].nombre} → ${Engine.nodoPorId[i.aId].nombre}
        ${i.nota ? '<br>“' + i.nota + '”' : ''}
        <br><small>${canalIco} ${i.autor} · ${hace(i.ts)}</small>
        <button class="voto" data-id="${i.id}">👍 ${i.votos || 0}</button></div>`;
    }).join('');
    $$('.voto').forEach((b) => b.addEventListener('click', () => Realtime.votar(b.dataset.id)));
  }
  function hace(ts) { const m = Math.round((Date.now() - ts) / 60000); return m < 1 ? 'ahora' : `hace ${m} min`; }

  // ---------- Reacción a incidentes en tiempo real ----------
  Realtime.suscribir((ev) => {
    Reports.aplicarAlMotor();
    if (ev.action === 'add' && ev.incidente) {
      const t = Reports.TIPOS[ev.incidente.tipo] || Reports.TIPOS.novedad;
      const canalIco = ev.incidente.canal === 'edge' ? '📹 Fotodetección' : ev.incidente.canal === 'whatsapp' ? '💬 WhatsApp' : '🌐 Web';
      toast(`<b>${t.icono} ${t.label}</b><br>${Engine.nodoPorId[ev.incidente.deId].nombre} → ${Engine.nodoPorId[ev.incidente.aId].nombre}<br><small>${canalIco} · ${ev.incidente.autor}</small>`, t.color);
    }
    pintarReportes();
    pintarIncidentes(Realtime.vigentes());
  });
  pintarReportes();

  // ---------- Cámara Edge ----------
  const camSel = $('#camSel');
  CAMARAS.forEach((c) => { const o = document.createElement('option'); o.value = c.id; o.textContent = c.nombre; camSel.appendChild(o); });
  const video = $('#cam');
  $('#btnCamOn').addEventListener('click', () => {
    $('#camStats').textContent = 'Iniciando…';
    Edge.iniciarCamaraReal(video, camSel.value,
      ({ vehiculos, personas, indice }) => {
        $('#camStats').innerHTML = `🚗 ${vehiculos} vehículos · 🚶 ${personas} personas<br>Índice de congestión: <b>${indice.toFixed(0)}%</b>
          <div class="barra"><span style="width:${indice}%;background:${indice > 70 ? '#e74c3c' : indice > 40 ? '#f39c12' : '#2ecc71'}"></span></div>`;
      },
      (msg) => toast(msg));
  });
  $('#btnCamOff').addEventListener('click', () => { Edge.detenerCamaraReal(video); $('#camStats').textContent = 'Cámara apagada'; });
  let simOn = false;
  $('#btnSim').addEventListener('click', (e) => {
    simOn = !simOn;
    if (simOn) { Edge.iniciarSimulacion(9000); e.target.textContent = '⏸️ Detener cámaras de fotodetección'; toast('🛰️ Red de cámaras de fotodetección ACTIVA'); }
    else { Edge.detenerSimulacion(); e.target.textContent = '🛰️ Activar cámaras de fotodetección'; }
  });

  // ---------- Service worker ----------
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
})();
