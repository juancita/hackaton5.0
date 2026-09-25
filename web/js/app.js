/*
 * app.js — Interfaz. Une planeador, asistente, mapa vivo (Waze) y reportes.
 * Vainilla JS + Leaflet. Usa el backend (api.js) si responde; si no, funciona offline
 * con engine.js / ai.js para rutas y chat; los reportes siempre van al servidor.
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
    if (vista === 'report') { abrirReporte(); vigilarFeed(); }
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
  // Logo → inicio (si ya estás en Rutas, el hash no cambia: solo sube al inicio)
  $('.topbar .brand').addEventListener('click', () => scrollTo({ top: 0, behavior: 'smooth' }));

  // FAB de Telegram: se encoge al bajar (leyendo rutas) y vuelve a extenderse al subir
  const tgFab = $('#tgFab');
  let ultimoY = scrollY;
  window.addEventListener('scroll', () => {
    const y = scrollY;
    if (Math.abs(y - ultimoY) < 8) return;
    tgFab.classList.toggle('mini', y > ultimoY && y > 80);
    ultimoY = y;
  }, { passive: true });

  // ---------- Layout responsive ----------
  // El mapa de Rutas queda fijo bajo la barra superior (móvil) y ocupa la altura libre (desktop).
  const esMovil = () => !matchMedia('(min-width: 860px)').matches;
  function medirTopbar() {
    document.documentElement.style.setProperty('--topbar-h', $('.topbar').offsetHeight + 'px');
    // Alto real de la barra inferior (incluye safe-area) para que el chat no quede tapado ni deje hueco
    document.documentElement.style.setProperty('--tabbar-real', $('.tabbar').offsetHeight + 'px');
    if (mapa) mapa.invalidateSize();
  }
  window.addEventListener('resize', medirTopbar);
  new ResizeObserver(medirTopbar).observe($('.topbar'));
  new ResizeObserver(medirTopbar).observe($('.tabbar'));
  new ResizeObserver(() => mapa && mapa.invalidateSize()).observe($('#mapa'));


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

  // ---------- Origen desde la ubicación del dispositivo (GPS) ----------
  // Toma la posición del navegador y elige el paradero más cercano como origen.
  // En http de LAN (sin GPS) usa la ubicación de desarrollo (misma que los reportes).
  const btnOrigenGps = $('#origenGps');
  function paraderoCercano(lat, lng) {
    const R = 6371000, rad = (d) => d * Math.PI / 180;
    let mejor = null;
    PARADEROS.forEach((p) => {
      if (typeof p.lat !== 'number' || typeof p.lng !== 'number') return;
      const dLat = rad(p.lat - lat), dLng = rad(p.lng - lng);
      const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(lat)) * Math.cos(rad(p.lat)) * Math.sin(dLng / 2) ** 2;
      const d = 2 * R * Math.asin(Math.sqrt(a));
      if (!mejor || d < mejor.d) mejor = { p, d };
    });
    return mejor;
  }
  function usarUbicacionOrigen(lat, lng) {
    const c = paraderoCercano(lat, lng);
    btnOrigenGps.classList.remove('cargando');
    if (!c) { toast('No encontré un paradero cercano a tu ubicación.'); return; }
    const inp = $('#origen'); inp.value = c.p.nombre; inp.dataset.id = c.p.id;
    btnOrigenGps.classList.add('ok');
    const dist = c.d >= 1000 ? `${(c.d / 1000).toFixed(1)} km` : `${Math.round(c.d)} m`;
    toast(`${ico('my_location')} Origen: <b>${esc(c.p.nombre)}</b><br><small>El paradero más cercano a tu ubicación (a ${dist})</small>`);
    // Si ya hay destino, calcula la ruta de una vez
    if (idLugar($('#destino'))) buscar();
  }
  btnOrigenGps.addEventListener('click', () => {
    if (btnOrigenGps.classList.contains('cargando')) return;
    btnOrigenGps.classList.remove('ok');
    btnOrigenGps.classList.add('cargando');
    if (MODO_DEV_HTTP) { usarUbicacionOrigen(UBICACION_DEV[0], UBICACION_DEV[1]); return; }
    if (!navigator.geolocation) { btnOrigenGps.classList.remove('cargando'); toast('Tu navegador no permite acceder a la ubicación.'); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => usarUbicacionOrigen(pos.coords.latitude, pos.coords.longitude),
      (err) => {
        btnOrigenGps.classList.remove('cargando');
        toast(err && err.code === 1
          ? 'Permiso de ubicación denegado. Actívalo para usar tu GPS.'
          : 'No pude obtener tu ubicación. Intenta de nuevo o escribe el origen.');
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 30000 }
    );
  });

  // ---------- Conexión con el servidor ----------
  // Con servidor: rutas, reportes y alertas son compartidos por todos los dispositivos (Postgres).
  // Sin servidor: rutas y chat funcionan en este dispositivo (engine.js + ai.js); reportes no.
  let enLinea = false;
  let incServidor = [];
  let incRecientes = []; // últimos reportes guardados en Postgres (vigentes y vencidos), para el mapa
  let firmaInc = null;
  async function revisarServidor() {
    const antes = enLinea;
    enLinea = await API.salud();
    if (enLinea !== antes) { firmaInc = null; await refrescarIncidentes(false); pintarPerfil(); pintarAdmin(); pintarEnvio(); vigilarFeed(); }
  }

  // Incidente del backend -> formato de la UI
  function incidenteLocal(v) {
    const t = Reports.TIPOS[v.tipo] || Reports.TIPOS.novedad;
    return { id: v.id, tipo: v.tipo, deId: v.de_id, aId: v.a_id, modo: v.modo, nota: v.nota, canal: 'web',
      autor: v.n_reportes > 1 ? `${v.n_reportes} vecinos` : 'Un vecino', lat: v.lat, lng: v.lng,
      vidaMin: t.vidaMin, sev: t.sev, ts: Date.parse(v.creado_en) || Date.now(), servidor: true,
      estado: v.estado, confianza: v.confianza, afecta: v.afecta_rutas, vigente: v.vigente !== false,
      nReportes: v.n_reportes, nConfirma: v.n_confirma, nNiega: v.n_niega, estrellasAutor: v.estrellas_autor,
      // El servidor marca, para quien consulta (X-Client-Id), si el reporte es suyo y cómo lo calificó
      esMio: !!v.es_mio, miVoto: v.mi_voto || null };
  }
  // Alertas vigentes: solo las del servidor (Postgres). Sin conexión no hay alertas que mostrar.
  function vigentes() {
    return enLinea ? incServidor.map(incidenteLocal) : [];
  }
  async function refrescarIncidentes(avisar = true) {
    if (!enLinea) { pintarTodo(); return; }
    // Los últimos reportes guardados de la misma ventana que muestra el mapa (1 h)
    const [lista, ultimos] = await Promise.all([API.incidentes(), API.recientes({ horas: 1, limit: 50 })]);
    if (!lista) return;
    const firma = JSON.stringify([lista, ultimos || []].map((l) => l.map((i) => [i.id, i.confianza, i.estado, i.n_reportes, i.n_confirma, i.n_niega, i.vigente, i.es_mio, i.mi_voto])));
    if (firma === firmaInc) return;
    const conocidos = new Set(incServidor.map((i) => i.id));
    if (avisar && firmaInc !== null) lista.filter((i) => !conocidos.has(i.id)).forEach((i) => toastIncidente(incidenteLocal(i), `${ico('cloud')} Servidor`));
    firmaInc = firma;
    incServidor = lista;
    if (ultimos) incRecientes = ultimos;
    pintarTodo();
  }
  // Mapa de rutas: los últimos reportes guardados en el servidor (los vencidos, atenuados)
  function paraMapa() {
    return enLinea ? incRecientes.map(incidenteLocal) : [];
  }
  function pintarTodo() { pintarReportes(); pintarIncidentes(paraMapa()); }

  // ---------- Feed "Alertas en vivo": la última hora; al bajar se cargan las anteriores ----------
  const PAGINA_FEED = 10;
  let feedMas = [], feedFin = false, feedCargando = false;
  function listaFeed() {
    if (!enLinea) return [];
    const vistos = new Set(), out = [];
    [...incRecientes, ...feedMas].forEach((v) => { if (!vistos.has(v.id)) { vistos.add(v.id); out.push(incidenteLocal(v)); } });
    return out.sort((a, b) => b.ts - a.ts);
  }
  async function cargarMasFeed() {
    if (!enLinea || feedFin || feedCargando) return;
    feedCargando = true; pintarFinFeed();
    const servidor = [...incRecientes, ...feedMas];
    const antes = servidor.length
      ? servidor.reduce((m, v) => (v.creado_en < m ? v.creado_en : m), servidor[0].creado_en)
      : new Date().toISOString();
    const pag = await API.recientes({ antes, limit: PAGINA_FEED });
    feedCargando = false;
    if (pag) { feedMas.push(...pag); feedFin = pag.length < PAGINA_FEED; pintarReportes(); }
    pintarFinFeed();
    if (pag && !feedFin) vigilarFeed();
  }
  function pintarFinFeed() {
    const el = $('#feedMas');
    el.hidden = !enLinea;
    el.innerHTML = feedCargando ? 'Cargando alertas anteriores…'
      : feedFin ? `${ico('history')} No hay más alertas` : `${ico('expand_more')} Desliza para ver alertas anteriores`;
  }
  // Actualiza en el feed un incidente que cambió (p. ej. tras un voto) sin esperar al sondeo
  function actualizarEnFeed(v) {
    [incRecientes, feedMas].forEach((l) => { const k = l.findIndex((x) => x.id === v.id); if (k >= 0) l[k] = v; });
  }
  const obsFeed = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) cargarMasFeed(); }, { rootMargin: '200px' });
  // Volver a observar dispara el callback si el final de la lista ya está a la vista (lista corta)
  function vigilarFeed() { obsFeed.unobserve($('#feedMas')); obsFeed.observe($('#feedMas')); }
  vigilarFeed();
  function toastIncidente(i, origen) {
    const t = Reports.TIPOS[i.tipo] || Reports.TIPOS.novedad;
    toast(`<b>${icoTipo(i.tipo)} ${t.label}</b><br>${Engine.nodoPorId[i.deId].nombre} → ${Engine.nodoPorId[i.aId].nombre}<br><small>${origen} · ${i.autor}</small>`, t.color);
  }
  const detalle = (r) => {
    const d = r && r.data && r.data.detail;
    return typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg).join(', ') : 'No se pudo completar';
  };

  // ---------- Planeador ----------
  $('#btnBuscar').addEventListener('click', buscar);
  $('#btnInvertir').addEventListener('click', () => {
    const o = $('#origen'), d = $('#destino');
    [o.value, d.value] = [d.value, o.value];
    const [idO, idD] = [o.dataset.id, d.dataset.id];
    if (idD) o.dataset.id = idD; else delete o.dataset.id;
    if (idO) d.dataset.id = idO; else delete d.dataset.id;
    if (o.value && d.value) buscar();
  });
  // Medios de transporte marcados (cada casilla puede agrupar varios modos, p. ej. "sitp,alimentador").
  // null = todos marcados (sin filtro). Caminar siempre se permite.
  function mediosElegidos() {
    const cajas = [...$$('#medios input')];
    const marcadas = cajas.filter((c) => c.checked);
    if (marcadas.length === cajas.length) return null;
    return marcadas.flatMap((c) => c.value.split(','));
  }
  // Cambiar los medios con resultados en pantalla vuelve a buscar
  $('#medios').addEventListener('change', () => { if (opsPlan.length || $('#resultados').textContent.trim()) buscar(); });
  async function buscar() {
    const oId = idLugar($('#origen'));
    const dId = idLugar($('#destino'));
    const prioridad = $('#prioridad').value;
    const cont = $('#resultados');
    ocultarMapaRuta();
    if (!oId || !dId) { cont.innerHTML = '<p class="empty">Escribe un origen y un destino válidos.</p>'; return; }
    if (oId === dId) { cont.innerHTML = '<p class="empty">El origen y el destino son iguales.</p>'; return; }
    const modos = mediosElegidos();
    if (modos && !modos.length) { opsPlan = []; cont.innerHTML = '<p class="empty">Marca al menos un medio de transporte.</p>'; return; }

    if (enLinea) {
      cont.innerHTML = '<p class="empty">Buscando rutas…</p>';
      const r = await API.rutas(oId, dId, prioridad, modos);
      if (r && r.ok) { pintarPlan(r.data.opciones, r.data.recomendada, r.data.incidentes_aplicados.length, 'servidor'); return; }
      if (r) { cont.innerHTML = `<p class="empty">${detalle(r)}</p>`; return; }
    }
    // Sin servidor: motor local, sin alertas (las alertas viven en el servidor)
    const ops = Engine.opciones(oId, dId, modos, prioridad);
    pintarPlan(ops, Math.max(0, ops.findIndex((o) => o.prioridad === prioridad && !/^(Sin|Con) /.test(o.etiqueta))), 0, 'local');
  }
  function pintarPlan(ops, recomendada, nIncidentes, fuente) {
    const cont = $('#resultados');
    opsPlan = ops;
    if (!ops.length) {
      ocultarMapaRuta();
      cont.innerHTML = mediosElegidos()
        ? '<p class="empty">No encontré ruta con los medios que marcaste. Prueba marcando otro medio.</p>'
        : '<p class="empty">No encontré ruta entre esos puntos. Puede haber un tramo bloqueado por un reporte.</p>';
      return;
    }
    const orden = [recomendada, ...ops.map((_, i) => i).filter((i) => i !== recomendada)];
    const aviso = nIncidentes ? `<p class="hint aviso-ruta">${ico('warning')} ${nIncidentes} alerta(s) ciudadana(s) afectan estas rutas.</p>` : '';
    const origen = fuente === 'servidor' ? `${ico('cloud_done')} Calculado en el servidor con las alertas de toda la comunidad` : `${ico('smartphone')} Calculado en este dispositivo (sin servidor)`;
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
  // Se dibuja sobre el mapa vivo, junto a los reportes de la última hora.
  let opsPlan = [];
  function ocultarMapaRuta() {
    if (!capaRuta) return;
    capaRuta.clearLayers();
  }
  function dibujarRutaPlan(op) {
    if (!capaRuta) return; // sin Leaflet (offline sin caché): solo las tarjetas
    capaRuta.clearLayers();
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
        .bindPopup(`${icoModo(tr.modo)} ${m.nombre} · <b>${tr.ruta}</b><br>${Engine.nodoPorId[tr.desde].nombre} → ${Engine.nodoPorId[tr.hasta].nombre}<br>${Math.round(tr.min)} min`);
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
        .bindPopup(`${ico('sync_alt')} Transbordo en <b>${Engine.nodoPorId[tr.desde].nombre}</b>`);
    });
    const pin = (id, letra, color) => {
      const p = coord(id); if (!p) return;
      L.marker(p, { icon: L.divIcon({ className: '', html: `<div class="ruta-pin" style="background:${color}">${letra}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] }) })
        .addTo(capaRuta).bindPopup(`<b>${Engine.nodoPorId[id].nombre}</b>`);
    };
    pin(op.tramos[0].desde, 'A', '#1A6B00');
    pin(op.tramos[op.tramos.length - 1].hasta, 'B', '#8A0000');
    if (puntos.length) mapa.fitBounds(L.latLngBounds(puntos), { padding: [30, 30], maxZoom: 16 });
    $('#mapa').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  function tarjetaRuta(op, recomendada, i) {
    const pasos = op.tramos.map((tr) => {
      const m = MODOS[tr.modo];
      const nOr = Engine.nodoPorId[tr.desde].nombre, nDe = Engine.nodoPorId[tr.hasta].nombre;
      const costo = tr.cop > 0 ? ` · $${tr.cop.toLocaleString('es-CO')}` : '';
      const alerta = tr.motivo ? `<div class="alerta">${ico('warning')} ${sinEmoji(tr.motivo)}</div>` : '';
      const otras = alternativas(tr);
      const tambien = otras.length
        ? `<div class="tambien">También te sirven: ${otras.map((x) => `<b>${x.ruta}</b> (~${Math.round(x.min + x.freqMin / 2)} min, pasa cada ${x.freqMin})`).join(' · ')}</div>` : '';
      return `<div class="paso"><span class="ico" style="--c:${m.color}">${icoModo(tr.modo)}</span><div>
        <strong>${m.nombre}</strong> · ${tr.ruta}<br>${nOr} → ${nDe} · ${Math.round(tr.min)} min${costo}${alerta}${tambien}</div></div>`;
    }).join('');
    const badge = (op.usaInformal ? `<span class="ruta-badge">${ico('add')}informal</span>` : '')
      + (recomendada ? `<span class="ruta-badge reco">${ico('star', 'fill')}Recomendada</span>` : '');
    return `<div class="ruta-card ${op.usaInformal ? 'informal' : ''} ${recomendada ? 'recomendada' : ''}" data-i="${i}" title="Ver en el mapa">
      <div class="ruta-head"><span class="ruta-etiqueta">${op.etiqueta}</span>${badge}</div>${pasos}
      <div class="totales"><span>${ico('schedule')}${op.totalMin} min</span><span>${ico('payments')}$${op.totalCop.toLocaleString('es-CO')}</span><span title="Transbordos">${ico('sync_alt')}${op.transbordos}</span></div>
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
  // Mapa de la ruta (imagen del backend) y enlace a Google Maps, dentro del chat
  function addMapa(m) {
    const d = document.createElement('div'); d.className = 'msg bot msg-mapa';
    const img = document.createElement('img'); img.src = API.urlMapa(m); img.alt = 'Mapa de la ruta: A es el origen y B el destino';
    img.loading = 'lazy'; img.addEventListener('load', () => { chatBody.scrollTop = chatBody.scrollHeight; });
    const a = document.createElement('a'); a.href = m.google_maps; a.target = '_blank'; a.rel = 'noopener';
    a.textContent = '🗺️ Abrir la ruta en Google Maps';
    d.append(img, a); chatBody.appendChild(d); chatBody.scrollTop = chatBody.scrollHeight;
  }
  // El chip de ubicación pide la posición al navegador en vez de mandar el texto del botón
  function enviarUbicacion(o) {
    if (!navigator.geolocation) { enviarChat(o.label); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        addMsg('📍 Mi ubicación', 'me'); pintarChips([]);
        responderChat('', { lat: pos.coords.latitude, lng: pos.coords.longitude });
      },
      () => enviarChat(o.label), // sin permiso: el asistente explica otras formas
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }
  function pintarChips(opciones) {
    chips.innerHTML = '';
    (opciones || []).forEach((o) => {
      const b = document.createElement('button'); b.className = 'chip'; b.textContent = o.label;
      b.addEventListener('click', () => (o.id === 'ubicacion' ? enviarUbicacion(o) : enviarChat(o.label)));
      chips.appendChild(b);
    });
  }
  async function responderChat(t, ubicacion) {
    const escribiendo = document.createElement('div'); escribiendo.className = 'msg bot escribiendo'; escribiendo.textContent = '…';
    chatBody.appendChild(escribiendo); chatBody.scrollTop = chatBody.scrollHeight;
    const r = await API.chat(t, ubicacion);
    escribiendo.remove();
    if (r) {
      addMsg(r.texto, 'bot'); if (r.mapa) addMapa(r.mapa); pintarChips(r.opciones_rapidas);
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

  // ---------- MAPA VIVO (Leaflet, tipo Waze) ----------
  // Solo muestra los reportes de la comunidad de la última hora y la ruta elegida por la persona.
  const VENTANA_MAPA_MS = 60 * 60 * 1000;
  const recientes = (lista) => lista.filter((i) => Date.now() - i.ts <= VENTANA_MAPA_MS);
  let mapa = null, capaInc = null, capaRuta = null, usandoSvg = false;
  function abrirMapa() {
    if (usandoSvg) { dibujarSvg(); return; }
    if (mapa) { setTimeout(() => mapa.invalidateSize(), 100); return; }
    if (typeof L === 'undefined') { activarSvgFallback(); return; }
    mapa = L.map('mapa', { zoomControl: true }).setView([4.575, -74.155], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18, attribution: '© OpenStreetMap',
    }).addTo(mapa);
    capaRuta = L.layerGroup().addTo(mapa);
    capaInc = L.layerGroup().addTo(mapa);
    pintarIncidentes(paraMapa());
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
  function pintarIncidentes(todas) {
    const lista = recientes(todas);
    const activas = lista.filter((i) => i.vigente !== false).length;
    const vencidas = lista.length - activas;
    $('#incCount').textContent = `${activas} ${activas === 1 ? 'alerta activa' : 'alertas activas'}`
      + (vencidas ? ` · ${vencidas} reciente${vencidas === 1 ? '' : 's'}` : '');
    if (usandoSvg) { dibujarSvg(); return; }
    if (!capaInc) return;
    capaInc.clearLayers();
    lista.forEach((i) => {
      const t = Reports.TIPOS[i.tipo] || Reports.TIPOS.novedad;
      const vencido = i.vigente === false;
      const clase = vencido ? ' vencido' : i.servidor && !i.afecta ? ' tenue' : '';
      const icon = L.divIcon({ className: 'inc-icon', html: `<div class="inc-pin${clase}" style="--c:${t.color}">${icoTipo(i.tipo)}</div>`, iconSize: [34, 34] });
      const conf = vencido ? '<br><small>Ya no está vigente</small>'
        : i.servidor ? `<br>Confianza ${Math.round(i.confianza * 100)}%${i.estado === 'verificado' ? ` · ${ico('verified')} verificado` : ''}` : '';
      // Los vencidos quedan debajo: lo vigente siempre se ve encima
      L.marker([i.lat, i.lng], { icon, zIndexOffset: vencido ? -1000 : 0 }).addTo(capaInc)
        .bindPopup(`<b>${icoTipo(i.tipo)} ${t.label}</b><br>${esc(i.nota || '')}${conf}<br><small>${esc(i.autor)} · ${hace(i.ts)}</small>`);
    });
  }
  function pintarLeyenda() {
    $('#mapLegend').innerHTML = Object.entries(MODOS)
      .map(([k, m]) => `<span class="leg" style="background:${m.color}">${icoModo(k)}${m.nombre}</span>`).join('');
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
    recientes(vigentes()).forEach((i) => {
      const t = Reports.TIPOS[i.tipo]; const a = Engine.nodoPorId[i.deId], b = Engine.nodoPorId[i.aId];
      const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', cx); c.setAttribute('cy', cy); c.setAttribute('r', 2.4);
      c.setAttribute('fill', t.color); c.setAttribute('stroke', '#fff'); c.setAttribute('stroke-width', '.5');
      svg.appendChild(c);
    });
  }

  // ---------- Reportes (como Waze: el reporte queda EXACTAMENTE donde estás) ----------
  // Solo se reporta en la ubicación real del GPS: el pin no se mueve a mano. Sin GPS (permiso
  // negado, página sin https, sin señal) o sin servidor (Postgres) no se puede enviar.
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const CENTRO_CB = [4.5800, -74.1580];
  // Staging de desarrollo por http (IP de la red local): el navegador no entrega el GPS fuera de
  // https, así que se usa una ubicación fija sobre una vía (Portal Tunal ↔ Perdomo) para poder probar.
  // Se cambia con localStorage 'muevecb_ubicacion_dev' = '4.5802,-74.1574' o window.MUEVECB_UBICACION_DEV.
  // En https (producción) nunca se usa: ahí manda el GPS real.
  const MODO_DEV_HTTP = !window.isSecureContext;
  const UBICACION_DEV = (() => {
    let v = window.MUEVECB_UBICACION_DEV;
    try { v = localStorage.getItem('muevecb_ubicacion_dev') || v; } catch (e) {}
    const [lat, lng] = (Array.isArray(v) ? v : String(v || '').split(',')).map(Number);
    return Number.isFinite(lat) && Number.isFinite(lng) ? [lat, lng] : [4.5802, -74.1574];
  })();
  const PRECISION_MAX_M = 500; // con una ubicación más imprecisa no sabemos en qué vía estás
  const repTipo = $('#repTipo');
  repTipo.innerHTML = '<option value=""></option>' + Object.entries(Reports.TIPOS)
    .map(([k, v]) => `<option value="${k}">${v.label}</option>`).join('');
  // Tipo de novedad como botones (un toque) sincronizados con el <select> oculto
  $('#repTipos').innerHTML = Object.entries(Reports.TIPOS).map(([k, v]) =>
    `<button type="button" class="tipo" role="radio" aria-checked="false" data-tipo="${k}" style="--c:${v.color}">${icoTipo(k)}${v.label}</button>`).join('');
  function marcarTipo(k) {
    repTipo.value = k;
    $$('#repTipos .tipo').forEach((b) => b.setAttribute('aria-checked', b.dataset.tipo === k));
    pintarEnvio();
  }
  $('#repTipos').addEventListener('click', (e) => { const b = e.target.closest('.tipo'); if (b) marcarTipo(b.dataset.tipo); });

  // repError: null | 'sin-gps' | 'permiso' | 'senal'
  let repPos = null, repPrecision = 0, repCercano = null, repError = null, watchGps = null;
  let mapaRep = null, pinRep = null, capaTramoRep = null, circuloGps = null;
  function abrirReporte() {
    if (!mapaRep && typeof L !== 'undefined') {
      mapaRep = L.map('repMapa', { zoomControl: false, attributionControl: false }).setView(CENTRO_CB, 14);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(mapaRep);
      TRAMOS.forEach((t) => {
        const a = Engine.nodoPorId[t.de], b = Engine.nodoPorId[t.a];
        L.polyline(t.geom || [[a.lat, a.lng], [b.lat, b.lng]], { color: MODOS[t.modo].color, weight: 3, opacity: 0.35, interactive: false }).addTo(mapaRep);
      });
      capaTramoRep = L.layerGroup().addTo(mapaRep);
      // Punto azul "estás aquí": se mueve solo con el GPS, no se arrastra ni se ubica tocando el mapa
      pinRep = L.marker(CENTRO_CB, { interactive: false, keyboard: false,
        icon: L.divIcon({ className: 'yo-marker', html: '<span class="yo-dot"></span>', iconSize: [22, 22], iconAnchor: [11, 11] }) });
      if (repPos) fijarPosicion(repPos.lat, repPos.lng, repPrecision);
    } else if (typeof L === 'undefined') {
      $('.rep-mapa-wrap').hidden = true;
    }
    if (mapaRep) setTimeout(() => mapaRep.invalidateSize(), 80);
    if (watchGps === null && !repPos) ubicar();
  }
  const gpsTexto = (el, txt) => { el.innerHTML = ico('my_location') + esc(txt); };
  // Sigue la ubicación: si caminas, el reporte sale de donde estés en ese momento
  function ubicar() {
    const gps = $('#repGps');
    if (watchGps !== null) { navigator.geolocation.clearWatch(watchGps); watchGps = null; }
    if (MODO_DEV_HTTP) {
      repError = null;
      fijarPosicion(...UBICACION_DEV, 0);
      gpsTexto(gps, 'Ubicación de prueba (dev)'); gps.classList.add('off');
      return;
    }
    repError = !navigator.geolocation ? 'sin-gps' : null;
    if (repError) { gpsTexto(gps, 'Ubicación no disponible'); gps.classList.add('off'); pintarDonde(); return; }
    gpsTexto(gps, 'Ubicando…'); gps.classList.remove('off');
    pintarDonde();
    watchGps = navigator.geolocation.watchPosition(
      (p) => { repError = null; fijarPosicion(p.coords.latitude, p.coords.longitude, p.coords.accuracy); },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          navigator.geolocation.clearWatch(watchGps); watchGps = null;
          repError = 'permiso'; repPos = null;
          if (pinRep && mapaRep) { pinRep.remove(); capaTramoRep.clearLayers(); if (circuloGps) { circuloGps.remove(); circuloGps = null; } }
          gpsTexto(gps, 'Sin permiso · reintentar');
        } else {
          if (!repPos) repError = 'senal';
          gpsTexto(gps, repPos ? `GPS ±${Math.round(repPrecision)} m` : 'Sin señal · reintentar');
        }
        gps.classList.toggle('off', !repPos);
        pintarDonde();
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 });
  }
  $('#repGps').addEventListener('click', ubicar);

  function fijarPosicion(lat, lng, precision) {
    const primera = !repPos;
    repPos = { lat, lng }; repPrecision = precision || 0;
    repCercano = Reports.tramoCercano(lat, lng);
    const gps = $('#repGps');
    gpsTexto(gps, `GPS ±${Math.round(repPrecision)} m`); gps.classList.remove('off');
    if (mapaRep) {
      if (!mapaRep.hasLayer(pinRep)) pinRep.addTo(mapaRep);
      pinRep.setLatLng([lat, lng]);
      if (circuloGps) { circuloGps.remove(); circuloGps = null; }
      if (repPrecision) circuloGps = L.circle([lat, lng], { radius: repPrecision, color: '#1B75BB', weight: 1, fillOpacity: 0.1, interactive: false }).addTo(mapaRep);
      capaTramoRep.clearLayers();
      if (repCercano && repCercano.dist <= Reports.RADIO_M) {
        const t = repCercano.tramo, a = Engine.nodoPorId[t.de], b = Engine.nodoPorId[t.a];
        L.polyline(t.geom || [[a.lat, a.lng], [b.lat, b.lng]], { color: MODOS[t.modo].color, weight: 7, opacity: 0.9, interactive: false }).addTo(capaTramoRep);
      }
      if (primera) mapaRep.setView([lat, lng], 16); else mapaRep.panTo([lat, lng]);
    }
    pintarDonde();
  }
  const MENSAJE_GPS = {
    'sin-gps': 'Este dispositivo no tiene ubicación disponible. Solo se puede reportar desde donde estás.',
    permiso: 'Activa el permiso de ubicación para reportar: el reporte queda donde estás.',
    senal: 'No pudimos obtener tu ubicación. Revisa el GPS y toca «Reintentar».',
  };
  const repImpreciso = () => repPrecision > PRECISION_MAX_M;
  const repFuera = () => !repCercano || repCercano.dist > Reports.RADIO_M;
  function pintarDonde() {
    $$('.rep-donde').forEach(pintarDondeEn);
    pintarEnvio();
  }
  function pintarDondeEn(el) {
    el.classList.toggle('fuera', !!repError || (!!repPos && (repImpreciso() || repFuera())));
    if (repError) el.innerHTML = ico('location_off') + ' ' + MENSAJE_GPS[repError];
    else if (!repPos) el.textContent = 'Buscando tu ubicación…';
    else if (repImpreciso()) el.innerHTML = ico('gps_not_fixed') + ` Tu ubicación es muy imprecisa (±${Math.round(repPrecision)} m). Espera a tener mejor señal GPS.`;
    else if (repFuera()) el.innerHTML = ico('wrong_location') + ' Estás lejos de las rutas de Ciudad Bolívar. Solo puedes reportar lo que pasa donde estás.';
    else {
      const t = repCercano.tramo, m = MODOS[t.modo];
      const dist = repCercano.dist < 30 ? 'sobre la vía' : `a ${Math.round(repCercano.dist)} m`;
      el.innerHTML = `<span class="rep-donde-ico" style="--c:${m.color}">${icoModo(t.modo)}</span>
        <span><b>${m.nombre} · ${esc(t.ruta)}</b><br><small>${Engine.nodoPorId[t.de].nombre} ↔ ${Engine.nodoPorId[t.a].nombre} · ${dist}</small></span>`;
    }
    if (MODO_DEV_HTTP && repPos) el.insertAdjacentHTML('beforeend', `<small class="rep-donde-aviso">${ico('science')} Modo dev (http): ubicación fija de prueba, no es tu GPS</small>`);
  }
  function pintarEnvio() {
    const b = $('#btnReportar');
    const ubicado = repPos && !repError && !repImpreciso() && !repFuera();
    const t = Reports.TIPOS[repTipo.value];
    b.disabled = !enLinea || !ubicado || !t;
    b.innerHTML = !enLinea ? `${ico('cloud_off')} Sin conexión con el servidor`
      : !ubicado ? `${ico('my_location')} Necesitamos tu ubicación`
      : !t ? 'Elige qué está pasando'
      : `${icoTipo(repTipo.value)} Reportar: ${t.label}`;
  }
  pintarEnvio();

  // Panel inferior para crear el reporte (tipo + detalle + enviar)
  const sheet = $('#repSheet');
  function abrirSheet() {
    pintarDonde();
    sheet.appendChild($('#toasts')); // los avisos quedan visibles por encima del fondo del panel
    sheet.showModal();
  }
  function cerrarSheet() { if (sheet.open) sheet.close(); }
  sheet.addEventListener('close', () => document.body.insertBefore($('#toasts'), $('main')));
  sheet.addEventListener('click', (e) => { if (e.target === sheet) cerrarSheet(); }); // toque en el fondo
  $('#btnAbrirReporte').addEventListener('click', abrirSheet);
  $('#repCerrar').addEventListener('click', cerrarSheet);
  $('#repCentrar').addEventListener('click', () => {
    if (repPos && mapaRep) mapaRep.setView([repPos.lat, repPos.lng], Math.max(mapaRep.getZoom(), 16));
    else ubicar();
  });

  $('#btnReportar').addEventListener('click', async () => {
    const tipo = repTipo.value, nota = $('#repNota').value.trim();
    if (!tipo || !repPos || repError || !enLinea) return;
    const b = $('#btnReportar'); b.disabled = true; b.textContent = 'Enviando…';
    // Se guarda en el servidor (Postgres) con la posición del GPS, tu identidad anónima y tus estrellas
    const r = await API.reportar({ tipo, lat: repPos.lat, lng: repPos.lng, nota });
    if (r && r.ok) {
      const v = r.data;
      toast(v.afecta_rutas
        ? `${ico('check_circle')} Reporte guardado · confianza ${Math.round(v.confianza * 100)}%. Ya afecta las rutas.`
        : `${ico('check_circle')} Reporte guardado · confianza ${Math.round(v.confianza * 100)}%. Se aplicará cuando otros lo confirmen.`);
      $('#repNota').value = ''; marcarTipo('');
      cerrarSheet();
      await refrescarIncidentes(false); pintarPerfil();
      return;
    }
    toast(!r ? `${ico('cloud_off')} No se pudo conectar con el servidor. Intenta de nuevo.`
      : r.status === 429 ? 'Ya reportaste esto hace poco' : detalle(r));
    pintarEnvio();
  });

  // Tarjeta pública: tipo, hace cuánto, comentario y 👍/👎. Tus reportes se distinguen y no se votan.
  function tarjetaAlerta(i) {
    const t = Reports.TIPOS[i.tipo] || Reports.TIPOS.novedad;
    const vencida = i.vigente === false;
    const votable = !vencida && !i.esMio;
    const voto = (valor, icono, n, titulo) => {
      const activo = i.miVoto === valor;
      const cls = `voto-btn ${valor}${activo ? ' activo' : ''}`;
      return votable
        ? `<button type="button" class="${cls}" data-accion="${valor}" data-id="${i.id}" aria-pressed="${activo}" title="${titulo}">${ico(icono, activo ? 'fill' : '')}<span>${n}</span></button>`
        : `<span class="${cls}" title="${titulo}">${ico(icono)}<span>${n}</span></span>`;
    };
    const fecha = new Date(i.ts).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
    return `<article class="rep-item${i.esMio ? ' mio' : ''}${vencida ? ' vencida' : ''}" style="--c:${t.color}">
      <div class="rep-head"><span class="rep-ico">${icoTipo(i.tipo)}</span>
        <div class="rep-tit"><strong>${t.label}</strong>
          <time datetime="${new Date(i.ts).toISOString()}" title="${fecha}">${hace(i.ts)}${vencida ? ' · vencida' : ''}</time></div>
        ${i.esMio ? `<span class="rep-mio-badge">${ico('person', 'fill')}Tu reporte</span>` : ''}</div>
      ${i.nota ? `<p class="rep-nota">“${esc(i.nota)}”</p>` : ''}
      <div class="rep-votos">
        ${voto('confirma', 'thumb_up', i.nConfirma, 'Sigue ahí')}
        ${voto('niega', 'thumb_down', i.nNiega, 'Ya no está')}
        ${i.esMio && !vencida ? '<small>Lo califican los demás</small>' : ''}
      </div></article>`;
  }
  // Tarjeta de admin: detalle completo para moderar (verificar / rechazar)
  function tarjetaAdmin(i) {
    const t = Reports.TIPOS[i.tipo] || Reports.TIPOS.novedad;
    const ruta = `${Engine.nodoPorId[i.deId].nombre} → ${Engine.nodoPorId[i.aId].nombre}`;
    const nota = i.nota ? `<p class="rep-nota">“${esc(i.nota)}”</p>` : '';
    const pct = Math.round(i.confianza * 100);
    const estado = i.estado === 'verificado' ? `<span class="estado ok">${ico('verified', 'fill')}Verificado</span>`
      : i.afecta ? '<span class="estado">Afecta rutas</span>' : '<span class="estado bajo">Por confirmar</span>';
    const acciones = (i.estado !== 'verificado' ? `<button class="voto admin" data-accion="verificar" data-id="${i.id}">${ico('verified')}Verificar</button>` : '')
      + `<button class="voto admin peligro" data-accion="rechazar" data-id="${i.id}">${ico('block')}Rechazar</button>`;
    const autor = i.estrellasAutor != null ? `${esc(i.autor)} ${estrellas(i.estrellasAutor, true)}` : esc(i.autor);
    return `<div class="rep-item" style="--c:${t.color}"><div class="rep-head"><span class="rep-ico">${icoTipo(i.tipo)}</span>
      <div class="rep-tit"><strong>${t.label}</strong><span class="rep-ruta">${ruta}</span></div>${estado}</div>${nota}
      <div class="conf"><span style="width:${pct}%;background:${pct >= 70 ? '#e74c3c' : pct >= 40 ? '#f39c12' : '#bbb'}"></span></div>
      <small class="rep-meta">Confianza ${pct}% · ${autor} · ${hace(i.ts)} · ${ico('thumb_up')} ${i.nConfirma} · ${ico('thumb_down')} ${i.nNiega}</small>
      <div class="rep-acciones">${acciones}</div></div>`;
  }
  function pintarReportes() {
    const lista = listaFeed(); const cont = $('#listaReportes');
    const ultimaHora = lista.filter((i) => Date.now() - i.ts <= VENTANA_MAPA_MS).length;
    $('#repCount').textContent = ultimaHora === 1 ? '1 en la última hora' : `${ultimaHora} en la última hora`;
    cont.innerHTML = !enLinea
      ? `<p class="empty">${ico('cloud_off')}<br>Sin conexión con el servidor.<br><small>Las alertas se cargan desde el servidor; reintentamos en unos segundos.</small></p>`
      : lista.length ? lista.map(tarjetaAlerta).join('')
      : `<p class="empty">${ico('task_alt')}<br>No hay alertas en la última hora.<br><small>Si ves algo en la vía, repórtalo y avisamos a todos.</small></p>`;
    pintarFinFeed();
    pintarListaAdmin();
  }
  // 👍/👎 al instante: se pinta el voto antes de que responda el servidor y se revierte si falla.
  // Tocar el voto que ya diste no hace nada; tocar el otro lo cambia.
  const votando = new Set();
  async function votar(b) {
    const { accion: valor, id } = b.dataset;
    const raw = [...incRecientes, ...feedMas].find((x) => x.id === id);
    if (!raw || raw.mi_voto === valor || votando.has(id)) return;
    votando.add(id);
    const antes = { ...raw };
    const optimista = { ...raw, mi_voto: valor,
      n_confirma: raw.n_confirma + (valor === 'confirma') - (raw.mi_voto === 'confirma'),
      n_niega: raw.n_niega + (valor === 'niega') - (raw.mi_voto === 'niega') };
    actualizarEnFeed(optimista); pintarReportes();
    const r = await API.votar(id, valor);
    votando.delete(id);
    if (r && r.ok && r.data && r.data.id) { actualizarEnFeed({ ...optimista, ...r.data }); pintarReportes(); pintarPerfil(); return; }
    actualizarEnFeed(antes); pintarReportes();
    toast(r ? detalle(r) : `${ico('cloud_off')} No se pudo enviar tu voto. Intenta de nuevo.`);
  }
  async function accionAlerta(e) {
    const b = e.target.closest('button[data-accion]'); if (!b) return;
    const { accion, id } = b.dataset;
    if (accion === 'confirma' || accion === 'niega') return votar(b);
    b.disabled = true;
    const r = accion === 'verificar' ? await API.verificar(id) : await API.rechazar(id);
    if (r && r.ok && r.data && r.data.id) actualizarEnFeed(r.data);
    toast(r && r.ok ? (accion === 'verificar' ? `${ico('verified')} Alerta verificada` : `${ico('block')} Alerta rechazada`) : detalle(r));
    await refrescarIncidentes(false); pintarPerfil();
  }
  $('#listaReportes').addEventListener('click', accionAlerta);
  $('#adminLista').addEventListener('click', accionAlerta);
  function hace(ts) {
    const m = Math.round((Date.now() - ts) / 60000);
    return m < 1 ? 'ahora' : m < 60 ? `hace ${m} min` : `hace ${Math.round(m / 60)} h`;
  }

  // ---------- Reputación (sin cuenta): estrellas de 0 a 5 ----------
  function estrellas(n, mini) {
    const v = Math.max(0, Math.min(5, Number(n) || 0));
    if (mini) return `<span class="estrellas mini" title="${v} de 5 estrellas">${ico('star', 'fill')}<b>${v.toLocaleString('es-CO')}</b></span>`;
    const icono = (k) => ico(v >= k ? 'star' : v >= k - 0.5 ? 'star_half' : 'star', v >= k - 0.5 ? 'fill' : '');
    return `<span class="estrellas" role="img" aria-label="${v} de 5 estrellas">`
      + [1, 2, 3, 4, 5].map((k) => `<span class="${v >= k - 0.5 ? 'on' : ''}">${icono(k)}</span>`).join('')
      + `<b>${v.toLocaleString('es-CO')}</b></span>`;
  }
  // Cabecera de Reportar: icono de usuario + puntuación. Nada más.
  async function pintarPerfil() {
    const el = $('#perfil');
    const p = enLinea ? await API.perfil() : null;
    const admin = p && p.rol === 'admin';
    el.innerHTML = `<span class="rep-user-ava">${ico(admin ? 'shield_person' : 'account_circle', 'fill')}</span>
      <strong>${admin ? 'Administrador' : 'Tú'}</strong>`
      + (admin ? '' : p ? estrellas(p.estrellas) : '<small>Sin conexión</small>');
    if (p && !admin) el.title = `${p.likes} 👍 · ${p.dislikes} 👎 de otros vecinos en tus reportes`;
  }

  // ---------- Administrador (pestaña #/admin) ----------
  function pintarAdmin() {
    const activo = enLinea && API.esAdmin;
    $('#adminLogin').hidden = activo;
    $('#adminPanel').hidden = !activo;
    $('#adminOffline').hidden = enLinea;
    $('#adminKey').disabled = $('#btnAdmin').disabled = !enLinea;
    $('#btnLimpiar').hidden = !activo && enLinea;
    $('#btnLimpiar').innerHTML = ico('delete_sweep') + (enLinea ? 'Limpiar todas las alertas' : 'Limpiar alertas de este dispositivo');
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
      ? [...lista].sort((a, b) => orden(a) - orden(b)).map(tarjetaAdmin).join('')
      : `<p class="empty">${ico('task_alt')}<br>No hay alertas que moderar.</p>`;
  }
  $('#adminForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const clave = $('#adminKey').value.trim(); if (!clave) return;
    $('#btnAdmin').disabled = true;
    API.setAdminKey(clave);
    $('#adminKey').value = '';
    const p = await API.perfil();
    if (!p || p.rol !== 'admin') { API.setAdminKey(''); toast(`${ico('lock')} Clave incorrecta`); }
    else toast(`${ico('shield_person')} Modo admin activo`);
    $('#btnAdmin').disabled = false;
    pintarAdmin(); pintarPerfil();
  });
  $('#btnSalirAdmin').addEventListener('click', () => {
    API.setAdminKey(''); toast('Saliste del modo admin');
    pintarAdmin(); pintarPerfil();
  });
  $('#btnLimpiar').addEventListener('click', async () => {
    if (!confirm('¿Limpiar todas las alertas?')) return;
    if (enLinea && API.esAdmin) {
      const r = await API.limpiar();
      toast(r && r.ok ? `${ico('delete_sweep')} ${r.data.eliminados} alerta(s) eliminadas del servidor` : detalle(r));
      await refrescarIncidentes(false);
    }
  });

  // ---------- Tiempo real ----------
  // Todo sale del servidor: alertas nuevas, votos y estrellas llegan por sondeo cada 5 s.
  abrirMapa();
  aplicarRuta();
  pintarTodo();
  revisarServidor();
  setInterval(() => { if (enLinea) refrescarIncidentes(); }, 5000);
  setInterval(revisarServidor, 15000);
  setInterval(() => { if (enLinea) pintarReportes(); }, 60000); // «hace X min» al día

  // ---------- Service worker ----------
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
})();
