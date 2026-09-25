/*
 * rides.js — Login por celular, MIS LUGARES (casa / paradero) y módulo de VIAJES
 * (conductores informales, cupos, bajarse a mitad del trayecto, cortar el viaje).
 * Aditivo: usa API (backend) y la mini-API del planeador (window.appPlan, en app.js).
 *
 * Identidad unificada: entras con celular + nombre; el mismo número es la misma persona en la
 * app y en el bot de Telegram. Puedes usar la app como PASAJERO o como CONDUCTOR y alternar.
 */
window.Rides = (() => {
  const { PARADEROS } = window.DB;
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);
  // `ico` es global (icons.js)
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const nombrePlace = (id) => esc(Engine.nodoPorId[id] ? Engine.nodoPorId[id].nombre : id);
  const toast = (h, c) => (window.appToast ? window.appToast(h, c) : alert(h.replace(/<[^>]+>/g, '')));
  const paradasDe = (v) => (v.paradas && v.paradas.length ? v.paradas : [v.origen_id, v.destino_id]);
  const recorrido = (v) => paradasDe(v).map(nombrePlace).join(' → ');

  let perfil = null;          // {nombre, modo, es_conductor}
  let modoUI = 'pasajero';    // panel activo en la vista Viajes
  let lugares = [];           // lugares guardados: [{etiqueta, nombre, lat, lng, place_id}]

  // ---------- Ubicación (GPS con respaldo en http de LAN) ----------
  const CB = [4.5802, -74.1574];
  function posicion() {
    return new Promise((resolve) => {
      if (!window.isSecureContext || !navigator.geolocation) return resolve(CB);
      navigator.geolocation.getCurrentPosition(
        (p) => resolve([p.coords.latitude, p.coords.longitude]),
        () => resolve(CB), { enableHighAccuracy: true, timeout: 7000, maximumAge: 30000 });
    });
  }

  // ---------- Sesión ----------
  async function refrescarSesion() {
    const label = $('#sesionLabel');
    if (API.logueado) {
      perfil = await API.perfil();
      lugares = (await API.misLugares()) || [];
      if (label) label.textContent = (perfil && perfil.nombre) ? perfil.nombre.split(' ')[0] : 'Mi cuenta';
      if (perfil && perfil.modo) setModoUI(perfil.modo);
    } else {
      perfil = null; lugares = [];
      if (label) label.textContent = 'Entrar';
    }
    pintarAtajos();
  }
  const lugar = (etiqueta) => lugares.find((l) => l.etiqueta === etiqueta);

  // ---------- Mis lugares: casa y paradero (GPS o tocando el mapa) ----------
  async function guardarLugar(etiqueta, lat, lng) {
    const p = window.appPlan && window.appPlan.paraderoCercano(lat, lng);
    const nombre = `${etiqueta === 'casa' ? 'Mi casa' : 'Mi paradero'}${p ? ' (cerca de ' + p.nombre + ')' : ''}`;
    const r = await API.guardarLugar({ etiqueta, nombre, lat, lng, place_id: p ? p.id : null });
    if (!r || !r.ok) return toast('No se pudo guardar el lugar');
    lugares = (await API.misLugares()) || [];
    toast(`${ico(etiqueta === 'casa' ? 'home' : 'signpost')} ¡Guardado! ${esc(nombre)}`);
    pintarAtajos(); pintarPanel();
  }
  async function guardarAqui(etiqueta) {
    toast('Tomando tu ubicación…');
    const [lat, lng] = await posicion();
    guardarLugar(etiqueta, lat, lng);
  }
  function guardarEnMapa(etiqueta) {
    cerrarPanel();
    window.appPlan.elegirEnMapa(`Toca en el mapa dónde queda ${etiqueta === 'casa' ? 'tu casa' : 'tu paradero'}`,
      (lat, lng) => guardarLugar(etiqueta, lat, lng));
  }

  // Atajos en el planeador: salir de / ir a mi casa, ir a mi paradero, elegir en el mapa
  function pintarAtajos() {
    const cont = $('#lugaresRapidos');
    if (!cont) return;
    const casa = lugar('casa'), paradero = lugar('paradero');
    const chips = [];
    if (API.logueado) {
      if (casa && casa.place_id) {
        chips.push(`<button class="chip-l" data-acc="salir-casa">${ico('home')} Salir de mi casa</button>`);
        chips.push(`<button class="chip-l" data-acc="ir-casa">${ico('home')} Ir a mi casa</button>`);
      } else {
        chips.push(`<button class="chip-l suave" data-acc="guardar-casa">${ico('add_home')} Guardar mi casa</button>`);
      }
      if (paradero && paradero.place_id) chips.push(`<button class="chip-l" data-acc="ir-paradero">${ico('signpost')} Ir a mi paradero</button>`);
    }
    chips.push(`<button class="chip-l suave" data-acc="mapa">${ico('pin_drop')} Elegir en el mapa</button>`);
    cont.innerHTML = chips.join('');
  }
  function wireAtajos() {
    const cont = $('#lugaresRapidos');
    if (!cont) return;
    cont.addEventListener('click', (e) => {
      const b = e.target.closest('.chip-l'); if (!b) return;
      const casa = lugar('casa'), paradero = lugar('paradero');
      switch (b.dataset.acc) {
        case 'salir-casa': window.appPlan.fijar('origen', casa.place_id); break;
        case 'ir-casa': window.appPlan.fijar('destino', casa.place_id); break;
        case 'ir-paradero': window.appPlan.fijar('destino', paradero.place_id); break;
        case 'guardar-casa': abrirPanel(); break;
        case 'mapa':
          // Dos toques: primero de dónde sales, luego a dónde vas
          window.appPlan.elegirEnMapa('Toca en el mapa de dónde sales', (la, ln) => {
            const o = window.appPlan.paraderoCercano(la, ln);
            if (o) window.appPlan.fijar('origen', o.id);
            window.appPlan.elegirEnMapa('Ahora toca a dónde vas', (lb, lnb) => {
              const d = window.appPlan.paraderoCercano(lb, lnb);
              if (d) window.appPlan.fijar('destino', d.id);
            });
          });
          break;
      }
    });
  }

  // ---------- Panel de mi cuenta ----------
  function crearPanel() {
    if ($('#cuentaModal')) return;
    const div = document.createElement('div');
    div.id = 'cuentaModal'; div.className = 'modal'; div.hidden = true;
    div.innerHTML = `<div class="modal-card cuenta">
      <button class="modal-x" type="button" data-acc="cerrar" aria-label="Cerrar"><span class="ms">close</span></button>
      <div id="cuentaCuerpo"></div></div>`;
    document.body.appendChild(div);
    div.addEventListener('click', async (e) => {
      if (e.target.id === 'cuentaModal') return cerrarPanel();
      const b = e.target.closest('[data-acc]'); if (!b) return;
      const acc = b.dataset.acc;
      if (acc === 'cerrar') cerrarPanel();
      else if (acc === 'salir') { API.logout(); cerrarPanel(); await refrescarSesion(); toast('Sesión cerrada'); }
      else if (acc === 'modo') { await API.setModo(b.dataset.modo); await refrescarSesion(); pintarPanel(); }
      else if (acc === 'aqui') guardarAqui(b.dataset.etiqueta);
      else if (acc === 'mapa') guardarEnMapa(b.dataset.etiqueta);
    });
  }
  function filaLugar(etiqueta, titulo, icono) {
    const l = lugar(etiqueta);
    return `<div class="cuenta-lugar">
      <div><strong>${ico(icono)} ${titulo}</strong><br><small>${l ? esc(l.nombre) : 'Sin guardar'}</small></div>
      <div class="cuenta-acc">
        <button class="linkbtn ghost" data-acc="aqui" data-etiqueta="${etiqueta}">${ico('my_location')} Estoy aquí</button>
        <button class="linkbtn ghost" data-acc="mapa" data-etiqueta="${etiqueta}">${ico('pin_drop')} En el mapa</button>
      </div></div>`;
  }
  function pintarPanel() {
    const cuerpo = $('#cuentaCuerpo'); if (!cuerpo || !perfil) return;
    cuerpo.innerHTML = `<div class="admin-escudo" aria-hidden="true"><span class="ms">account_circle</span></div>
      <h2>Hola, ${esc(perfil.nombre || 'vecino/a')}</h2>
      <p class="hint">Tu número está guardado cifrado. Es la misma cuenta en la app y en el bot de Telegram.</p>
      <div class="modo-switch">
        <button class="modo ${perfil.modo !== 'conductor' ? 'activo' : ''}" data-acc="modo" data-modo="pasajero">${ico('person')}Pasajero</button>
        <button class="modo ${perfil.modo === 'conductor' ? 'activo' : ''}" data-acc="modo" data-modo="conductor">${ico('local_taxi')}Conductor</button>
      </div>
      <h3 class="cuenta-tit">Mis lugares</h3>
      ${filaLugar('casa', 'Mi casa', 'home')}
      ${filaLugar('paradero', 'Mi paradero para salir de la localidad', 'signpost')}
      <button class="linkbtn ghost salir" data-acc="salir">${ico('logout')} Cerrar sesión</button>`;
  }
  async function abrirPanel() {
    if (!API.logueado) return abrirLogin();
    crearPanel();
    if (!perfil) await refrescarSesion();
    pintarPanel(); $('#cuentaModal').hidden = false;
  }
  function cerrarPanel() { const m = $('#cuentaModal'); if (m) m.hidden = true; }

  // ---------- Modal de login ----------
  function abrirLogin() { $('#loginModal').hidden = false; setTimeout(() => $('#loginTel').focus(), 50); }
  function cerrarLogin() { $('#loginModal').hidden = true; }
  let modoLogin = 'pasajero';

  function wireLogin() {
    $('#btnSesion').addEventListener('click', () => (API.logueado ? abrirPanel() : abrirLogin()));
    $('#loginCerrar').addEventListener('click', cerrarLogin);
    $('#loginModal').addEventListener('click', (e) => { if (e.target.id === 'loginModal') cerrarLogin(); });
    $$('#loginModo .modo').forEach((b) => b.addEventListener('click', () => {
      modoLogin = b.dataset.modo;
      $$('#loginModo .modo').forEach((x) => x.classList.toggle('activo', x === b));
    }));
    $('#loginForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const tel = $('#loginTel').value.trim(), nombre = $('#loginNombre').value.trim();
      if (tel.replace(/\D/g, '').length < 7) return toast('Escribe un número de celular válido');
      const btn = $('#btnLogin'); btn.disabled = true; btn.textContent = 'Entrando…';
      const r = await API.login(tel, nombre, modoLogin);
      btn.disabled = false; btn.textContent = 'Entrar';
      if (!r) return toast('No se pudo conectar con el servidor');
      cerrarLogin();
      await refrescarSesion();
      toast(`¡Bienvenido/a, ${esc(nombre || 'vecino/a')}! ${ico('waving_hand')}`);
      if (!lugar('casa')) setTimeout(() => toast(`${ico('home')} Tip: guarda tu casa en tu cuenta y pide rutas con un toque`), 1500);
      abrir();
    });
  }

  // ---------- Vista Viajes ----------
  function setModoUI(modo) {
    modoUI = modo === 'conductor' ? 'conductor' : 'pasajero';
    $$('#modoSwitch .modo').forEach((b) => b.classList.toggle('activo', b.dataset.modo === modoUI));
    $('#panelPasajero').hidden = modoUI !== 'pasajero';
    $('#panelConductor').hidden = modoUI !== 'conductor';
  }

  function wireViajes() {
    $$('#modoSwitch .modo').forEach((b) => b.addEventListener('click', async () => {
      setModoUI(b.dataset.modo);
      if (API.logueado) API.setModo(b.dataset.modo);
      abrir();
    }));
    $('#refViajes').addEventListener('click', () => cargarProximos());
    const dl = $('#lugaresV');
    if (dl && !dl.children.length) PARADEROS.forEach((p) => { const o = document.createElement('option'); o.value = p.nombre; dl.appendChild(o); });
    $('#btnAnunciar').addEventListener('click', anunciar);
    // Delegación de eventos (las tarjetas se repintan cada 5 s)
    $('#listaViajes').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.classList.contains('btn-reservar')) pedirBajada(b.dataset.id);
      else if (b.classList.contains('btn-baja')) reservar(b.dataset.id, b.dataset.baja || null);
    });
    $('#misViajes').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      const id = b.dataset.id;
      if (b.classList.contains('acc-salir')) salir(id);
      else if (b.classList.contains('acc-lleno')) accion('lleno', id);
      else if (b.classList.contains('acc-fin')) accion('finalizar', id);
      else if (b.classList.contains('acc-desvio')) desvio(id);
      else if (b.classList.contains('acc-cortar')) { const box = $(`#corte-${id}`); if (box) box.hidden = !box.hidden; }
      else if (b.classList.contains('acc-corte')) cortar(id, b.dataset.parada);
    });
  }

  async function abrir() {
    $('#viajesLogin').hidden = API.logueado;
    if (perfil && perfil.modo) setModoUI(perfil.modo);
    if (modoUI === 'conductor') { await cargarMisViajes(); } else { await cargarProximos(); }
  }

  // -- Avisos de MIS cupos (la app avisa si mi jeep salió, cortó o se desvió) --
  const KEY_CUPOS = 'muevecb_mis_cupos';
  const leerCupos = () => { try { return JSON.parse(localStorage.getItem(KEY_CUPOS)) || {}; } catch (e) { return {}; } };
  const guardarCupos = (c) => { try { localStorage.setItem(KEY_CUPOS, JSON.stringify(c)); } catch (e) {} };
  function revisarMisCupos(viajes) {
    const mios = leerCupos();
    let cambio = false;
    viajes.forEach((v) => {
      const antes = mios[v.id]; if (!antes) return;
      if (v.estado === 'en_ruta' && antes.estado !== 'en_ruta') toast(`${ico('directions_car')} <b>¡Tu ${esc(v.ruta)} ya salió!</b><br>${recorrido(v)}`, '#2E7D32');
      if (v.corta_en && v.corta_en !== antes.corta_en) toast(`${ico('content_cut')} <b>Tu viaje llega solo hasta ${nombrePlace(v.corta_en)}</b><br>Si ibas más allá, busca otra opción.`, '#E4002B');
      if (v.desvio && v.desvio !== antes.desvio) toast(`${ico('alt_route')} <b>Tu viaje va por desvío</b><br>${esc(v.desvio)}`, '#F58220');
      if (v.estado !== antes.estado || v.corta_en !== antes.corta_en || v.desvio !== antes.desvio) {
        mios[v.id] = { estado: v.estado, corta_en: v.corta_en, desvio: v.desvio }; cambio = true;
      }
    });
    if (cambio) guardarCupos(mios);
  }

  // -- Pasajero: próximos viajes + reservar --
  async function cargarProximos(silencioso = false) {
    const cont = $('#listaViajes');
    if (!silencioso) cont.innerHTML = '<p class="empty">Cargando…</p>';
    const viajes = await API.proximos();
    API.horarios().then((h) => { if (h && Object.keys(h).length) try { localStorage.setItem('muevecb_horarios', JSON.stringify(h)); } catch (e) {} });
    if (!viajes) {
      // OFFLINE: se muestran los horarios típicos aprendidos del historial de los conductores
      let h = null; try { h = JSON.parse(localStorage.getItem('muevecb_horarios')); } catch (e) {}
      cont.innerHTML = h && Object.keys(h).length
        ? `<p class="hint">${ico('cloud_off')} Sin conexión. Horarios típicos (aprendidos del historial de los conductores):</p>` +
          Object.entries(h).map(([ruta, hs]) => `<div class="rep-item viaje"><strong>${ico('local_taxi')} ${esc(ruta)}</strong><br><small>${ico('schedule')} Suele salir: ${hs.map(esc).join(' · ')}</small></div>`).join('')
        : '<p class="empty">Sin conexión con el servidor.</p>';
      return;
    }
    revisarMisCupos(viajes);
    if (!viajes.length) { cont.innerHTML = '<p class="empty">No hay viajes publicados ahora. Vuelve pronto o pídelo en el asistente.</p>'; return; }
    const abiertos = new Set([...$$('.bajadas:not([hidden])')].map((x) => x.dataset.id));
    cont.innerHTML = viajes.map((v) => tarjetaViaje(v, abiertos.has(v.id))).join('');
  }

  function estadoBadge(v) {
    if (v.estado === 'en_ruta') return `<span class="vb ruta">${ico('directions_car')} en ruta</span>`;
    if (v.lleno || v.cupos_libres <= 0) return `<span class="vb lleno">lleno</span>`;
    return `<span class="vb libre">${v.cupos_libres} cupos</span>`;
  }
  const corteHtml = (v) => (v.corta_en ? `<div class="desvio corte">${ico('content_cut')} Llega solo hasta ${nombrePlace(v.corta_en)}</div>` : '');
  const desvioHtml = (v) => (v.desvio ? `<div class="desvio">${ico('alt_route')} Desvío: ${esc(v.desvio)}</div>` : '');

  function tarjetaViaje(v, abierto = false) {
    const lleno = v.lleno || v.cupos_libres <= 0;
    const ps = paradasDe(v);
    const bajadas = ps.slice(1).map((p, i) => `<button class="linkbtn ${i === ps.length - 2 ? '' : 'ghost'} btn-baja" data-id="${v.id}" data-baja="${i === ps.length - 2 ? '' : p}">
        ${ico(i === ps.length - 2 ? 'flag' : 'logout')} ${i === ps.length - 2 ? 'Voy hasta ' : 'Me bajo en '}${nombrePlace(p)}</button>`).join('');
    const accion = lleno
      ? `<button class="linkbtn ghost" disabled>Lleno</button>`
      : `<button class="linkbtn btn-reservar" data-id="${v.id}">${ico('event_seat')} Apartar cupo</button>`;
    return `<div class="rep-item viaje">
      <div class="viaje-top"><strong>${ico('local_taxi')} ${esc(v.ruta)}</strong>${estadoBadge(v)}</div>
      ${recorrido(v)}
      <br><small>${ico('schedule')} ${esc(v.hora)} · ${esc(v.driver_nombre || 'Conductor')} · ${v.esperando || 0} esperando</small>
      ${corteHtml(v)}${desvioHtml(v)}
      <div class="viaje-acc">${accion}</div>
      <div class="bajadas viaje-acc" data-id="${v.id}" ${abierto ? '' : 'hidden'}><small class="bajadas-tit">¿Hasta dónde vas?</small>${bajadas}</div></div>`;
  }
  function pedirBajada(id) {
    if (!API.logueado) { toast('Entra con tu celular para apartar cupo'); return abrirLogin(); }
    const box = document.querySelector(`.bajadas[data-id="${id}"]`);
    if (!box) return reservar(id, null);
    // Si el viaje no tiene paradas intermedias, se reserva directo
    if (box.querySelectorAll('.btn-baja').length <= 1) return reservar(id, null);
    box.hidden = !box.hidden;
  }
  async function reservar(id, baja_en) {
    if (!API.logueado) { toast('Entra con tu celular para apartar cupo'); return abrirLogin(); }
    const r = await API.reservar(id, baja_en);
    if (!r) return toast('No se pudo reservar');
    if (!r.ok) return toast(r.data && r.data.detail ? esc(r.data.detail) : 'No se pudo reservar');
    const v = r.data;
    const mios = leerCupos(); mios[v.id] = { estado: v.estado, corta_en: v.corta_en, desvio: v.desvio }; guardarCupos(mios);
    toast(`${ico('check_circle')} ¡Cupo apartado${baja_en ? ', te bajas en ' + nombrePlace(baja_en) : ''}! El conductor ya sabe que vas. Te avisamos cuando salga.`);
    cargarProximos();
  }

  // -- Conductor: anunciar + gestionar --
  async function anunciar() {
    if (!API.logueado) { toast('Entra con tu celular para publicar viajes'); return abrirLogin(); }
    const ruta = $('#cRuta').value.trim();
    const origen_id = Engine.resolver($('#cOrigen').value);
    const destino_id = Engine.resolver($('#cDestino').value);
    const hora = $('#cHora').value;
    const cupos = parseInt($('#cCupos').value, 10) || 1;
    if (!origen_id || !destino_id) return toast('Elige un origen y destino válidos');
    await API.perfilConductor({ ruta, barrio_base: origen_id });
    const r = await API.anunciarViaje({ origen_id, destino_id, hora, cupos, ruta });
    if (!r || !r.ok) return toast(esc((r && r.data && r.data.detail) || 'No se pudo publicar'));
    toast(`${ico('campaign')} Viaje publicado: ${recorrido(r.data)} a las ${esc(hora)}`);
    cargarMisViajes();
  }
  async function cargarMisViajes(silencioso = false) {
    const cont = $('#misViajes');
    if (!silencioso) cont.innerHTML = '<p class="empty">Cargando…</p>';
    if (!API.logueado) { cont.innerHTML = '<p class="empty">Entra con tu celular para gestionar tus viajes.</p>'; return; }
    const viajes = await API.misViajes();
    if (!viajes) { cont.innerHTML = '<p class="empty">Sin conexión.</p>'; return; }
    if (!viajes.length) { cont.innerHTML = '<p class="empty">Aún no has publicado viajes.</p>'; return; }
    const abiertos = new Set([...$$('.cortes:not([hidden])')].map((x) => x.dataset.id));
    cont.innerHTML = viajes.map((v) => tarjetaMio(v, abiertos.has(v.id))).join('');
  }
  function tarjetaMio(v, cortesAbiertos = false) {
    const activo = v.estado !== 'finalizado';
    const intermedias = paradasDe(v).slice(1, -1);
    const acciones = activo ? `<div class="viaje-acc">
        ${v.estado === 'programado' ? `<button class="linkbtn acc-salir" data-id="${v.id}">${ico('my_location')} Ya salí</button>` : ''}
        <button class="linkbtn ghost acc-lleno" data-id="${v.id}">Lleno</button>
        ${intermedias.length && !v.corta_en ? `<button class="linkbtn ghost acc-cortar" data-id="${v.id}">${ico('content_cut')} Cortar</button>` : ''}
        <button class="linkbtn ghost acc-desvio" data-id="${v.id}">Desvío</button>
        <button class="linkbtn ghost acc-fin" data-id="${v.id}">Finalizar</button>
      </div>
      <div id="corte-${v.id}" class="cortes viaje-acc" data-id="${v.id}" ${cortesAbiertos ? '' : 'hidden'}><small class="bajadas-tit">¿Hasta dónde llegas?</small>
        ${intermedias.map((p) => `<button class="linkbtn acc-corte" data-id="${v.id}" data-parada="${p}">${ico('content_cut')} Llego hasta ${nombrePlace(p)}</button>`).join('')}
      </div>` : '';
    return `<div class="rep-item viaje">
      <div class="viaje-top"><strong>${ico('local_taxi')} ${esc(v.ruta)}</strong>${estadoBadge(v)}</div>
      ${recorrido(v)}
      <br><small>${ico('schedule')} ${esc(v.hora)} · ${v.esperando || 0} pasajeros esperando</small>
      ${corteHtml(v)}${desvioHtml(v)}
      ${acciones}</div>`;
  }
  async function salir(id) {
    toast('Compartiendo tu ubicación…');
    const [lat, lng] = await posicion();
    const r = await API.salir(id, lat, lng);
    if (!r || !r.ok) return toast(esc((r && r.data && r.data.detail) || 'No se pudo marcar la salida'));
    toast(r.data.lleno ? `${ico('directions_car')} ¡En ruta y lleno! Avisado a tus pasajeros.` : `${ico('directions_car')} ¡En ruta! Tus pasajeros ya saben que saliste.`);
    cargarMisViajes();
  }
  async function cortar(id, parada) {
    const r = await API.cortar(id, parada);
    if (!r || !r.ok) return toast(esc((r && r.data && r.data.detail) || 'No se pudo cortar el viaje'));
    toast(`${ico('content_cut')} Tu viaje llega hasta ${nombrePlace(parada)}. Avisamos a ${r.data.afectados} pasajero(s) que iban más allá.`);
    cargarMisViajes();
  }
  async function desvio(id) {
    const nota = prompt('¿Por dónde te desvías y por qué? (ej: por la 68, hay protesta en la Distrital)');
    if (!nota) return;
    const r = await API.desvio(id, nota);
    if (!r || !r.ok) return toast('No se pudo avisar el desvío');
    toast(`${ico('alt_route')} Desvío avisado a tus pasajeros y a la comunidad`);
    cargarMisViajes();
  }
  async function accion(tipo, id) {
    const r = tipo === 'lleno' ? await API.lleno(id) : await API.finalizar(id);
    if (!r || !r.ok) return toast('No se pudo actualizar');
    toast(tipo === 'lleno' ? 'Marcado como lleno' : 'Viaje finalizado');
    cargarMisViajes();
  }

  // ---------- Init ----------
  function init() {
    if (!$('#btnSesion')) return;
    wireLogin();
    wireViajes();
    wireAtajos();
    // rides.js carga después del router de app.js: si se entra directo a #/viajes, abrir aquí
    refrescarSesion().then(() => { if (/^#\/?viajes/.test(location.hash)) abrir(); });
    // En vivo: la vista Viajes se refresca sola; además revisa MIS cupos aunque esté en otra pestaña
    setInterval(() => {
      if (document.hidden) return;
      const vista = document.getElementById('view-viajes');
      const enViajes = vista && vista.classList.contains('active');
      if (enViajes) { if (modoUI === 'conductor') cargarMisViajes(true); else cargarProximos(true); }
      else if (Object.keys(leerCupos()).length) API.proximos().then((vs) => vs && revisarMisCupos(vs));
    }, 5000);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  return { abrir, refrescarSesion, abrirLogin, abrirPanel };
})();
