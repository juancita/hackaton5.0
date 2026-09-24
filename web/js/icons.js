/*
 * icons.js — Iconos de la interfaz (Material Symbols Rounded, ver look-and-feel.md)
 * ---------------------------------------------------------------------------------
 * Los datos compartidos con el backend (MODOS[].icono, Reports.TIPOS[].icono) siguen
 * siendo emojis porque viajan como texto a WhatsApp/Telegram. La web usa estos nombres.
 */

const ICONO_MODO = {
  cable: 'gondola_lift', troncal: 'directions_bus', alimentador: 'directions_bus', sitp: 'directions_bus',
  jeep: 'directions_car', colectivo: 'airport_shuttle', veredal: 'local_shipping', caminando: 'directions_walk',
};
const ICONO_TIPO = {
  derrumbe: 'landslide', bloqueo: 'construction', trancon: 'traffic',
  lleno: 'groups', sinservicio: 'do_not_disturb_on', novedad: 'info',
};
const ICONO_CANAL = { whatsapp: 'chat', telegram: 'send', web: 'public' };

/** <span> con el icono; `cls` agrega clases extra (p. ej. 'fill'). */
const ico = (nombre, cls = '') => `<span class="ms${cls ? ' ' + cls : ''}" aria-hidden="true">${nombre}</span>`;
const icoModo = (modo) => ico(ICONO_MODO[modo] || 'directions_bus');
const icoTipo = (tipo) => ico(ICONO_TIPO[tipo] || 'info');
const icoCanal = (canal) => ico(ICONO_CANAL[canal] || 'public');

/** Quita el emoji inicial de textos que vienen del backend (p. ej. el `motivo` de un tramo). */
const sinEmoji = (s) => String(s || '').replace(/^(\p{Extended_Pictographic}|️|‍|\s)+/u, '');
