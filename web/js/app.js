/*
 * app.js — Interfaz. Une planeador, asistente, mapa vivo (Waze) y reportes.
 * Vainilla JS + Leaflet. Usa el backend (api.js) si responde; si no, funciona offline
 * con engine.js / ai.js / realtime.js (degradación elegante).
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

  // ---------- Autocompletar origen / destino ----------
  // Pide sugerencias al backend (/places/suggest); sin backend, filtra PARADEROS en local.
  const norm = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();
  function sugerirLocal(q) {
    const n = norm(q);
    const rango = (p) => {
      const nom = norm(p.nombre);
      if (nom.startsWith(n)) return 1;
      if (nom.split(/\s+/).some((w) => w.startsWith(n))) return 2;
      if (Object.entries(window.DB.ALIAS).some(([a, id]) => id === p.id && norm(a).startsWith(n))) return 3;
      return nom.includes(n) ? 4 : 0;
    };
    return PARADEROS.map((p) => [rango(p), p]).filter(([r]) => r)
      .sort((a, b) => a[0] - b[0] || a[1].nombre.localeCompare(b[1].nombre)).slice(0, 8).map(([, p]) => p);
  }
  function autocompletar(input) {
    const lista = document.createElement('ul');
    lista.className = 'sugerencias'; lista.setAttribute('role', 'listbox'); lista.hidden = true;
    input.parentElement.appendChild(lista);
    let items = [], activo = -1, timer = null, pedido = 0;

    function pintar() {
      lista.innerHTML = items.map((p, i) => `<li role="option" data-i="${i}" class="${i === activo ? 'activo' : ''}">
        <strong>${p.nombre}</strong><small>${p.tipo} · zona ${p.zona}</small></li>`).join('');
      lista.hidden = !items.length;
      input.setAttribute('aria-expanded', String(!lista.hidden));
    }
    function elegir(i) {
      const p = items[i]; if (!p) return;
      input.value = p.nombre; input.dataset.id = p.id;
      items = []; activo = -1; pintar();
    }
    input.addEventListener('input', () => {
      delete input.dataset.id;
      clearTimeout(timer);
      const q = input.value;
      if (!norm(q)) { items = []; pintar(); return; }
      timer = setTimeout(async () => {
        const n = ++pedido;
        const remotas = await API.suggest(q);
        if (n !== pedido) return; // llegó una respuesta vieja
        items = remotas || sugerirLocal(q); activo = -1; pintar();
      }, 200);
    });
    input.addEventListener('keydown', (e) => {
      if (lista.hidden) return;
      if (e.key === 'ArrowDown') { activo = (activo + 1) % items.length; pintar(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { activo = (activo - 1 + items.length) % items.length; pintar(); e.preventDefault(); }
      else if (e.key === 'Enter' && activo >= 0) { elegir(activo); e.preventDefault(); }
      else if (e.key === 'Escape') { items = []; pintar(); }
    });
    lista.addEventListener('mousedown', (e) => { const li = e.target.closest('li'); if (li) { elegir(+li.dataset.i); e.preventDefault(); } });
    input.addEventListener('blur', () => setTimeout(() => { items = []; pintar(); }, 100));
  }
  autocompletar($('#origen'));
  autocompletar($('#destino'));
  const idLugar = (input) => input.dataset.id || Engine.resolver(input.value);

  // ---------- Planeador ----------
  Reports.aplicarAlMotor();
  $('#btnBuscar').addEventListener('click', buscar);
  function buscar() {
    Reports.aplicarAlMotor();
    const oId = idLugar($('#origen'));
    const dId = idLugar($('#destino'));
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

  // ---------- Chat (asistente guiado / manual) ----------
  // Con backend: /chat/web (estado de conversación, pasos, LLM). Sin backend: ai.js local.
  const chatBody = $('#chatBody');
  const chips = $('#chatChips');
  function addMsg(texto, quien) {
    const d = document.createElement('div'); d.className = 'msg ' + quien; d.textContent = texto;
    chatBody.appendChild(d); chatBody.scrollTop = chatBody.scrollHeight;
  }
  function pintarChips(opciones) {
    chips.innerHTML = '';
    (opciones || []).forEach((o) => {
      const b = document.createElement('button'); b.className = 'chip'; b.textContent = o.label;
      b.addEventListener('click', () => enviarChat(o.label));
      chips.appendChild(b);
    });
  }
  async function responderChat(t) {
    const r = await API.chat(t);
    if (r) {
      addMsg(r.texto, 'bot'); pintarChips(r.opciones_rapidas);
      if (r.reporte) Realtime.publicar(incidenteLocal(r.reporte, 'Tú (chat)'));
      return;
    }
    const local = await AI.responder(t, 'web', 'Tú');
    addMsg(local.texto, 'bot'); pintarChips([]);
  }
  async function enviarChat(texto) {
    const input = $('#chatInput'); const t = (typeof texto === 'string' ? texto : input.value).trim(); if (!t) return;
    addMsg(t, 'me'); input.value = ''; pintarChips([]);
    await responderChat(t);
  }
  $('#chatSend').addEventListener('click', () => enviarChat());
  $('#chatInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') enviarChat(); });
  responderChat('hola');

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
        .addTo(mapa).bindPopup(`<b>📹 ${c.nombre}</b><br>Cámara de fotodetección (ubicación de referencia)`);
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
        .bindPopup(`<b>${t.icono} ${t.label}</b><br>${i.nota || ''}<br><small>${i.autor} · ${hace(i.ts)}</small>`);
    });
  }
  function pintarLeyenda() {
    $('#mapLegend').innerHTML = Object.values(MODOS)
      .map((m) => `<span class="leg" style="background:${m.color}">${m.icono} ${m.nombre}</span>`).join('')
      + '<span class="leg" style="background:#111">📹 Cámara de fotodetección</span>';
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
  // Incidente del backend -> formato del bus local (realtime.js) para el mapa y la lista
  function incidenteLocal(v, autor) {
    const t = Reports.TIPOS[v.tipo] || Reports.TIPOS.novedad;
    return { id: v.id, tipo: v.tipo, deId: v.de_id, aId: v.a_id, modo: v.modo, nota: v.nota, canal: 'web',
      autor, lat: v.lat, lng: v.lng, vidaMin: t.vidaMin, sev: t.sev, confianza: v.confianza, ts: Date.parse(v.creado_en) || Date.now() };
  }
  $('#btnReportar').addEventListener('click', async () => {
    const t = TRAMOS[+repTramo.value];
    const nota = $('#repNota').value;
    $('#repNota').value = '';
    // El feedback se guarda en el backend (Postgres) con tu identidad anónima; si no hay red, queda local.
    const r = await API.reportar({ tipo: repTipo.value, de_id: t.de, a_id: t.a, modo: t.modo, nota });
    if (r && r.ok) { Realtime.publicar(incidenteLocal(r.data, 'Tú (web)')); return; }
    if (r && r.status === 429) { toast('Ya reportaste esto hace poco 🙏'); return; }
    Reports.reportar({ tipo: repTipo.value, deId: t.de, aId: t.a, modo: t.modo, nota, canal: 'web', autor: 'Tú (web)' });
  });
  $('#btnLimpiar').addEventListener('click', () => { if (confirm('¿Limpiar todas las alertas? (solo para el demo)')) Realtime.limpiarTodo(); });
  function pintarReportes() {
    const lista = Realtime.vigentes(); const cont = $('#listaReportes');
    if (!lista.length) { cont.innerHTML = '<p class="empty">No hay alertas activas ahora mismo.</p>'; return; }
    cont.innerHTML = lista.map((i) => {
      const t = Reports.TIPOS[i.tipo] || Reports.TIPOS.novedad;
      const canalIco = i.canal === 'whatsapp' ? '💬' : i.canal === 'telegram' ? '✈️' : '🌐';
      const conf = i.confianza != null ? ` · confianza ${Math.round(i.confianza * 100)}%` : '';
      return `<div class="rep-item" style="border-left-color:${t.color}">${t.icono} <strong>${t.label}</strong>
        <br>${Engine.nodoPorId[i.deId].nombre} → ${Engine.nodoPorId[i.aId].nombre}
        ${i.nota ? '<br>“' + i.nota + '”' : ''}
        <br><small>${canalIco} ${i.autor} · ${hace(i.ts)}${conf}</small>
        <button class="voto" data-id="${i.id}">👍 ${i.votos || 0}</button></div>`;
    }).join('');
    $$('.voto').forEach((b) => b.addEventListener('click', () => {
      Realtime.votar(b.dataset.id);
      API.votar(b.dataset.id, 'confirma'); // si el incidente existe en el backend, suma confianza
    }));
  }
  function hace(ts) { const m = Math.round((Date.now() - ts) / 60000); return m < 1 ? 'ahora' : `hace ${m} min`; }

  // ---------- Reacción a incidentes en tiempo real ----------
  Realtime.suscribir((ev) => {
    Reports.aplicarAlMotor();
    if (ev.action === 'add' && ev.incidente) {
      const t = Reports.TIPOS[ev.incidente.tipo] || Reports.TIPOS.novedad;
      const canalIco = ev.incidente.canal === 'whatsapp' ? '💬 WhatsApp' : ev.incidente.canal === 'telegram' ? '✈️ Telegram' : '🌐 Web';
      toast(`<b>${t.icono} ${t.label}</b><br>${Engine.nodoPorId[ev.incidente.deId].nombre} → ${Engine.nodoPorId[ev.incidente.aId].nombre}<br><small>${canalIco} · ${ev.incidente.autor}</small>`, t.color);
    }
    pintarReportes();
    pintarIncidentes(Realtime.vigentes());
  });
  pintarReportes();

  // ---------- Service worker ----------
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
})();
