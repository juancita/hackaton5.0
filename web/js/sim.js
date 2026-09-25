/*
 * sim.js — "Sala en vivo": varios vecinos reportando y calificando a la vez.
 * Cada vecino simulado es una identidad anónima distinta ante el backend (X-Client-Id propio):
 * sus reportes se guardan en Postgres vía FastAPI (POST /incidents), sus 👍/👎 son votos reales
 * (POST /incidents/{id}/votos) y sus estrellas salen de GET /reporters/me. El mapa y la lista
 * se leen del servidor (GET /incidents/recent), así que lo que pasa aquí lo ve toda la app.
 */
(() => {
  const { PARADEROS, TRAMOS, MODOS } = window.DB;
  const $ = (s) => document.querySelector(s);
  const esc = (x) => String(x).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // 6 vecinos simulados (mezcla de canales y perfiles del territorio); `id` es su identidad anónima
  const USUARIOS = [
    { id: 'sala-rosa', nombre: 'Doña Rosa', canal: 'whatsapp', icono: 'elderly_woman', barrio: 'Paraíso Alto' },
    { id: 'sala-carlos', nombre: 'Carlos (jeepero)', canal: 'whatsapp', icono: 'person', barrio: 'Quiba' },
    { id: 'sala-laura', nombre: 'Laura (estudiante)', canal: 'web', icono: 'school', barrio: 'Sierra Morena' },
    { id: 'sala-andres', nombre: 'Andrés (comerciante)', canal: 'web', icono: 'storefront', barrio: 'Perdomo' },
    { id: 'sala-jac', nombre: 'JAC Arborizadora', canal: 'web', icono: 'home_work', barrio: 'Arborizadora Alta' },
    { id: 'sala-miguel', nombre: 'Miguel', canal: 'whatsapp', icono: 'person', barrio: 'Meissen' },
  ];

  // Reportes rápidos disponibles en cada panel
  const RAPIDOS = ['derrumbe', 'bloqueo', 'trancon', 'lleno', 'sinservicio'];

  function tramoDe(barrio) {
    const nodo = PARADEROS.find((p) => p.nombre === barrio);
    const id = nodo ? nodo.id : 'tunal';
    return TRAMOS.find((t) => t.de === id || t.a === id) || TRAMOS[0];
  }
  const detalle = (r) => {
    const d = r && r.data && r.data.detail;
    return !r ? 'Sin conexión con el servidor' : typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg).join(', ') : 'No se pudo completar';
  };
  const estrellasMini = (n) => (n == null ? ''
    : `<span class="estrellas mini" title="${n} de 5 estrellas">${ico('star', 'fill')}<b>${Number(n).toLocaleString('es-CO')}</b></span>`);

  // ---------- Paneles de los vecinos ----------
  const cont = $('#users');
  USUARIOS.forEach((u, idx) => {
    const div = document.createElement('div');
    div.className = 'user ' + (u.canal === 'whatsapp' ? 'wa' : 'web');
    div.innerHTML = `
      <div class="uhead">${ico(u.icono, 'fill')} <strong>${u.nombre}</strong>
        <span class="canal">${icoCanal(u.canal)}${u.canal === 'whatsapp' ? 'WhatsApp' : 'Web'}</span></div>
      <div class="ubody">
        <div class="uinfo">${ico('location_on')}${u.barrio}<span class="ustars" id="stars-${idx}"></span></div>
        <div class="quick">${RAPIDOS.map((t) => {
          const tt = Reports.TIPOS[t];
          return `<button style="background:${tt.color}" data-u="${idx}" data-t="${t}">${icoTipo(t)}${tt.label.split(' ')[0]}</button>`;
        }).join('')}</div>
        <div class="last" id="last-${idx}"></div>
      </div>`;
    cont.appendChild(div);
  });
  const ultimo = (idx, html) => { $('#last-' + idx).innerHTML = html; };

  async function reportarComo(idx, tipo) {
    const u = USUARIOS[idx]; const tr = tramoDe(u.barrio);
    const r = await API.reportar({ tipo, de_id: tr.de, a_id: tr.a, modo: tr.modo, nota: `Reportado por ${u.nombre}` }, u.id);
    ultimo(idx, r && r.ok ? `${ico('check')} Enviaste: ${Reports.TIPOS[tipo].label}` : `${ico('error')} ${esc(detalle(r))}`);
    await refrescar();
  }
  async function votarComo(idx, inc, valor) {
    const r = await API.votar(inc.id, valor, USUARIOS[idx].id);
    if (r && r.ok) ultimo(idx, `${ico(valor === 'confirma' ? 'thumb_up' : 'thumb_down')} Calificó: ${inc.label} en ${Engine.nodoPorId[inc.de_id].nombre}`);
    await refrescar();
  }
  cont.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-u]'); if (!b) return;
    reportarComo(+b.dataset.u, b.dataset.t);
  });

  // ---------- Mapa vivo (Leaflet con calles reales; SVG esquemático si no carga Leaflet) ----------
  let mapa = null, capaInc = null;
  if (typeof L !== 'undefined') {
    mapa = L.map('mapa', { zoomControl: true }).setView([4.575, -74.155], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '© OpenStreetMap' }).addTo(mapa);
    const puntos = [];
    TRAMOS.forEach((t) => {
      const a = Engine.nodoPorId[t.de], b = Engine.nodoPorId[t.a]; if (!a || !b) return;
      const linea = t.geom || [[a.lat, a.lng], [b.lat, b.lng]];
      puntos.push(...linea);
      L.polyline(linea, { color: MODOS[t.modo].color, weight: MODOS[t.modo].formal ? 4 : 3, opacity: 0.6,
        dashArray: MODOS[t.modo].formal ? null : '6,6' }).addTo(mapa)
        .bindPopup(`${icoModo(t.modo)} ${MODOS[t.modo].nombre}<br><b>${esc(t.ruta)}</b><br>${a.nombre} → ${b.nombre}`);
    });
    PARADEROS.forEach((p) => {
      L.circleMarker([p.lat, p.lng], { radius: 4, color: '#fff', weight: 1.5, fillColor: '#770092', fillOpacity: 1 })
        .addTo(mapa).bindPopup(`<b>${esc(p.nombre)}</b>`);
    });
    if (puntos.length) mapa.fitBounds(L.latLngBounds(puntos), { padding: [20, 20] });
    capaInc = L.layerGroup().addTo(mapa);
    // El mapa cambia de tamaño con la ventana (grid responsive): Leaflet debe recalcular
    new ResizeObserver(() => mapa.invalidateSize()).observe($('#mapa'));
  } else {
    $('#mapa').style.display = 'none';
    $('#mapaSvg').style.display = 'block';
  }

  // lista: vistas del backend (IncidentView) de la última hora, más nuevas primero
  function dibujar(lista) {
    const vig = lista.filter((i) => i.vigente);
    $('#incCount').textContent = vig.length === 1 ? '1 alerta' : `${vig.length} alertas`;
    if (!mapa) { dibujarSvg(vig); return; }
    capaInc.clearLayers();
    lista.forEach((i) => {
      const t = Reports.TIPOS[i.tipo] || Reports.TIPOS.novedad;
      const clase = !i.vigente ? ' vencido' : !i.afecta_rutas ? ' tenue' : '';
      const icon = L.divIcon({ className: 'inc-icon', html: `<div class="inc-pin${clase}" style="--c:${t.color}">${icoTipo(i.tipo)}</div>`, iconSize: [34, 34] });
      L.marker([i.lat, i.lng], { icon, zIndexOffset: i.vigente ? 0 : -1000 }).addTo(capaInc)
        .bindPopup(`<b>${icoTipo(i.tipo)} ${t.label}</b><br>${Engine.nodoPorId[i.de_id].nombre} → ${Engine.nodoPorId[i.a_id].nombre}`
          + `<br><small>${esc(i.nota)} ${estrellasMini(i.estrellas_autor)} · ${ico('thumb_up')} ${i.n_confirma} · ${ico('thumb_down')} ${i.n_niega}</small>`);
    });
  }

  const NS = 'http://www.w3.org/2000/svg';
  function dibujarSvg(vig) {
    const svg = $('#mapaSvg'); svg.innerHTML = '';
    TRAMOS.forEach((t) => {
      const a = Engine.nodoPorId[t.de], b = Engine.nodoPorId[t.a];
      const l = document.createElementNS(NS, 'line');
      l.setAttribute('x1', a.x); l.setAttribute('y1', a.y); l.setAttribute('x2', b.x); l.setAttribute('y2', b.y);
      l.setAttribute('stroke', MODOS[t.modo].color); l.setAttribute('stroke-width', MODOS[t.modo].formal ? 0.8 : 0.6);
      if (!MODOS[t.modo].formal) l.setAttribute('stroke-dasharray', '1.5,1');
      svg.appendChild(l);
    });
    PARADEROS.forEach((p) => {
      const c = document.createElementNS(NS, 'circle');
      c.setAttribute('cx', p.x); c.setAttribute('cy', p.y); c.setAttribute('r', 1.2);
      c.setAttribute('fill', '#770092'); c.setAttribute('stroke', '#fff'); c.setAttribute('stroke-width', '.3');
      svg.appendChild(c);
    });
    vig.forEach((i) => {
      const t = Reports.TIPOS[i.tipo]; const a = Engine.nodoPorId[i.de_id], b = Engine.nodoPorId[i.a_id];
      const pin = document.createElementNS(NS, 'circle');
      pin.setAttribute('cx', (a.x + b.x) / 2); pin.setAttribute('cy', (a.y + b.y) / 2); pin.setAttribute('r', 2);
      pin.setAttribute('fill', t.color); pin.setAttribute('stroke', '#fff'); pin.setAttribute('stroke-width', '.5');
      svg.appendChild(pin);
    });
  }

  function toast(html, color) {
    const el = document.createElement('div'); el.className = 'toast';
    if (color) el.style.borderLeftColor = color; el.innerHTML = html;
    $('#toasts').appendChild(el);
    setTimeout(() => el.classList.add('show'), 10);
    setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, 4500);
  }

  // Lista bajo el mapa: los reportes de la última hora guardados en el servidor
  function pintarFeed(lista) {
    const feed = $('#feed');
    feed.innerHTML = lista.map((i) => `<div data-id="${i.id}" class="${i.vigente ? '' : 'vencido'}">${icoTipo(i.tipo)} <b>${esc(i.label)}</b>
      en ${Engine.nodoPorId[i.de_id].nombre} · ${esc(i.nota)} ${estrellasMini(i.estrellas_autor)}
      · ${ico('thumb_up')} ${i.n_confirma} ${ico('thumb_down')} ${i.n_niega}${i.vigente ? '' : ' · vencida'}</div>`).join('');
  }
  $('#feed').addEventListener('click', (e) => {
    const d = e.target.closest('div[data-id]'); const i = d && ultimos.find((x) => x.id === d.dataset.id);
    if (i && mapa) mapa.setView([i.lat, i.lng], 16);
  });

  // ---------- Sincronización con el servidor (sondeo) ----------
  let ultimos = [], conocidos = null, enLinea = true;
  async function refrescar() {
    const lista = await API.recientes({ horas: 1, limit: 50 });
    enLinea = !!lista;
    $('#salaEstado').hidden = enLinea;
    $$('#users button').forEach((b) => { b.disabled = !enLinea; });
    if (!lista) return;
    // Avisar solo de lo que apareció después de abrir la sala
    if (conocidos) lista.filter((i) => !conocidos.has(i.id)).forEach((i) => {
      const t = Reports.TIPOS[i.tipo] || Reports.TIPOS.novedad;
      toast(`<b>${icoTipo(i.tipo)} ${t.label}</b><br><small>${esc(i.nota)} · guardado en el servidor</small>`, t.color);
    });
    conocidos = new Set(lista.map((i) => i.id));
    ultimos = lista;
    dibujar(lista); pintarFeed(lista);
    // Estrellas de cada vecino (las dan los 👍/👎 de los demás)
    const perfiles = await Promise.all(USUARIOS.map((u) => API.perfil(u.id)));
    perfiles.forEach((p, idx) => { $('#stars-' + idx).innerHTML = p ? estrellasMini(p.estrellas) : ''; });
  }
  const $$ = (s) => document.querySelectorAll(s);
  refrescar();
  setInterval(refrescar, 3000);

  // ---------- Simulación: los vecinos reportan y se califican entre ellos ----------
  const azar = (l) => l[Math.floor(Math.random() * l.length)];
  let auto = null;
  $('#btnAuto').addEventListener('click', (e) => {
    if (auto) { clearInterval(auto); auto = null; e.currentTarget.innerHTML = ico('play_arrow', 'fill') + 'Simular actividad'; return; }
    e.currentTarget.innerHTML = ico('pause', 'fill') + 'Pausar simulación';
    auto = setInterval(() => {
      if (!enLinea) return;
      const idx = Math.floor(Math.random() * USUARIOS.length);
      // Reportes de otros vecinos que siguen vigentes: se pueden calificar
      const ajenos = ultimos.filter((i) => i.vigente && !i.nota.includes(USUARIOS[idx].nombre));
      if (ajenos.length && Math.random() < 0.5) votarComo(idx, azar(ajenos), Math.random() < 0.75 ? 'confirma' : 'niega');
      else reportarComo(idx, azar(RAPIDOS));
    }, 3500);
  });

  // ---------- Cámaras de fotodetección (Edge AI) ----------
  // Cada cámara de semáforo (las de fotocomparendos) cuenta vehículos EN EL BORDE y solo envía un número:
  // el nivel de congestión. Con ≥60% el backend crea un incidente verificado en su tramo y las rutas lo
  // esquivan; se combina con los reportes de los vecinos (más fuentes = más confianza).
  let camTimer = null;
  $('#btnCamaras').addEventListener('click', (e) => {
    const btn = e.currentTarget;
    if (camTimer) { clearInterval(camTimer); camTimer = null; btn.innerHTML = ico('videocam') + 'Cámaras de fotodetección'; return; }
    btn.innerHTML = ico('videocam_off') + 'Detener cámaras';
    let primera = true;
    const leer = async () => {
      if (!enLinea) return;
      const camaras = window.DB.CAMARAS || [];
      // Guion del demo: la primera lectura es la subida a Paraíso con el tráfico detenido (bloqueo)
      const cam = primera ? (camaras.find((c) => c.id === 'cam-paraiso') || azar(camaras)) : azar(camaras);
      if (!cam) return;
      const nivel = primera ? 0.97 : Math.min(0.97, 0.45 + Math.random() * 0.55);  // 45%..97%
      primera = false;
      const vehiculos = Math.round(nivel * 60);
      const r = await API.camaraLectura(cam.id, +nivel.toFixed(2), vehiculos);
      const pct = Math.round(nivel * 100);
      if (r && r.ok && r.data.accion === 'incidente') {
        toast(`<b>${ico('videocam')} ${cam.nombre}</b><br>Detectó ${vehiculos} vehículos (${pct}% de congestión) → <b>${r.data.tipo}</b> publicado y rutas desviadas`, '#E4002B');
        refrescar();
      } else if (r && r.ok) {
        toast(`${ico('videocam')} ${cam.nombre}: flujo normal (${pct}%)`, '#2ECC71');
      }
    };
    leer();
    camTimer = setInterval(leer, 6000);
  });
})();
