/*
 * rides.js — Login por celular + módulo de VIAJES (conductores informales y cupos).
 * Aditivo: no toca el resto de app.js. Usa API (backend) y cae con mensajes si no hay servidor.
 *
 * Identidad unificada: entras con celular + nombre; el mismo número es la misma persona en la
 * app y en el bot de Telegram. Puedes usar la app como PASAJERO o como CONDUCTOR y alternar.
 */
window.Rides = (() => {
  const { PARADEROS } = window.DB;
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);
  // `ico` es global (icons.js)
  const nombrePlace = (id) => (Engine.nodoPorId[id] ? Engine.nodoPorId[id].nombre : id);
  const toast = (h, c) => (window.appToast ? window.appToast(h, c) : alert(h.replace(/<[^>]+>/g, '')));

  let perfil = null;          // {nombre, modo, es_conductor}
  let modoUI = 'pasajero';    // panel activo en la vista Viajes

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
      if (label) label.textContent = (perfil && perfil.nombre) ? perfil.nombre.split(' ')[0] : 'Mi cuenta';
      if (perfil && perfil.modo) setModoUI(perfil.modo);
    } else {
      perfil = null;
      if (label) label.textContent = 'Entrar';
    }
  }

  // ---------- Modal de login ----------
  function abrirLogin() { $('#loginModal').hidden = false; setTimeout(() => $('#loginTel').focus(), 50); }
  function cerrarLogin() { $('#loginModal').hidden = true; }
  let modoLogin = 'pasajero';

  function wireLogin() {
    $('#btnSesion').addEventListener('click', () => {
      if (API.logueado) {
        if (confirm(`Sesión de ${perfil && perfil.nombre ? perfil.nombre : 'usuario'}.\n¿Cerrar sesión?`)) {
          API.logout(); refrescarSesion(); toast('Sesión cerrada');
        }
      } else abrirLogin();
    });
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
      toast(`¡Bienvenido/a, ${nombre || 'vecino/a'}! ${ico('waving_hand')}`);
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
    // Cambiar de modo pasajero/conductor
    $$('#modoSwitch .modo').forEach((b) => b.addEventListener('click', async () => {
      setModoUI(b.dataset.modo);
      if (API.logueado) API.setModo(b.dataset.modo);
      abrir();
    }));
    $('#refViajes').addEventListener('click', () => cargarProximos());
    // Datalist de lugares para el conductor
    const dl = $('#lugaresV');
    if (dl && !dl.children.length) PARADEROS.forEach((p) => { const o = document.createElement('option'); o.value = p.nombre; dl.appendChild(o); });
    $('#cRuta') && ($('#cRuta').value = (perfil && perfil.ruta) || '');
    $('#btnAnunciar').addEventListener('click', anunciar);
  }

  async function abrir() {
    $('#viajesLogin').hidden = API.logueado;
    if (perfil && perfil.modo) setModoUI(perfil.modo);
    if (modoUI === 'conductor') { await cargarMisViajes(); } else { await cargarProximos(); }
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
          Object.entries(h).map(([ruta, hs]) => `<div class="rep-item viaje"><strong>${ico('local_taxi')} ${ruta}</strong><br><small>${ico('schedule')} Suele salir: ${hs.join(' · ')}</small></div>`).join('')
        : '<p class="empty">Sin conexión con el servidor.</p>';
      return;
    }
    if (!viajes.length) { cont.innerHTML = '<p class="empty">No hay viajes publicados ahora. Vuelve pronto o pídelo en el asistente.</p>'; return; }
    cont.innerHTML = viajes.map(tarjetaViaje).join('');
    $$('.btn-reservar').forEach((b) => b.addEventListener('click', () => reservar(b.dataset.id)));
  }

  function estadoBadge(v) {
    if (v.estado === 'en_ruta') return `<span class="vb ruta">${ico('directions_car')} en ruta</span>`;
    if (v.lleno || v.cupos_libres <= 0) return `<span class="vb lleno">lleno</span>`;
    return `<span class="vb libre">${v.cupos_libres} cupos</span>`;
  }
  function tarjetaViaje(v) {
    const lleno = v.lleno || v.cupos_libres <= 0;
    const accion = lleno
      ? `<button class="linkbtn ghost" disabled>Lleno</button>`
      : `<button class="linkbtn btn-reservar" data-id="${v.id}">${ico('event_seat')} Apartar cupo</button>`;
    return `<div class="rep-item viaje">
      <div class="viaje-top"><strong>${ico('local_taxi')} ${v.ruta}</strong>${estadoBadge(v)}</div>
      ${nombrePlace(v.origen_id)} → ${nombrePlace(v.destino_id)}
      <br><small>${ico('schedule')} ${v.hora} · ${v.driver_nombre || 'Conductor'} · ${v.esperando || 0} esperando</small>
      ${v.desvio ? `<div class="desvio">${ico('alt_route')} Desvío: ${v.desvio}</div>` : ''}
      <div class="viaje-acc">${accion}</div></div>`;
  }
  async function reservar(id) {
    if (!API.logueado) { toast('Entra con tu celular para apartar cupo'); return abrirLogin(); }
    const r = await API.reservar(id);
    if (!r) return toast('No se pudo reservar');
    if (!r.ok) return toast(r.data && r.data.detail ? r.data.detail : 'No se pudo reservar');
    toast(`${ico('check_circle')} ¡Cupo apartado! El conductor ya sabe que vas.`);
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
    // Asegura perfil de conductor con la ruta
    await API.perfilConductor({ ruta, barrio_base: origen_id });
    const r = await API.anunciarViaje({ origen_id, destino_id, hora, cupos, ruta });
    if (!r || !r.ok) return toast((r && r.data && r.data.detail) || 'No se pudo publicar');
    toast(`${ico('campaign')} Viaje publicado: ${ruta} a las ${hora}`);
    cargarMisViajes();
  }
  async function cargarMisViajes(silencioso = false) {
    const cont = $('#misViajes');
    if (!silencioso) cont.innerHTML = '<p class="empty">Cargando…</p>';
    if (!API.logueado) { cont.innerHTML = '<p class="empty">Entra con tu celular para gestionar tus viajes.</p>'; return; }
    const viajes = await API.misViajes();
    if (!viajes) { cont.innerHTML = '<p class="empty">Sin conexión.</p>'; return; }
    if (!viajes.length) { cont.innerHTML = '<p class="empty">Aún no has publicado viajes.</p>'; return; }
    cont.innerHTML = viajes.map(tarjetaMio).join('');
    $$('.acc-salir').forEach((b) => b.addEventListener('click', () => salir(b.dataset.id)));
    $$('.acc-lleno').forEach((b) => b.addEventListener('click', () => accion('lleno', b.dataset.id)));
    $$('.acc-fin').forEach((b) => b.addEventListener('click', () => accion('finalizar', b.dataset.id)));
    $$('.acc-desvio').forEach((b) => b.addEventListener('click', async () => {
      const nota = prompt('¿Por dónde te desvías y por qué? (ej: por la 68, hay protesta en la Distrital)');
      if (!nota) return;
      const r = await API.desvio(b.dataset.id, nota);
      if (!r || !r.ok) return toast('No se pudo avisar el desvío');
      toast(`${ico('alt_route')} Desvío avisado a tus pasajeros y a la comunidad`);
      cargarMisViajes();
    }));
  }
  function tarjetaMio(v) {
    const activo = v.estado !== 'finalizado';
    const acciones = activo ? `<div class="viaje-acc">
        ${v.estado === 'programado' ? `<button class="linkbtn acc-salir" data-id="${v.id}">${ico('my_location')} Ya salí</button>` : ''}
        <button class="linkbtn ghost acc-lleno" data-id="${v.id}">Lleno</button>
        <button class="linkbtn ghost acc-desvio" data-id="${v.id}">Desvío</button>
        <button class="linkbtn ghost acc-fin" data-id="${v.id}">Finalizar</button>
      </div>` : '';
    return `<div class="rep-item viaje">
      <div class="viaje-top"><strong>${ico('local_taxi')} ${v.ruta}</strong>${estadoBadge(v)}</div>
      ${nombrePlace(v.origen_id)} → ${nombrePlace(v.destino_id)}
      <br><small>${ico('schedule')} ${v.hora} · ${v.esperando || 0} pasajeros esperando</small>
      ${v.desvio ? `<div class="desvio">${ico('alt_route')} Desvío: ${v.desvio}</div>` : ''}
      ${acciones}</div>`;
  }
  async function salir(id) {
    toast('Compartiendo tu ubicación…');
    const [lat, lng] = await posicion();
    const r = await API.salir(id, lat, lng);
    if (!r || !r.ok) return toast((r && r.data && r.data.detail) || 'No se pudo marcar la salida');
    const v = r.data;
    toast(v.lleno ? `${ico('directions_car')} ¡En ruta y lleno! Avisado a tus pasajeros.` : `${ico('directions_car')} ¡En ruta! Tus pasajeros ya saben que saliste.`);
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
    // rides.js carga después del router de app.js: si se entra directo a #/viajes, abrir aquí
    refrescarSesion().then(() => { if (/^#\/?viajes/.test(location.hash)) abrir(); });
    // En vivo: mientras la vista Viajes está abierta se refresca sola ("en ruta", cupos, desvíos)
    setInterval(() => {
      const vista = document.getElementById('view-viajes');
      if (!vista || !vista.classList.contains('active') || document.hidden) return;
      if (modoUI === 'conductor') cargarMisViajes(true); else cargarProximos(true);
    }, 5000);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  return { abrir, refrescarSesion, abrirLogin };
})();
