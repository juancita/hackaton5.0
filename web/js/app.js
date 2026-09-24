/*
 * app.js — Interfaz. Une planeador, asistente, mapa vivo (Waze) y reportes.
 * Vainilla JS + Leaflet. Usa el backend (api.js) si responde; si no, funciona offline
 * con engine.js / ai.js / realtime.js (degradación elegante).
 */
(() => {
  const { PARADEROS, MODOS, TRAMOS, CAMARAS } = window.DB;
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  // ---------- Navegación (hash routing: /#/rutas, /#/asistente, /#/reportar, /#/admin) ----------
  const SLUG_POR_VISTA = { plan: 'rutas', chat: 'asistente', report: 'reportar', admin: 'admin' };
  const VISTA_POR_SLUG = { rutas: 'plan', asistente: 'chat', chat: 'chat', reportar: 'report', admin: 'admin' };
  function mostrarVista(vista) {
    $$('.tabbar button').forEach((x) => x.classList.toggle('active', x.dataset.view === vista));
    $$('.view').forEach((v) => v.classList.remove('active'));
    $('#view-' + vista).classList.add('active');
    if (vista === 'plan') abrirMapa();
    if (vista === 'report') abrirReporte();
    if (vista === 'admin') pintarAdmin();
  }
  function aplicarRuta() {
    const slug = location.hash.replace(/^#\/?/, '').toLowerCase();
    mostrarVista(VISTA_POR_SLUG[slug] || 'plan');
  }
  $$('.tabbar button').forEach((b) => b.addEventListener('click', () => {
    location.hash = '#/' + SLUG_POR_VISTA[b.dataset.view];
  }));
  window.addEventListener('hashchange', aplicarRuta);

  // ---------- Layout responsive ----------
  // El mapa de Rutas queda fijo bajo la barra superior (móvil) y ocupa la altura libre (desktop).
  const esMovil = () => !matchMedia('(min-width: 860px)').matches;
  function medirTopbar() {
    document.documentElement.style.setProperty('--topbar-h', $('.topbar').offsetHeight + 'px');
    if (mapa) mapa.invalidateSize();
  }
  window.addEventListener('resize', medirTopbar);
  new ResizeObserver(medirTopbar).observe($('.topbar'));
  new ResizeObserver(() => mapa && mapa.invalidateSize()).observe($('#mapa'));

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

  // ---------- Conexión con el servidor ----------
  // Con servidor: rutas, reportes y alertas son compartidos por todos los dispositivos (Postgres).
  // Sin servidor: todo sigue funcionando en este dispositivo (engine.js + realtime.js).
  let enLinea = false;
  let incServidor = [];
  let firmaInc = null;
  async function revisarServidor() {
    const antes = enLinea;
    enLinea = await API.salud();
    const pill = $('#srvStatus');
    pill.textContent = enLinea ? '🟢 servidor' : '⚪ solo local';
    pill.title = enLinea ? `Conectado a ${API.base}` : `Sin servidor (${API.base}): funcionando solo en este dispositivo`;
    pill.classList.toggle('on', enLinea);
    if (enLinea !== antes) { firmaInc = null; await refrescarIncidentes(false); pintarPerfil(); pintarAdmin(); }
  }

  // Incidente del backend -> formato de la UI (el mismo que usa realtime.js)
  function incidenteLocal(v) {
    const t = Reports.TIPOS[v.tipo] || Reports.TIPOS.novedad;
    return { id: v.id, tipo: v.tipo, deId: v.de_id, aId: v.a_id, modo: v.modo, nota: v.nota, canal: 'web',
      autor: v.n_reportes > 1 ? `${v.n_reportes} vecinos` : 'Un vecino', lat: v.lat, lng: v.lng,
      vidaMin: t.vidaMin, sev: t.sev, ts: Date.parse(v.creado_en) || Date.now(), servidor: true,
      estado: v.estado, confianza: v.confianza, afecta: v.afecta_rutas,
      nReportes: v.n_reportes, nConfirma: v.n_confirma, nNiega: v.n_niega };
  }
  // Alertas visibles: las del servidor + las que solo existen en este dispositivo (p. ej. el simulador)
  function vigentes() {
    const locales = Realtime.vigentes();
    if (!enLinea) return locales;
    const ids = new Set(incServidor.map((i) => i.id));
    return [...incServidor.map(incidenteLocal), ...locales.filter((i) => !ids.has(i.id))];
  }
  async function refrescarIncidentes(avisar = true) {
    if (!enLinea) { pintarTodo(); return; }
    const lista = await API.incidentes();
    if (!lista) return;
    const firma = JSON.stringify(lista.map((i) => [i.id, i.confianza, i.estado, i.n_reportes, i.n_confirma, i.n_niega]));
    if (firma === firmaInc) return;
    const conocidos = new Set(incServidor.map((i) => i.id));
    if (avisar && firmaInc !== null) lista.filter((i) => !conocidos.has(i.id)).forEach((i) => toastIncidente(incidenteLocal(i), '🌐 Servidor'));
    firmaInc = firma;
    incServidor = lista;
    pintarTodo();
  }
  function pintarTodo() { pintarReportes(); pintarIncidentes(vigentes()); }
  function toastIncidente(i, origen) {
    const t = Reports.TIPOS[i.tipo] || Reports.TIPOS.novedad;
    toast(`<b>${t.icono} ${t.label}</b><br>${Engine.nodoPorId[i.deId].nombre} → ${Engine.nodoPorId[i.aId].nombre}<br><small>${origen} · ${i.autor}</small>`, t.color);
  }
  const detalle = (r) => {
    const d = r && r.data && r.data.detail;
    return typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg).join(', ') : 'No se pudo completar 😕';
  };

  // ---------- Planeador ----------
  Reports.aplicarAlMotor();
  $('#btnBuscar').addEventListener('click', buscar);
  $('#btnInvertir').addEventListener('click', () => {
    const o = $('#origen'), d = $('#destino');
    [o.value, d.value] = [d.value, o.value];
    const [idO, idD] = [o.dataset.id, d.dataset.id];
    if (idD) o.dataset.id = idD; else delete o.dataset.id;
    if (idO) d.dataset.id = idO; else delete d.dataset.id;
    if (o.value && d.value) buscar();
  });
  async function buscar() {
    const oId = idLugar($('#origen'));
    const dId = idLugar($('#destino'));
    const prioridad = $('#prioridad').value;
    const cont = $('#resultados');
    ocultarMapaRuta();
    if (!oId || !dId) { cont.innerHTML = '<p class="empty">Escribe un origen y un destino válidos 🙏</p>'; return; }
    if (oId === dId) { cont.innerHTML = '<p class="empty">El origen y el destino son iguales 😅</p>'; return; }

    if (enLinea) {
      cont.innerHTML = '<p class="empty">Buscando rutas…</p>';
      const r = await API.rutas(oId, dId, prioridad);
      if (r && r.ok) { pintarPlan(r.data.opciones, r.data.recomendada, r.data.incidentes_aplicados.length, 'servidor'); return; }
      if (r) { cont.innerHTML = `<p class="empty">${detalle(r)}</p>`; return; }
    }
    // Sin servidor: motor local con las alertas de este dispositivo
    Reports.aplicarAlMotor();
    const ops = Engine.opciones(oId, dId);
    pintarPlan(ops, Math.max(0, ops.findIndex((o) => o.prioridad === prioridad)), 0, 'local');
  }
  function pintarPlan(ops, recomendada, nIncidentes, fuente) {
    const cont = $('#resultados');
    opsPlan = ops;
    if (!ops.length) { ocultarMapaRuta(); cont.innerHTML = '<p class="empty">No encontré ruta entre esos puntos. Puede haber un tramo bloqueado por un reporte.</p>'; return; }
    const orden = [recomendada, ...ops.map((_, i) => i).filter((i) => i !== recomendada)];
    const aviso = nIncidentes ? `<p class="hint">⚠️ ${nIncidentes} alerta(s) ciudadana(s) afectan estas rutas.</p>` : '';
    const origen = fuente === 'servidor' ? '🟢 Calculado en el servidor con las alertas de toda la comunidad' : '⚪ Calculado en este dispositivo (sin servidor)';
    cont.innerHTML = aviso + orden.map((i) => tarjetaRuta(ops[i], i === recomendada, i)).join('') + `<p class="hint fuente">${origen}</p>`;
    elegirRuta(recomendada);
    // En móvil: sube hasta el mapa para ver la ruta y las tarjetas debajo
    if (esMovil()) {
      const y = $('#view-plan .plan-form').getBoundingClientRect().bottom + scrollY - $('.topbar').offsetHeight;
      window.scrollTo({ top: Math.max(0, y), behavior: 'smooth' });
    }
    else $('#view-plan .plan-panel').scrollTo({ top: 0, behavior: 'smooth' });
  }
  // Tocar una tarjeta la dibuja en el mapa
  $('#resultados').addEventListener('click', (e) => {
    const card = e.target.closest('.ruta-card[data-i]');
    if (card) elegirRuta(+card.dataset.i);
  });
  function elegirRuta(i) {
    $$('#resultados .ruta-card').forEach((c) => c.classList.toggle('seleccionada', +c.dataset.i === i));
    if (opsPlan[i]) dibujarRutaPlan(opsPlan[i]);
  }

  // ---------- Mapa de la ruta elegida ----------
  // Se dibuja sobre el mapa vivo del inicio; la red completa queda atenuada detrás.
  let opsPlan = [];
  function ocultarMapaRuta() {
    if (!capaRuta) return;
    capaRuta.clearLayers();
    atenuarRed(false);
  }
  function dibujarRutaPlan(op) {
    if (!capaRuta) return; // sin Leaflet (offline sin caché): solo las tarjetas
    capaRuta.clearLayers();
    atenuarRed(true);
    const coord = (id) => { const n = Engine.nodoPorId[id]; return n && [n.lat, n.lng]; };
    const puntos = [];
    op.tramos.forEach((tr) => {
      const m = MODOS[tr.modo];
      const paradas = tr.paradas || [tr.desde, tr.hasta];
      const linea = [];
      paradas.slice(1).forEach((id, k) => linea.push(...trazado(paradas[k], id, tr.modo, tr.ruta)));
      puntos.push(...linea);
      L.polyline(linea, { color: '#fff', weight: 9, opacity: 0.9 }).addTo(capaRuta);
      L.polyline(linea, { color: m.color, weight: 6, dashArray: m.formal ? null : '8,8' }).addTo(capaRuta)
        .bindPopup(`${m.icono} ${m.nombre} · <b>${tr.ruta}</b><br>${Engine.nodoPorId[tr.desde].nombre} → ${Engine.nodoPorId[tr.hasta].nombre}<br>${Math.round(tr.min)} min`);
      // Paradas intermedias del tramo
      paradas.slice(1, -1).map(coord).filter(Boolean)
        .forEach((p) => L.circleMarker(p, { radius: 4, color: m.color, weight: 2, fillColor: '#fff', fillOpacity: 1 }).addTo(capaRuta));
      // Si el trazado real no llega hasta el paradero, une a pie (punteado gris)
      [[coord(tr.desde), linea[0]], [linea[linea.length - 1], coord(tr.hasta)]].forEach(([a, b]) => {
        if (a && b && mapa.distance(a, b) > 20) L.polyline([a, b], { color: '#6B7280', weight: 3, dashArray: '2,6' }).addTo(capaRuta);
      });
    });
    // Transbordos, origen (A) y destino (B)
    op.tramos.slice(1).forEach((tr) => {
      const p = coord(tr.desde);
      if (p) L.circleMarker(p, { radius: 7, color: '#fff', weight: 2, fillColor: '#111', fillOpacity: 1 }).addTo(capaRuta)
        .bindPopup(`🔁 Transbordo en <b>${Engine.nodoPorId[tr.desde].nombre}</b>`);
    });
    const pin = (id, letra, color) => {
      const p = coord(id); if (!p) return;
      L.marker(p, { icon: L.divIcon({ className: '', html: `<div class="ruta-pin" style="background:${color}">${letra}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] }) })
        .addTo(capaRuta).bindPopup(`<b>${Engine.nodoPorId[id].nombre}</b>`);
    };
    pin(op.tramos[0].desde, 'A', '#16a34a');
    pin(op.tramos[op.tramos.length - 1].hasta, 'B', '#dc2626');
    if (puntos.length) mapa.fitBounds(L.latLngBounds(puntos), { padding: [30, 30], maxZoom: 16 });
    $('#mapa').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  function tarjetaRuta(op, recomendada, i) {
    const pasos = op.tramos.map((tr) => {
      const m = MODOS[tr.modo];
      const nOr = Engine.nodoPorId[tr.desde].nombre, nDe = Engine.nodoPorId[tr.hasta].nombre;
      const costo = tr.cop > 0 ? ` · $${tr.cop.toLocaleString('es-CO')}` : '';
      const alerta = tr.motivo ? `<div class="alerta">⚠️ ${tr.motivo}</div>` : '';
      const otras = alternativas(tr);
      const tambien = otras.length
        ? `<div class="tambien">También te sirven: ${otras.map((x) => `<b>${x.ruta}</b> (~${Math.round(x.min + x.freqMin / 2)} min, pasa cada ${x.freqMin})`).join(' · ')}</div>` : '';
      return `<div class="paso"><span class="ico">${m.icono}</span><div>
        <strong>${m.nombre}</strong> · ${tr.ruta}<br>${nOr} → ${nDe} · ${Math.round(tr.min)} min${costo}${alerta}${tambien}</div></div>`;
    }).join('');
    const badge = (op.usaInformal ? '<span class="ruta-badge">＋ informal</span>' : '')
      + (recomendada ? '<span class="ruta-badge reco">⭐ Recomendada</span>' : '');
    return `<div class="ruta-card ${op.usaInformal ? 'informal' : ''} ${recomendada ? 'recomendada' : ''}" data-i="${i}" title="Ver en el mapa">
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
    const escribiendo = document.createElement('div'); escribiendo.className = 'msg bot escribiendo'; escribiendo.textContent = '…';
    chatBody.appendChild(escribiendo); chatBody.scrollTop = chatBody.scrollHeight;
    const r = await API.chat(t);
    escribiendo.remove();
    if (r) {
      addMsg(r.texto, 'bot'); pintarChips(r.opciones_rapidas);
      if (r.reporte) { await refrescarIncidentes(false); pintarPerfil(); }
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
  let mapa = null, capaInc = null, capaOfi = null, capaRed = null, capaRuta = null, usandoSvg = false;
  function abrirMapa() {
    if (usandoSvg) { dibujarSvg(); return; }
    if (mapa) { setTimeout(() => mapa.invalidateSize(), 100); return; }
    if (typeof L === 'undefined') { activarSvgFallback(); return; }
    mapa = L.map('mapa', { zoomControl: true }).setView([4.575, -74.155], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18, attribution: '© OpenStreetMap',
    }).addTo(mapa);
    capaRed = L.layerGroup().addTo(mapa);
    dibujarRutas();
    dibujarCamaras();
    capaOfi = L.layerGroup().addTo(mapa);
    capaRuta = L.layerGroup().addTo(mapa);
    capaInc = L.layerGroup().addTo(mapa);
    pintarOficiales();
    pintarIncidentes(vigentes());
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
      L.polyline(t.geom || [[a.lat, a.lng], [b.lat, b.lng]], {
        color: MODOS[t.modo].color, weight: MODOS[t.modo].formal ? 4 : 3,
        opacity: 0.75, dashArray: MODOS[t.modo].formal ? null : '6,6',
      }).addTo(capaRed).bindPopup(`${MODOS[t.modo].icono} ${MODOS[t.modo].nombre}<br><b>${t.ruta}</b><br>${a.nombre} → ${b.nombre}`);
    });
    PARADEROS.forEach((p) => {
      L.circleMarker([p.lat, p.lng], { radius: 6, color: '#fff', weight: 2,
        fillColor: p.zona === 'rural' ? '#8B5A2B' : (p.tipo === 'cable' || p.tipo === 'portal' ? '#7B2FF7' : '#1B75BB'),
        fillOpacity: 1 }).addTo(capaRed).bindPopup(`<b>${p.nombre}</b><br>Zona ${p.zona}`);
    });
  }
  // Trazado de un tramo: el real (geom, por las calles) si lo tenemos; si no, línea recta entre paraderos
  function trazado(de, a, modo, ruta) {
    const t = TRAMOS.find((x) => x.modo === modo && x.ruta === ruta && ((x.de === de && x.a === a) || (x.de === a && x.a === de)));
    if (t && t.geom) return t.de === de ? t.geom : [...t.geom].reverse();
    return [de, a].map((id) => Engine.nodoPorId[id]).filter(Boolean).map((n) => [n.lat, n.lng]);
  }
  // Otras rutas del mismo modo que cubren el mismo trayecto (p. ej. varios buses UD → Hospital)
  function alternativas(tr) {
    if ((tr.paradas || []).length > 2) return [];
    return TRAMOS.filter((x) => x.modo === tr.modo && x.ruta !== tr.ruta
      && ((x.de === tr.desde && x.a === tr.hasta) || (x.de === tr.hasta && x.a === tr.desde)));
  }
  function atenuarRed(si) {
    capaRed.eachLayer((l) => l.setStyle(l instanceof L.CircleMarker
      ? { opacity: si ? 0.35 : 1, fillOpacity: si ? 0.35 : 1 } : { opacity: si ? 0.2 : 0.75 }));
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
      const tenue = i.servidor && !i.afecta ? ' tenue' : '';
      const icon = L.divIcon({ className: 'inc-icon', html: `<div class="inc-pin${tenue}" style="--c:${t.color}">${t.icono}</div>`, iconSize: [34, 34] });
      const conf = i.servidor ? `<br>Confianza ${Math.round(i.confianza * 100)}%${i.estado === 'verificado' ? ' · ✅ verificado' : ''}` : '';
      L.marker([i.lat, i.lng], { icon }).addTo(capaInc)
        .bindPopup(`<b>${t.icono} ${t.label}</b><br>${i.nota || ''}${conf}<br><small>${i.autor} · ${hace(i.ts)}</small>`);
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
    vigentes().forEach((i) => {
      const t = Reports.TIPOS[i.tipo]; const a = Engine.nodoPorId[i.deId], b = Engine.nodoPorId[i.aId];
      const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', cx); c.setAttribute('cy', cy); c.setAttribute('r', 2.4);
      c.setAttribute('fill', t.color); c.setAttribute('stroke', '#fff'); c.setAttribute('stroke-width', '.5');
      svg.appendChild(c);
    });
  }

  // ---------- Reportes (como Waze: el reporte queda donde estás) ----------
  // La ubicación sale del GPS; si no hay (http en la LAN, permiso negado, sin señal) el pin
  // arranca en el centro de Ciudad Bolívar y la persona lo ajusta tocando el mapa.
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const CENTRO_CB = [4.5800, -74.1580];
  const repTipo = $('#repTipo');
  repTipo.innerHTML = '<option value=""></option>' + Object.entries(Reports.TIPOS)
    .map(([k, v]) => `<option value="${k}">${v.icono} ${v.label}</option>`).join('');
  // Tipo de novedad como botones (un toque) sincronizados con el <select> oculto
  $('#repTipos').innerHTML = Object.entries(Reports.TIPOS).map(([k, v]) =>
    `<button type="button" class="tipo" role="radio" aria-checked="false" data-tipo="${k}" style="--c:${v.color}"><span>${v.icono}</span>${v.label}</button>`).join('');
  function marcarTipo(k) {
    repTipo.value = k;
    $$('#repTipos .tipo').forEach((b) => b.setAttribute('aria-checked', b.dataset.tipo === k));
    pintarEnvio();
  }
  $('#repTipos').addEventListener('click', (e) => { const b = e.target.closest('.tipo'); if (b) marcarTipo(b.dataset.tipo); });

  let repPos = null, repFuente = null, repCercano = null;
  let mapaRep = null, pinRep = null, capaTramoRep = null, circuloGps = null;
  function abrirReporte() {
    if (!mapaRep && typeof L !== 'undefined') {
      mapaRep = L.map('repMapa', { zoomControl: false, attributionControl: false }).setView(CENTRO_CB, 15);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(mapaRep);
      TRAMOS.forEach((t) => {
        const a = Engine.nodoPorId[t.de], b = Engine.nodoPorId[t.a];
        L.polyline(t.geom || [[a.lat, a.lng], [b.lat, b.lng]], { color: MODOS[t.modo].color, weight: 3, opacity: 0.35, interactive: false }).addTo(mapaRep);
      });
      capaTramoRep = L.layerGroup().addTo(mapaRep);
      pinRep = L.marker(CENTRO_CB, { draggable: true, autoPan: true,
        icon: L.divIcon({ className: 'rep-pin', html: '<div class="rep-pin-in"><span>📣</span></div>', iconSize: [40, 48], iconAnchor: [20, 46] }) }).addTo(mapaRep);
      pinRep.on('dragend', () => { const p = pinRep.getLatLng(); fijarPosicion(p.lat, p.lng, 'manual'); });
      mapaRep.on('click', (e) => fijarPosicion(e.latlng.lat, e.latlng.lng, 'manual'));
    } else if (typeof L === 'undefined') {
      $('.rep-mapa-wrap').hidden = true;
    }
    if (mapaRep) setTimeout(() => mapaRep.invalidateSize(), 80);
    if (!repPos) ubicar(false);
  }
  // forzar: el usuario pidió volver al GPS aunque haya movido el pin a mano
  function ubicar(forzar) {
    const gps = $('#repGps');
    if (!navigator.geolocation || !window.isSecureContext) {
      gps.textContent = '📍 Ubicación no disponible'; gps.classList.add('off');
      if (!repPos) fijarPosicion(...CENTRO_CB, 'centro');
      return;
    }
    gps.textContent = '📍 Ubicando…'; gps.classList.remove('off');
    if (!repPos) fijarPosicion(...CENTRO_CB, 'centro', null, true); // mientras llega el GPS
    // Si nadie responde el permiso, no dejamos el "Ubicando…" colgado
    setTimeout(() => { if (repFuente === 'centro' && gps.textContent.includes('Ubicando')) { gps.textContent = '📍 Toca para usar GPS'; gps.classList.add('off'); } }, 12000);
    navigator.geolocation.getCurrentPosition(
      (p) => { if (forzar || repFuente !== 'manual') fijarPosicion(p.coords.latitude, p.coords.longitude, 'gps', p.coords.accuracy); },
      () => {
        gps.textContent = '📍 Sin permiso de ubicación'; gps.classList.add('off');
        if (!repPos) fijarPosicion(...CENTRO_CB, 'centro');
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 });
  }
  $('#repGps').addEventListener('click', () => ubicar(true));
  pintarEnvio();

  function fijarPosicion(lat, lng, fuente, precision, esperandoGps) {
    repPos = { lat, lng }; repFuente = fuente;
    repCercano = Reports.tramoCercano(lat, lng);
    const gps = $('#repGps');
    if (esperandoGps) { /* conserva "Ubicando…" */ }
    else if (fuente === 'gps') { gps.textContent = `📍 GPS ±${Math.round(precision || 0)} m`; gps.classList.remove('off'); }
    else if (fuente === 'manual') { gps.textContent = '📍 Pin ajustado · usar GPS'; }
    if (mapaRep) {
      pinRep.setLatLng([lat, lng]);
      if (circuloGps) { circuloGps.remove(); circuloGps = null; }
      if (fuente === 'gps' && precision) circuloGps = L.circle([lat, lng], { radius: precision, color: '#1B75BB', weight: 1, fillOpacity: 0.1, interactive: false }).addTo(mapaRep);
      capaTramoRep.clearLayers();
      if (repCercano && repCercano.dist <= Reports.RADIO_M) {
        const t = repCercano.tramo, a = Engine.nodoPorId[t.de], b = Engine.nodoPorId[t.a];
        L.polyline(t.geom || [[a.lat, a.lng], [b.lat, b.lng]], { color: MODOS[t.modo].color, weight: 7, opacity: 0.9, interactive: false }).addTo(capaTramoRep);
      }
      if (fuente !== 'manual') mapaRep.setView([lat, lng], 16);
    }
    pintarDonde();
  }
  function pintarDonde() {
    const el = $('#repDonde');
    const fuera = !repCercano || repCercano.dist > Reports.RADIO_M;
    el.classList.toggle('fuera', fuera);
    if (!repPos) el.textContent = 'Activa tu ubicación para reportar.';
    else if (fuera) el.innerHTML = '⚠️ Estás lejos de las rutas de Ciudad Bolívar. <b>Mueve el pin</b> a la vía donde pasa la novedad.';
    else {
      const t = repCercano.tramo, m = MODOS[t.modo];
      const dist = repCercano.dist < 30 ? 'sobre la vía' : `a ${Math.round(repCercano.dist)} m`;
      el.innerHTML = `<span class="rep-donde-ico" style="--c:${m.color}">${m.icono}</span>
        <span><b>${m.nombre} · ${esc(t.ruta)}</b><br><small>${Engine.nodoPorId[t.de].nombre} ↔ ${Engine.nodoPorId[t.a].nombre} · ${dist}</small></span>`;
    }
    if (repFuente === 'centro' && !fuera) el.insertAdjacentHTML('beforeend', '<small class="rep-donde-aviso">Ubicación aproximada: ajusta el pin</small>');
    pintarEnvio();
  }
  function pintarEnvio() {
    const b = $('#btnReportar');
    const listo = repPos && repCercano && repCercano.dist <= Reports.RADIO_M;
    const t = Reports.TIPOS[repTipo.value];
    b.disabled = !listo || !t;
    b.textContent = !t ? 'Elige qué está pasando' : !listo ? 'Ubica el pin en una vía' : `Reportar ${t.icono} ${t.label}`;
  }

  $('#btnReportar').addEventListener('click', async () => {
    const tipo = repTipo.value, nota = $('#repNota').value.trim();
    if (!tipo || !repPos || !repCercano) return;
    const b = $('#btnReportar'); b.disabled = true; b.textContent = 'Enviando…';
    const listo = () => { $('#repNota').value = ''; marcarTipo(''); };
    if (enLinea) {
      // El feedback queda en el servidor (Postgres) con tu identidad anónima y tu peso de reputación
      const r = await API.reportar({ tipo, lat: repPos.lat, lng: repPos.lng, nota });
      if (r && r.ok) {
        const v = r.data;
        toast(v.afecta_rutas
          ? `✅ Reporte recibido · confianza ${Math.round(v.confianza * 100)}%. Ya afecta las rutas.`
          : `✅ Reporte recibido · confianza ${Math.round(v.confianza * 100)}%. Se aplicará cuando otros lo confirmen.`);
        listo(); await refrescarIncidentes(false); pintarPerfil();
        return;
      }
      if (r) { toast(r.status === 429 ? 'Ya reportaste esto hace poco 🙏' : detalle(r)); pintarEnvio(); return; }
    }
    const t = repCercano.tramo;
    Reports.reportar({ tipo, deId: t.de, aId: t.a, modo: t.modo, nota, canal: 'web', autor: 'Tú (web)', lat: repPos.lat, lng: repPos.lng });
    listo();
  });

  // Tarjeta de alerta: la pública lleva votos; la de admin, verificar / rechazar
  function tarjetaAlerta(i, modoAdmin) {
    const t = Reports.TIPOS[i.tipo] || Reports.TIPOS.novedad;
    const ruta = `${Engine.nodoPorId[i.deId].nombre} → ${Engine.nodoPorId[i.aId].nombre}`;
    const nota = i.nota ? `<p class="rep-nota">“${esc(i.nota)}”</p>` : '';
    const cabeza = (estado) => `<div class="rep-head"><span class="rep-ico">${t.icono}</span>
      <div class="rep-tit"><strong>${t.label}</strong><span class="rep-ruta">${ruta}</span></div>${estado}</div>`;
    if (!i.servidor) {
      const canalIco = i.canal === 'whatsapp' ? '💬' : i.canal === 'telegram' ? '✈️' : '🌐';
      return `<div class="rep-item" style="--c:${t.color}">${cabeza('')}${nota}
        <div class="rep-pie"><small>${canalIco} ${esc(i.autor)} · ${hace(i.ts)} · solo en este dispositivo</small>
        ${modoAdmin ? '' : `<button class="voto" data-accion="local" data-id="${i.id}">👍 ${i.votos || 0}</button>`}</div></div>`;
    }
    const pct = Math.round(i.confianza * 100);
    const estado = i.estado === 'verificado' ? '<span class="estado ok">✅ Verificado</span>'
      : i.afecta ? '<span class="estado">Afecta rutas</span>' : '<span class="estado bajo">Por confirmar</span>';
    const acciones = modoAdmin
      ? (i.estado !== 'verificado' ? `<button class="voto admin" data-accion="verificar" data-id="${i.id}">✅ Verificar</button>` : '')
        + `<button class="voto admin peligro" data-accion="rechazar" data-id="${i.id}">❌ Rechazar</button>`
      : `<button class="voto" data-accion="confirma" data-id="${i.id}">👍 Sigue ahí</button>
         <button class="voto" data-accion="niega" data-id="${i.id}">👎 Ya no está</button>`;
    return `<div class="rep-item" style="--c:${t.color}">${cabeza(estado)}${nota}
      <div class="conf"><span style="width:${pct}%;background:${pct >= 70 ? '#e74c3c' : pct >= 40 ? '#f39c12' : '#bbb'}"></span></div>
      <small>Confianza ${pct}% · ${i.autor} · ${hace(i.ts)} · 👍 ${i.nConfirma} · 👎 ${i.nNiega}</small>
      <div class="rep-acciones">${acciones}</div></div>`;
  }
  function pintarReportes() {
    const lista = vigentes(); const cont = $('#listaReportes');
    $('#repCount').textContent = lista.length === 1 ? '1 alerta' : `${lista.length} alertas`;
    cont.innerHTML = lista.length ? lista.map((i) => tarjetaAlerta(i, false)).join('')
      : '<p class="empty">✨ No hay alertas activas ahora mismo.<br><small>Si ves algo en la vía, repórtalo y avisamos a todos.</small></p>';
    pintarListaAdmin();
  }
  async function accionAlerta(e) {
    const b = e.target.closest('button[data-accion]'); if (!b) return;
    const { accion, id } = b.dataset;
    if (accion === 'local') { Realtime.votar(id); return; }
    b.disabled = true;
    const r = accion === 'verificar' ? await API.verificar(id)
      : accion === 'rechazar' ? await API.rechazar(id)
      : await API.votar(id, accion);
    const mensajes = { confirma: '👍 Gracias por confirmar', niega: '👎 Gracias, lo tendremos en cuenta',
      verificar: '✅ Alerta verificada', rechazar: '❌ Alerta rechazada' };
    toast(r && r.ok ? mensajes[accion] : detalle(r));
    await refrescarIncidentes(false); pintarPerfil();
  }
  $('#listaReportes').addEventListener('click', accionAlerta);
  $('#adminLista').addEventListener('click', accionAlerta);
  function hace(ts) { const m = Math.round((Date.now() - ts) / 60000); return m < 1 ? 'ahora' : `hace ${m} min`; }

  // ---------- Reputación (sin cuenta) ----------
  async function pintarPerfil() {
    const el = $('#perfil');
    const p = enLinea ? await API.perfil() : null;
    if (!p) { el.hidden = true; return; }
    el.hidden = false;
    if (p.rol === 'admin') {
      el.innerHTML = '🛡️ <strong>Administrador</strong><br><small>Tus reportes pesan 100% y quedan verificados al instante.</small>';
      return;
    }
    const rep = Math.round(p.reputacion * 100), peso = Math.round(p.peso * 100);
    el.innerHTML = `<strong>Tu reputación: ${rep}%</strong> · tus reportes pesan ${peso}%
      <div class="conf"><span style="width:${rep}%;background:#7B2FF7"></span></div>
      <small>✅ ${p.aciertos} acertados · ❌ ${p.fallos} descartados. Sin cuenta: te identificamos de forma anónima en este dispositivo.</small>`;
  }

  // ---------- Administrador (pestaña #/admin) ----------
  function pintarAdmin() {
    const activo = enLinea && API.esAdmin;
    $('#adminLogin').hidden = activo;
    $('#adminPanel').hidden = !activo;
    $('#adminOffline').hidden = enLinea;
    $('#adminKey').disabled = $('#btnAdmin').disabled = !enLinea;
    $('#btnLimpiar').hidden = !activo && enLinea;
    $('#btnLimpiar').textContent = enLinea ? '🗑️ Limpiar todas las alertas' : '🗑️ Limpiar alertas de este dispositivo';
    pintarListaAdmin();
  }
  function pintarListaAdmin() {
    if ($('#adminPanel').hidden) return;
    const lista = vigentes();
    const n = (f) => lista.filter(f).length;
    $('#adminStats').innerHTML = [
      ['Activas', lista.length],
      ['Por confirmar', n((i) => i.servidor && !i.afecta && i.estado !== 'verificado')],
      ['Verificadas', n((i) => i.estado === 'verificado')],
    ].map(([k, v]) => `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join('');
    // Primero lo que necesita decisión: por confirmar, luego activas, al final verificadas
    const orden = (i) => (i.estado === 'verificado' ? 2 : i.afecta ? 1 : 0);
    $('#adminLista').innerHTML = lista.length
      ? [...lista].sort((a, b) => orden(a) - orden(b)).map((i) => tarjetaAlerta(i, true)).join('')
      : '<p class="empty">✨ No hay alertas que moderar.</p>';
  }
  $('#adminForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const clave = $('#adminKey').value.trim(); if (!clave) return;
    $('#btnAdmin').disabled = true;
    API.setAdminKey(clave);
    $('#adminKey').value = '';
    const p = await API.perfil();
    if (!p || p.rol !== 'admin') { API.setAdminKey(''); toast('Clave incorrecta 🔒'); }
    else toast('🛡️ Modo admin activo');
    $('#btnAdmin').disabled = false;
    pintarAdmin(); pintarPerfil();
  });
  $('#btnSalirAdmin').addEventListener('click', () => {
    API.setAdminKey(''); toast('Saliste del modo admin');
    pintarAdmin(); pintarPerfil();
  });
  $('#btnLimpiar').addEventListener('click', async () => {
    if (!confirm('¿Limpiar todas las alertas?')) return;
    Realtime.limpiarTodo();
    if (enLinea && API.esAdmin) {
      const r = await API.limpiar();
      toast(r && r.ok ? `🗑️ ${r.data.eliminados} alerta(s) eliminadas del servidor` : detalle(r));
      await refrescarIncidentes(false);
    }
  });

  // ---------- Reacción a incidentes en tiempo real ----------
  // Locales (misma máquina / simulador) por el bus; los del servidor llegan por sondeo cada 5 s.
  Realtime.suscribir((ev) => {
    Reports.aplicarAlMotor();
    if (ev.action === 'add' && ev.incidente) {
      const canal = ev.incidente.canal === 'whatsapp' ? '💬 WhatsApp' : ev.incidente.canal === 'telegram' ? '✈️ Telegram' : '🌐 Web';
      toastIncidente(ev.incidente, canal);
    }
    pintarTodo();
  });
  abrirMapa();
  aplicarRuta();
  pintarTodo();
  revisarServidor();
  setInterval(() => { if (enLinea) refrescarIncidentes(); }, 5000);
  setInterval(revisarServidor, 15000);

  // ---------- Service worker ----------
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
})();
