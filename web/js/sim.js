/*
 * sim.js — "Sala en vivo": simula 3–6 usuarios reportando a la vez.
 * Unos entran por WhatsApp y otros por la web. Todo se propaga por
 * Realtime → el mapa compartido y los paneles se actualizan al instante.
 * Ideal para el pitch: demuestra el efecto de red en tiempo real, offline.
 */
(() => {
  const { PARADEROS, TRAMOS, MODOS } = window.DB;
  const $ = (s) => document.querySelector(s);

  // 6 usuarios simulados (mezcla de canales y perfiles del territorio)
  const USUARIOS = [
    { nombre: 'Doña Rosa', canal: 'whatsapp', icono: 'elderly_woman', barrio: 'Paraíso Alto' },
    { nombre: 'Carlos (jeepero)', canal: 'whatsapp', icono: 'person', barrio: 'Quiba' },
    { nombre: 'Laura (estudiante)', canal: 'web', icono: 'school', barrio: 'Sierra Morena' },
    { nombre: 'Andrés (comerciante)', canal: 'web', icono: 'storefront', barrio: 'Perdomo' },
    { nombre: 'JAC Arborizadora', canal: 'web', icono: 'home_work', barrio: 'Arborizadora Alta' },
    { nombre: 'Miguel', canal: 'whatsapp', icono: 'person', barrio: 'Meissen' },
  ];

  // Reportes rápidos disponibles en cada panel
  const RAPIDOS = ['derrumbe', 'bloqueo', 'trancon', 'lleno', 'sinservicio'];

  function tramoDe(barrio) {
    const nodo = PARADEROS.find((p) => p.nombre === barrio);
    const id = nodo ? nodo.id : 'tunal';
    return TRAMOS.find((t) => t.de === id || t.a === id) || TRAMOS[0];
  }

  // Render de paneles de usuario
  const cont = $('#users');
  USUARIOS.forEach((u, idx) => {
    const div = document.createElement('div');
    div.className = 'user ' + (u.canal === 'whatsapp' ? 'wa' : 'web');
    div.innerHTML = `
      <div class="uhead">${ico(u.icono, 'fill')} <strong>${u.nombre}</strong>
        <span class="canal">${icoCanal(u.canal)}${u.canal === 'whatsapp' ? 'WhatsApp' : 'Web'}</span></div>
      <div class="ubody">
        <div style="display:flex;align-items:center;gap:2px;font-size:11px;color:var(--gris);margin-bottom:6px">${ico('location_on')}${u.barrio}</div>
        <div class="quick">${RAPIDOS.map((t) => {
          const tt = Reports.TIPOS[t];
          return `<button style="background:${tt.color}" data-u="${idx}" data-t="${t}">${icoTipo(t)}${tt.label.split(' ')[0]}</button>`;
        }).join('')}</div>
        <div class="last" id="last-${idx}"></div>
      </div>`;
    cont.appendChild(div);
  });

  cont.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-u]'); if (!b) return;
    const u = USUARIOS[+b.dataset.u]; const tr = tramoDe(u.barrio);
    Reports.reportar({ tipo: b.dataset.t, deId: tr.de, aId: tr.a, modo: tr.modo,
      nota: `Reportado por ${u.nombre}`, canal: u.canal, autor: u.nombre });
    $('#last-' + b.dataset.u).innerHTML = `${ico('check')} Enviaste: ${Reports.TIPOS[b.dataset.t].label}`;
  });

  // ---------- Mapa vivo (SVG, siempre offline) ----------
  const NS = 'http://www.w3.org/2000/svg';
  function dibujar() {
    const svg = $('#mapa'); svg.innerHTML = '';
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
    Realtime.vigentes().forEach((i) => {
      const t = Reports.TIPOS[i.tipo]; const a = Engine.nodoPorId[i.deId], b = Engine.nodoPorId[i.aId];
      const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
      const halo = document.createElementNS(NS, 'circle');
      halo.setAttribute('cx', cx); halo.setAttribute('cy', cy); halo.setAttribute('r', 3.5);
      halo.setAttribute('fill', t.color); halo.setAttribute('opacity', '.25');
      const pin = document.createElementNS(NS, 'circle');
      pin.setAttribute('cx', cx); pin.setAttribute('cy', cy); pin.setAttribute('r', 2);
      pin.setAttribute('fill', t.color); pin.setAttribute('stroke', '#fff'); pin.setAttribute('stroke-width', '.5');
      svg.appendChild(halo); svg.appendChild(pin);
    });
    $('#incCount').textContent = Realtime.vigentes().length + ' alertas';
  }

  function toast(html, color) {
    const el = document.createElement('div'); el.className = 'toast';
    if (color) el.style.borderLeftColor = color; el.innerHTML = html;
    $('#toasts').appendChild(el);
    setTimeout(() => el.classList.add('show'), 10);
    setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, 4500);
  }

  function feed(i) {
    const t = Reports.TIPOS[i.tipo]; const d = document.createElement('div');
    d.innerHTML = `${icoTipo(i.tipo)} <b>${i.autor}</b> ${icoCanal(i.canal)}: ${t.label} en ${Engine.nodoPorId[i.deId].nombre}`;
    $('#feed').prepend(d);
  }

  Realtime.suscribir((ev) => {
    dibujar();
    if (ev.action === 'add' && ev.incidente) {
      const t = Reports.TIPOS[ev.incidente.tipo];
      toast(`<b>${icoTipo(ev.incidente.tipo)} ${t.label}</b><br><small>${ev.incidente.autor} · ${ev.incidente.canal}</small>`, t.color);
      feed(ev.incidente);
    }
  });
  dibujar();

  // ---------- Controles ----------
  let auto = null;
  $('#btnAuto').addEventListener('click', (e) => {
    if (auto) { clearInterval(auto); auto = null; e.currentTarget.innerHTML = ico('play_arrow', 'fill') + 'Simular actividad'; return; }
    e.currentTarget.innerHTML = ico('pause', 'fill') + 'Pausar simulación';
    auto = setInterval(() => {
      const u = USUARIOS[Math.floor(Math.random() * USUARIOS.length)];
      const tipo = RAPIDOS[Math.floor(Math.random() * RAPIDOS.length)];
      const tr = tramoDe(u.barrio);
      Reports.reportar({ tipo, deId: tr.de, aId: tr.a, modo: tr.modo, nota: `Reportado por ${u.nombre}`, canal: u.canal, autor: u.nombre });
    }, 3500);
  });
  $('#btnClear').addEventListener('click', () => { Realtime.limpiarTodo(); $('#feed').innerHTML = ''; });
})();
