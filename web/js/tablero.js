/*
 * tablero.js — Tablero de movilidad del administrador (y demo del producto para entidades).
 * ---------------------------------------------------------------------------
 * Pinta /admin/tablero (cifras agregadas y anónimas que calcula el backend) con Chart.js y Leaflet,
 * y el resumen ejecutivo que redacta la IA (/admin/tablero/resumen). Chart.js se carga solo al abrir
 * el tablero; si no carga (sin señal), se ven las cifras y tablas igual.
 */
window.Tablero = (() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (n) => Number(n || 0).toLocaleString('es-CO');
  const pct = (n) => `${Number(n || 0).toLocaleString('es-CO', { maximumFractionDigits: 1 })}%`;
  const toast = (h) => (window.appToast ? window.appToast(h) : null);
  const CHART_JS = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js';
  const C = { morado: '#770092', lila: '#B45CC8', verde: '#12A150', naranja: '#E8531C', navy: '#1F3864',
    info: '#005888', indigo: '#3D0080', gris: '#9A96A6', amarillo: '#D99A00' };
  const PALETA = [C.morado, C.naranja, C.info, C.verde, C.indigo, C.amarillo, C.lila, C.navy];
  const TIPOS = { trancon: 'Trancón', lleno: 'Lleno / no para', sinservicio: 'Sin servicio', novedad: 'Novedad',
    derrumbe: 'Derrumbe', bloqueo: 'Bloqueo / manifestación' };
  const MEDIO_COLOR = { informal: C.naranja, sitp: C.info, cable: C.morado, transmilenio: C.navy };

  let dias = 30;
  let charts = [];
  let mapa = null;
  let cargando = false;

  function cargarChart() {
    if (window.Chart) return Promise.resolve(true);
    return new Promise((ok) => {
      const s = document.createElement('script');
      s.src = CHART_JS; s.onload = () => ok(true); s.onerror = () => ok(false);
      document.head.appendChild(s);
    });
  }

  function limpiar() {
    charts.forEach((c) => c.destroy()); charts = [];
    if (mapa) { mapa.remove(); mapa = null; }
  }

  // ---------- Estructura ----------
  function esqueleto(d) {
    const k = d.kpis;
    const kpi = (icono, valor, etiqueta, extra = '', color = '') =>
      `<div class="kpi"${color ? ` style="--c:${color}"` : ''}><span class="ms" aria-hidden="true">${icono}</span>`
      + `<b>${valor}</b><span>${etiqueta}</span>${extra ? `<small>${extra}</small>` : ''}</div>`;
    return `
      <div class="card tab-head">
        <div>
          <h2><span class="ms" aria-hidden="true">insights</span> Tablero de movilidad · Ciudad Bolívar</h2>
          <p class="hint">Datos agregados y anónimos de los últimos ${d.dias} días: consultas de ruta, viajes informales, cupos y reportes.</p>
          ${d.datos_demo ? '<span class="tab-demo"><span class="ms" aria-hidden="true">science</span>Incluye datos simulados para la demostración</span>' : ''}
        </div>
        <div class="tab-controles">
          <div class="tab-periodo" role="group" aria-label="Periodo">
            ${[7, 30, 60].map((n) => `<button type="button" data-dias="${n}" class="${n === d.dias ? 'activo' : ''}">${n} días</button>`).join('')}
          </div>
          <button type="button" class="linkbtn ghost" data-acc="csv"><span class="ms" aria-hidden="true">download</span>Descargar CSV</button>
        </div>
      </div>

      <div class="card tab-ia">
        <div class="tab-ia-head">
          <span class="tab-ia-ico"><span class="ms" aria-hidden="true">auto_awesome</span></span>
          <div><h3>Análisis de la IA</h3><small id="tabIaFuente">Gemini está leyendo ${num(k.consultas)} consultas…</small></div>
          <button type="button" class="linkbtn ghost" data-acc="reanalizar" title="Pedir un análisis nuevo"><span class="ms" aria-hidden="true">refresh</span></button>
        </div>
        <div id="tabIaTexto" class="tab-ia-texto cargando"><span></span><span></span><span></span></div>
      </div>

      <div class="kpis">
        ${kpi('group', num(k.usuarios_activos), 'vecinos activos', k.crecimiento_usuarios_pct > 0 ? `▲ ${pct(k.crecimiento_usuarios_pct)} en el periodo` : '', C.morado)}
        ${kpi('route', num(k.consultas), 'consultas de ruta', `${num(k.consultas_dia)} al día`, C.info)}
        ${kpi('airport_shuttle', num(k.conductores_activos), 'conductores informales', `${num(k.viajes_informales)} viajes`, C.naranja)}
        ${kpi('event_seat', pct(k.ocupacion_pct), 'ocupación promedio', `${num(k.pasajeros_informales)} pasajeros`, C.verde)}
        ${kpi('bookmark_added', num(k.cupos_apartados), 'cupos apartados en la app', '', C.indigo)}
        ${kpi('hourglass_bottom', num(k.horas_espera_evitadas), 'horas de espera evitadas', 'estimado: 12 min por cupo', C.amarillo)}
        ${kpi('campaign', num(k.reportes), 'reportes ciudadanos', `${pct(k.reportes_chat_pct)} por el chat con IA`, C.naranja)}
        ${kpi('logout', pct(k.fuera_localidad_pct), 'sale de la localidad', 'hacia otra zona de Bogotá', C.navy)}
      </div>

      <div class="tab-grid">
        <section class="card tab-ancho">
          <h3>¿A qué hora se mueve la loma?</h3>
          <p class="hint">Consultas por hora del día y porcentaje de viajes informales que salen llenos.</p>
          <div class="tab-chart alto"><canvas id="chHoras"></canvas></div>
        </section>

        <section class="card tab-ancho">
          <h3>Flujos: de los barrios a las salidas y a toda Bogotá</h3>
          <p class="hint">El grosor es el volumen de consultas. Línea continua: barrio → salida de la localidad. Punteada: salida → destino final. Solo flujos de 5 personas o más.</p>
          <div id="tabMapa" class="tab-mapa"></div>
        </section>

        <section class="card">
          <h3>Destinos finales</h3>
          <p class="hint">A qué zona de Bogotá sigue el viaje.</p>
          <div class="tab-chart"><canvas id="chFinales"></canvas></div>
        </section>

        <section class="card">
          <h3>Salidas de la localidad</h3>
          <p class="hint">Por dónde sale la gente hacia el resto de la ciudad.</p>
          <div class="tab-chart"><canvas id="chSalidas"></canvas></div>
        </section>

        <section class="card">
          <h3>Medio que define el viaje</h3>
          <p class="hint">Si la ruta usa un tramo informal, cuenta como informal.</p>
          <div class="tab-chart"><canvas id="chMedios"></canvas></div>
        </section>

        <section class="card">
          <h3>Crecimiento semanal</h3>
          <p class="hint">Vecinos distintos que usaron la app cada semana.</p>
          <div class="tab-chart"><canvas id="chSemanal"></canvas></div>
        </section>

        <section class="card tab-ancho">
          <h3>Mapa de calor: día y hora</h3>
          <p class="hint">Cuándo se concentran las consultas de ruta.</p>
          <div id="tabHeat" class="heat"></div>
        </section>

        <section class="card tab-ancho">
          <h3>Rutas informales</h3>
          <p class="hint">Ocupación, viajes que se cortan a mitad de camino y pasajeros que se bajan antes del final.</p>
          <div class="tab-tabla" id="tabRutas"></div>
        </section>

        <section class="card">
          <h3>Barrios que más piden rutas</h3>
          <p class="hint">Y qué tanto dependen del transporte informal.</p>
          <div class="tab-tabla" id="tabBarrios"></div>
        </section>

        <section class="card">
          <h3>Trayectos más pedidos</h3>
          <p class="hint">Origen → destino.</p>
          <div class="tab-tabla" id="tabPares"></div>
        </section>

        <section class="card">
          <h3>Reportes por tipo</h3>
          <div class="tab-chart"><canvas id="chTipos"></canvas></div>
        </section>

        <section class="card">
          <h3>¿Por dónde llegan los reportes?</h3>
          <p class="hint">El chat con IA convierte un mensaje en un reporte del mapa.</p>
          <div class="tab-chart"><canvas id="chCanales"></canvas></div>
        </section>

        <section class="card tab-ancho">
          <h3><span class="ms" aria-hidden="true">lightbulb</span> Conclusiones y acciones</h3>
          <p class="hint">Calculadas directamente con los datos: son la base del análisis de la IA.</p>
          <div class="insights">${d.insights.map((i) => `
            <div class="insight"><span class="ms" aria-hidden="true">${esc(i.icono)}</span>
              <div><b>${esc(i.titulo)}</b><p>${esc(i.texto)}.</p><p class="accion"><span class="ms" aria-hidden="true">arrow_forward</span>${esc(i.accion)}</p></div>
            </div>`).join('')}
          </div>
        </section>
      </div>

      <p class="hint tab-privacidad"><span class="ms" aria-hidden="true">verified_user</span>
        Sin nombres ni teléfonos: el número se guarda cifrado y todo se muestra agregado. Los flujos con menos de 5 personas se agrupan (k-anonimato). Ley 1581 de 2012.</p>`;
  }

  // ---------- Tablas ----------
  const barra = (v, color) => `<span class="barrita"><i style="width:${Math.min(100, v)}%;background:${color}"></i></span>`;
  function tablas(d) {
    $('#tabRutas').innerHTML = `<table><thead><tr><th>Ruta</th><th>Viajes</th><th>Ocupación</th><th>Se cortan</th><th>Dónde</th><th>Se bajan antes</th><th>Hora pico</th></tr></thead><tbody>
      ${d.rutas_informales.slice(0, 10).map((r) => `<tr>
        <td><b>${esc(r.ruta)}</b><small>${r.conductores} conductor${r.conductores === 1 ? '' : 'es'}</small></td>
        <td>${num(r.viajes)}</td>
        <td>${barra(r.ocupacion_pct, C.verde)} ${pct(r.ocupacion_pct)}</td>
        <td>${r.cortados_pct ? `<b class="alerta-txt">${pct(r.cortados_pct)}</b>` : '—'}</td>
        <td>${esc(r.corte_frecuente || '—')}</td>
        <td>${r.bajan_antes_pct != null ? pct(r.bajan_antes_pct) : '—'}</td>
        <td>${esc(r.hora_pico || '—')}</td></tr>`).join('')}</tbody></table>`;
    $('#tabBarrios').innerHTML = `<table><thead><tr><th>Barrio</th><th>Consultas</th><th>Dependen del informal</th></tr></thead><tbody>
      ${d.barrios.map((b) => `<tr><td><b>${esc(b.nombre)}</b><small>zona ${esc(b.zona)}</small></td><td>${num(b.n)}</td>
        <td>${barra(b.informal_pct, C.naranja)} ${pct(b.informal_pct)}</td></tr>`).join('')}</tbody></table>`;
    $('#tabPares').innerHTML = `<table><thead><tr><th>Trayecto</th><th>Consultas</th><th>Informal</th></tr></thead><tbody>
      ${d.pares.map((p) => `<tr><td>${esc(p.origen)} → ${esc(p.destino)}</td><td>${num(p.n)}</td><td>${pct(p.informal_pct)}</td></tr>`).join('')}</tbody></table>`;
    // Mapa de calor
    const m = d.heatmap.matriz;
    const max = Math.max(1, ...m.flat());
    const horas = [...Array(24).keys()].filter((h) => h >= 4 && h <= 22);
    $('#tabHeat').innerHTML = `<div class="heat-grid" style="grid-template-columns: 40px repeat(${horas.length}, 1fr)">
      <span></span>${horas.map((h) => `<span class="heat-h">${h}</span>`).join('')}
      ${d.heatmap.dias.map((dia, i) => `<span class="heat-d">${dia}</span>${horas.map((h) => {
        const v = m[i][h];
        return `<span class="heat-c" style="--a:${(v / max).toFixed(3)}" title="${dia} ${h}:00 · ${num(v)} consultas"></span>`;
      }).join('')}`).join('')}</div>
      <div class="heat-ley"><span>menos</span><i></i><span>más consultas</span></div>`;
  }

  // ---------- Gráficos ----------
  function graficos(d) {
    const Ch = window.Chart;
    Ch.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Ch.defaults.color = '#5F6170';
    Ch.defaults.plugins.legend.labels.boxWidth = 12;
    const nuevo = (id, cfg) => { const el = document.getElementById(id); if (el) charts.push(new Ch(el, cfg)); };
    const horas = [...Array(24).keys()];
    const ph = d.por_hora;
    nuevo('chHoras', {
      data: {
        labels: horas.map((h) => `${h}h`),
        datasets: [
          { type: 'bar', label: 'Salen de la localidad', data: ph.salida, backgroundColor: C.morado, stack: 'c', yAxisID: 'y' },
          { type: 'bar', label: 'Regresan', data: ph.regreso, backgroundColor: C.lila, stack: 'c', yAxisID: 'y' },
          { type: 'bar', label: 'Dentro de la localidad', data: ph.interno, backgroundColor: '#D9C2E2', stack: 'c', yAxisID: 'y' },
          { type: 'line', label: '% de viajes informales llenos', data: ph.llenos_pct.map((v, h) => (ph.viajes_informales[h] >= 20 ? v : null)),
            borderColor: C.naranja, backgroundColor: C.naranja, yAxisID: 'y2', tension: 0.35, spanGaps: true, pointRadius: 3 },
        ],
      },
      options: {
        maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
        scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, title: { display: true, text: 'consultas' } },
          y2: { position: 'right', min: 0, max: 100, grid: { display: false }, ticks: { callback: (v) => `${v}%` } } },
        plugins: { legend: { position: 'bottom' } },
      },
    });
    const dona = (id, items, etiqueta, colores) => nuevo(id, {
      type: 'doughnut',
      data: { labels: items.map((x) => x.nombre), datasets: [{ data: items.map((x) => x[etiqueta]), backgroundColor: colores || PALETA, borderWidth: 2, borderColor: '#fff' }] },
      options: { maintainAspectRatio: false, cutout: '58%', plugins: { legend: { position: 'right' },
        tooltip: { callbacks: { label: (c) => ` ${c.label}: ${num(c.parsed)} (${pct(items[c.dataIndex].pct)})` } } } },
    });
    dona('chFinales', d.destinos_finales, 'consultas');
    dona('chMedios', d.medios, 'n', d.medios.map((m) => MEDIO_COLOR[m.modo] || C.gris));
    nuevo('chSalidas', {
      type: 'bar',
      data: { labels: d.salidas.map((s) => s.nombre), datasets: [{ label: 'consultas', data: d.salidas.map((s) => s.consultas), backgroundColor: C.morado, borderRadius: 6 }] },
      options: { indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false },
        tooltip: { callbacks: { label: (c) => ` ${num(c.parsed.x)} consultas (${pct(d.salidas[c.dataIndex].pct)}) · ${d.salidas[c.dataIndex].corredor}` } } },
        scales: { y: { grid: { display: false } } } },
    });
    nuevo('chSemanal', {
      type: 'line',
      data: { labels: d.semanal.map((s) => new Date(s.semana + 'T12:00:00').toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })),
        datasets: [{ label: 'vecinos activos', data: d.semanal.map((s) => s.usuarios), borderColor: C.verde,
          backgroundColor: 'rgba(18,161,80,.14)', fill: true, tension: 0.35, pointRadius: 4 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
    });
    nuevo('chTipos', {
      type: 'bar',
      data: { labels: d.reportes.por_tipo.map((t) => TIPOS[t.tipo] || t.tipo),
        datasets: [{ data: d.reportes.por_tipo.map((t) => t.n), backgroundColor: C.naranja, borderRadius: 6 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } } } },
    });
    dona('chCanales', d.reportes.por_canal.filter((c) => c.canal !== 'admin'), 'n', [C.morado, C.info, C.verde, C.gris]);
  }

  // ---------- Mapa de flujos ----------
  function mapaFlujos(d) {
    const el = $('#tabMapa');
    if (!el || !window.L) { if (el) el.innerHTML = '<p class="empty">Mapa no disponible sin conexión.</p>'; return; }
    mapa = L.map(el, { scrollWheelZoom: false, zoomControl: true, attributionControl: true });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 17, attribution: '© OpenStreetMap' }).addTo(mapa);
    const maxF = Math.max(1, ...d.flujos.map((f) => f.n));
    const maxFF = Math.max(1, ...d.flujos_finales.map((f) => f.n));
    // Salida → destino final (punteado, por debajo)
    d.flujos_finales.forEach((f) => {
      L.polyline([f.de, f.a], { color: C.info, weight: 2 + 10 * (f.n / maxFF), opacity: 0.55, dashArray: '6,8' })
        .bindTooltip(`${esc(f.salida)} → <b>${esc(f.final)}</b><br>${num(f.n)} consultas`, { sticky: true }).addTo(mapa);
    });
    // Barrio → salida (continua)
    d.flujos.forEach((f) => {
      L.polyline([f.de, f.a], { color: C.morado, weight: 2 + 12 * (f.n / maxF), opacity: 0.7, lineCap: 'round' })
        .bindTooltip(`${esc(f.origen)} → <b>${esc(f.salida)}</b><br>${num(f.n)} consultas`, { sticky: true }).addTo(mapa);
    });
    // Salidas (círculos proporcionales) y destinos finales
    const porSalida = {};
    d.flujos.forEach((f) => { porSalida[f.salida_id] = porSalida[f.salida_id] || { n: 0, p: f.a, nombre: f.salida }; porSalida[f.salida_id].n += f.n; });
    const maxS = Math.max(1, ...Object.values(porSalida).map((s) => s.n));
    Object.values(porSalida).forEach((s) => L.circleMarker(s.p, { radius: 7 + 14 * Math.sqrt(s.n / maxS), color: '#fff', weight: 2, fillColor: C.naranja, fillOpacity: 0.95 })
      .bindTooltip(`<b>${esc(s.nombre)}</b><br>${num(s.n)} salidas`, { direction: 'top' }).addTo(mapa));
    d.destinos_finales.filter((f) => f.id !== 'local').forEach((f) => L.marker([f.lat, f.lng], {
      icon: L.divIcon({ className: '', html: `<div class="dest-pin">${esc(f.nombre)}<b>${pct(f.pct)}</b></div>`, iconSize: null }),
    }).addTo(mapa));
    const encuadrar = () => {
      if (!mapa) return;
      mapa.invalidateSize();
      // Encuadre fijo: Ciudad Bolívar y las zonas de Bogotá a donde sigue el viaje (las veredas quedan al sur)
      mapa.fitBounds([[4.515, -74.215], [4.655, -74.055]], { padding: [10, 10] });
    };
    encuadrar();
    setTimeout(encuadrar, 300);  // el contenedor termina de medir su ancho después de pintar la grilla
  }

  // ---------- Resumen de la IA ----------
  async function resumen(nuevo = false) {
    const caja = $('#tabIaTexto'), fuente = $('#tabIaFuente');
    if (!caja) return;
    caja.className = 'tab-ia-texto cargando'; caja.innerHTML = '<span></span><span></span><span></span>';
    const r = await API.tableroResumen(dias, nuevo);
    if (!$('#tabIaTexto')) return;
    if (!r) { caja.className = 'tab-ia-texto'; caja.textContent = 'No pude pedir el análisis. Las conclusiones de abajo están calculadas con los datos.'; fuente.textContent = 'Sin conexión con la IA'; return; }
    caja.className = 'tab-ia-texto';
    const lineas = r.texto.split('\n').map((l) => l.trim()).filter(Boolean);
    const intro = lineas.filter((l) => !l.startsWith('•')).join(' ');
    const recs = lineas.filter((l) => l.startsWith('•')).map((l) => l.replace(/^•\s*/, ''));
    caja.innerHTML = (intro ? `<p>${esc(intro)}</p>` : '')
      + (recs.length ? `<ul>${recs.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : '');
    fuente.innerHTML = r.fuente === 'gemini'
      ? `Redactado por <b>Gemini</b> (${esc(r.modelo || '')}) con las cifras calculadas · ${new Date(r.generado_en).toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' })}`
      : 'IA no disponible: conclusiones calculadas con reglas';
  }

  // ---------- Ciclo ----------
  async function abrir() {
    const cont = $('#adminTablero');
    if (!cont || cargando) return;
    cargando = true;
    limpiar();
    cont.innerHTML = '<p class="empty"><span class="ms" aria-hidden="true">hourglass_top</span><br>Cargando el tablero…</p>';
    const [d, hayChart] = await Promise.all([API.tablero(dias), cargarChart()]);
    cargando = false;
    if (!d) { cont.innerHTML = '<p class="empty">No pude cargar el tablero. Revisa la conexión o la clave de administrador.</p>'; return; }
    cont.innerHTML = esqueleto(d);
    tablas(d);
    if (hayChart) graficos(d);
    else document.querySelectorAll('#adminTablero .tab-chart').forEach((c) => { c.innerHTML = '<p class="empty">Gráfico no disponible sin conexión.</p>'; });
    mapaFlujos(d);
    resumen();
  }

  function cerrar() { limpiar(); const c = $('#adminTablero'); if (c) c.innerHTML = ''; }

  document.addEventListener('click', async (e) => {
    const b = e.target.closest('#adminTablero button'); if (!b) return;
    if (b.dataset.dias) { dias = +b.dataset.dias; abrir(); }
    else if (b.dataset.acc === 'reanalizar') resumen(true);
    else if (b.dataset.acc === 'csv') {
      const blob = await API.tableroCsv(dias);
      if (!blob) { toast('No pude descargar el CSV'); return; }
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = `muevete_cb_tablero_${dias}d.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    }
  });

  return { abrir, cerrar };
})();
