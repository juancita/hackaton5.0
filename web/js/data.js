/*
 * data.js — Datos semilla de movilidad de Ciudad Bolívar
 * -------------------------------------------------------------------
 * Cruza el sistema FORMAL (TransMiCable + SITP) con el INFORMAL
 * (jeeps, colectivos, rutas veredales). Este es el corazón del reto:
 * la información informal hoy solo existe en el "boca a boca".
 *
 * Fuentes de referencia (a citar ante el jurado):
 *  - Secretaría Distrital de Movilidad (rutas SITP / TransMiCable)
 *  - Datos Abiertos Bogotá / datos.gov.co
 *  - IDECA (cartografía del Distrito)
 *  - Conocimiento comunitario (jeeperos, JAC) → reporte ciudadano
 *
 * lat/lng: coordenadas APROXIMADAS de Ciudad Bolívar (editables). Sirven para
 * el mapa tipo Waze. x,y: lienzo esquemático 0..100 para el mapa OFFLINE.
 */

const MODOS = {
  cable:     { nombre: 'TransMiCable', icono: '🚡', color: '#7B2FF7', formal: true },
  troncal:   { nombre: 'TransMilenio', icono: '🚍', color: '#E4002B', formal: true },
  sitp:      { nombre: 'SITP zonal',   icono: '🚌', color: '#1B75BB', formal: true },
  jeep:      { nombre: 'Jeep / camperos', icono: '🚙', color: '#F5A623', formal: false },
  colectivo: { nombre: 'Colectivo',    icono: '🚐', color: '#F58220', formal: false },
  veredal:   { nombre: 'Ruta veredal', icono: '🛻', color: '#8B5A2B', formal: false },
  caminando: { nombre: 'Caminando',    icono: '🚶', color: '#6B7280', formal: true },
};

// Paraderos y puntos de interés (nodos del grafo)
const PARADEROS = [
  // --- TransMiCable (4 estaciones reales) ---
  { id: 'tunal',      nombre: 'Portal Tunal',         tipo: 'portal',   x: 50, y: 92, zona: 'baja',  lat: 4.5749, lng: -74.1310 },
  { id: 'juanpablo',  nombre: 'Juan Pablo II',        tipo: 'cable',    x: 46, y: 70, zona: 'media', lat: 4.5710, lng: -74.1470 },
  { id: 'manitas',    nombre: 'Manitas',              tipo: 'cable',    x: 42, y: 50, zona: 'media', lat: 4.5760, lng: -74.1560 },
  { id: 'mirador',    nombre: 'Mirador (El Paraíso)', tipo: 'cable',    x: 38, y: 30, zona: 'alta',  lat: 4.5820, lng: -74.1620 },

  // --- Barrios / centralidades ---
  { id: 'perdomo',    nombre: 'Perdomo',              tipo: 'barrio',   x: 62, y: 84, zona: 'baja',  lat: 4.5940, lng: -74.1540 },
  { id: 'meissen',    nombre: 'Meissen',              tipo: 'barrio',   x: 58, y: 88, zona: 'baja',  lat: 4.5880, lng: -74.1490 },
  { id: 'sierramorena', nombre: 'Sierra Morena',      tipo: 'barrio',   x: 70, y: 62, zona: 'media', lat: 4.5980, lng: -74.1650 },
  { id: 'arborizadora', nombre: 'Arborizadora Alta',  tipo: 'barrio',   x: 66, y: 48, zona: 'alta',  lat: 4.5920, lng: -74.1690 },
  { id: 'lucero',     nombre: 'Lucero Alto',          tipo: 'barrio',   x: 52, y: 40, zona: 'alta',  lat: 4.5780, lng: -74.1600 },
  { id: 'jerusalen',  nombre: 'Jerusalén',            tipo: 'barrio',   x: 78, y: 44, zona: 'alta',  lat: 4.6000, lng: -74.1720 },
  { id: 'paraiso',    nombre: 'Paraíso Alto',         tipo: 'barrio',   x: 34, y: 20, zona: 'alta',  lat: 4.5850, lng: -74.1660 },
  { id: 'quiba',      nombre: 'Quiba (rural)',        tipo: 'vereda',   x: 20, y: 55, zona: 'rural', lat: 4.5600, lng: -74.1850 },
  { id: 'mochuelo',   nombre: 'Mochuelo Bajo',        tipo: 'vereda',   x: 30, y: 78, zona: 'rural', lat: 4.5450, lng: -74.1700 },
  { id: 'pasquilla',  nombre: 'Pasquilla (rural)',    tipo: 'vereda',   x: 14, y: 72, zona: 'rural', lat: 4.5300, lng: -74.1950 },

  // --- Puntos de interés ---
  { id: 'hospital',   nombre: 'Hospital Meissen',     tipo: 'salud',    x: 56, y: 90, zona: 'baja',  lat: 4.5900, lng: -74.1470 },
  { id: 'sena',       nombre: 'SENA / U. Distrital CB',tipo: 'educacion',x: 60, y: 80, zona: 'baja',  lat: 4.5910, lng: -74.1560 },
  { id: 'plaza',      nombre: 'Plaza de mercado Perdomo', tipo: 'comercio', x: 64, y: 82, zona: 'baja', lat: 4.5945, lng: -74.1550 },
];

/*
 * TRAMOS (aristas del grafo). Cada tramo conecta dos paraderos con un modo.
 */
const TRAMOS = [
  // === TransMiCable (formal) — la columna vertebral ===
  { de: 'tunal', a: 'juanpablo', modo: 'cable', min: 5, cop: 2950, freqMin: 1, ruta: 'Cable L1' },
  { de: 'juanpablo', a: 'manitas', modo: 'cable', min: 4, cop: 0, freqMin: 1, ruta: 'Cable L1' },
  { de: 'manitas', a: 'mirador', modo: 'cable', min: 5, cop: 0, freqMin: 1, ruta: 'Cable L1' },

  // === Troncal / Portal (formal) ===
  { de: 'tunal', a: 'perdomo', modo: 'troncal', min: 12, cop: 2950, freqMin: 6, ruta: 'Alimentador' },

  // === SITP zonal (formal) ===
  { de: 'tunal', a: 'meissen', modo: 'sitp', min: 10, cop: 2950, freqMin: 12, ruta: 'C15' },
  { de: 'meissen', a: 'perdomo', modo: 'sitp', min: 8, cop: 0, freqMin: 12, ruta: 'C15' },
  { de: 'perdomo', a: 'sierramorena', modo: 'sitp', min: 15, cop: 2950, freqMin: 15, ruta: '742' },
  { de: 'sierramorena', a: 'arborizadora', modo: 'sitp', min: 12, cop: 0, freqMin: 15, ruta: '742' },
  { de: 'meissen', a: 'hospital', modo: 'sitp', min: 4, cop: 0, freqMin: 12, ruta: 'C15' },
  { de: 'perdomo', a: 'sena', modo: 'sitp', min: 6, cop: 2950, freqMin: 10, ruta: '388' },
  { de: 'perdomo', a: 'plaza', modo: 'caminando', min: 5, cop: 0, freqMin: 0, ruta: 'a pie' },

  // === INFORMAL — el diferenciador ===
  { de: 'mirador', a: 'paraiso', modo: 'jeep', min: 8, cop: 1500, freqMin: 20, ruta: 'Jeep Paraíso' },
  { de: 'manitas', a: 'lucero', modo: 'colectivo', min: 10, cop: 1800, freqMin: 18, ruta: 'Colectivo Lucero' },
  { de: 'arborizadora', a: 'jerusalen', modo: 'colectivo', min: 9, cop: 1700, freqMin: 25, ruta: 'Colectivo Jerusalén' },
  { de: 'lucero', a: 'paraiso', modo: 'jeep', min: 12, cop: 2000, freqMin: 30, ruta: 'Jeep Alto' },
  { de: 'tunal', a: 'mochuelo', modo: 'veredal', min: 35, cop: 3000, freqMin: 40, ruta: 'Veredal Mochuelo' },
  { de: 'mochuelo', a: 'quiba', modo: 'veredal', min: 25, cop: 2500, freqMin: 60, ruta: 'Veredal Quiba' },
  { de: 'quiba', a: 'pasquilla', modo: 'veredal', min: 30, cop: 2500, freqMin: 90, ruta: 'Veredal Pasquilla' },
  { de: 'manitas', a: 'quiba', modo: 'jeep', min: 40, cop: 3500, freqMin: 60, ruta: 'Jeep Quiba' },
  { de: 'juanpablo', a: 'sierramorena', modo: 'caminando', min: 14, cop: 0, freqMin: 0, ruta: 'a pie' },
  { de: 'manitas', a: 'arborizadora', modo: 'caminando', min: 16, cop: 0, freqMin: 0, ruta: 'a pie' },
];

/*
 * CÁMARAS DE FOTODETECCIÓN — infraestructura existente de la Secretaría Distrital de
 * Movilidad. Hoy solo se muestran como marcadores de referencia en el mapa (sin detección).
 */
const CAMARAS = [
  { id: 'cam-villavicencio', nombre: 'Fotodetección Av. Villavicencio', tramo: { de: 'tunal', a: 'perdomo', modo: 'troncal' }, lat: 4.5850, lng: -74.1425 },
  { id: 'cam-tunal',    nombre: 'Fotodetección Portal Tunal',    tramo: { de: 'tunal', a: 'meissen', modo: 'sitp' }, lat: 4.5820, lng: -74.1400 },
  { id: 'cam-boyaca',   nombre: 'Fotodetección Av. Boyacá (Sierra Morena)', tramo: { de: 'perdomo', a: 'sierramorena', modo: 'sitp' }, lat: 4.5960, lng: -74.1600 },
  { id: 'cam-paraiso',  nombre: 'Fotodetección subida a Paraíso', tramo: { de: 'mirador', a: 'paraiso', modo: 'jeep' }, lat: 4.5835, lng: -74.1640 },
];

// Alias / apodos que la gente usa (para el buscador y el chat de IA)
const ALIAS = {
  'el cable': 'tunal', 'transmicable': 'tunal', 'portal': 'tunal', 'tunal': 'tunal',
  'paraiso': 'paraiso', 'el paraiso': 'paraiso', 'mirador': 'mirador',
  'sierra': 'sierramorena', 'sierra morena': 'sierramorena',
  'arborizadora': 'arborizadora', 'la arborizadora': 'arborizadora',
  'lucero': 'lucero', 'jerusalen': 'jerusalen', 'quiba': 'quiba',
  'pasquilla': 'pasquilla', 'mochuelo': 'mochuelo', 'meissen': 'meissen',
  'perdomo': 'perdomo', 'hospital': 'hospital', 'sena': 'sena',
  'universidad': 'sena', 'u distrital': 'sena', 'plaza': 'plaza', 'mercado': 'plaza',
  'manitas': 'manitas', 'juan pablo': 'juanpablo', 'juan pablo ii': 'juanpablo',
};

// Exponer global (sin módulos, para máxima compatibilidad offline)
window.DB = { MODOS, PARADEROS, TRAMOS, CAMARAS, ALIAS };
