/*
 * data.js — Red de movilidad de Ciudad Bolívar (fuente de verdad del front, OFFLINE)
 * ---------------------------------------------------------------------------------
 * GENERADO por backend/scripts/build_network.py — no editar a mano: cambia el script
 * y vuelve a correrlo (actualiza también backend/data/network.json).
 *
 * Cruza el sistema FORMAL (TransMiCable, alimentadores, SITP) con el INFORMAL
 * (jeeps, colectivos, veredales). Cada paradero y tramo trae su `fuente`:
 *  - ArcGIS TransMilenio / Secretaría Distrital de Movilidad (estaciones, paraderos,
 *    orden de paradas por ruta, trazado del cable) — el mismo de datos.gov.co.
 *  - OpenStreetMap / IDECA para veredas y equipamientos sin paradero SITP.
 *  - Conocimiento comunitario para lo informal (se valida con reporte ciudadano).
 *
 * lat/lng reales. x,y: lienzo esquemático 0..100 para el mapa OFFLINE.
 * geom: trazado [lat, lng] por las paradas reales de la ruta.
 */

const MODOS = {
  cable: {"nombre": "TransMiCable", "icono": "🚡", "color": "#7B2FF7", "formal": true},
  troncal: {"nombre": "TransMilenio", "icono": "🚍", "color": "#E4002B", "formal": true},
  alimentador: {"nombre": "Alimentador TM", "icono": "🚌", "color": "#00A650", "formal": true},
  sitp: {"nombre": "SITP zonal", "icono": "🚌", "color": "#1B75BB", "formal": true},
  jeep: {"nombre": "Jeep / camperos", "icono": "🚙", "color": "#F5A623", "formal": false},
  colectivo: {"nombre": "Colectivo", "icono": "🚐", "color": "#F58220", "formal": false},
  veredal: {"nombre": "Ruta veredal", "icono": "🛻", "color": "#8B5A2B", "formal": false},
  caminando: {"nombre": "Caminando", "icono": "🚶", "color": "#6B7280", "formal": true},
};

const PARADEROS = [
  {"id": "tunal", "nombre": "Portal Tunal", "tipo": "portal", "zona": "baja", "lat": 4.56957, "lng": -74.13924, "direccion": "Av. Boyaca - Av Villavicencio", "fuente": "ArcGIS TransMilenio · Troncal/consulta_estaciones_troncales", "x": 67, "y": 31},
  {"id": "juanpablo", "nombre": "Juan Pablo II", "tipo": "cable", "zona": "media", "lat": 4.55579, "lng": -74.14743, "direccion": "CL 67C Sur - 18P-13", "fuente": "ArcGIS TransMilenio · BRT/ConsultaEstacionesCable", "x": 51, "y": 44},
  {"id": "manitas", "nombre": "Manitas", "tipo": "cable", "zona": "media", "lat": 4.55028, "lng": -74.15052, "direccion": "KR 18L - 70G Sur", "fuente": "ArcGIS TransMilenio · BRT/ConsultaEstacionesCable", "x": 46, "y": 50},
  {"id": "mirador", "nombre": "Mirador (El Paraíso)", "tipo": "cable", "zona": "alta", "lat": 4.5501, "lng": -74.15885, "direccion": "KR 27B - CL 71H Sur", "fuente": "ArcGIS TransMilenio · BRT/ConsultaEstacionesCable", "x": 30, "y": 50},
  {"id": "estperdomo", "nombre": "Estación Perdomo (TransMilenio)", "tipo": "estacion", "zona": "baja", "lat": 4.59578, "lng": -74.16497, "direccion": "AutoSur-Kr78C", "fuente": "ArcGIS TransMilenio · Troncal/consulta_estaciones_troncales", "x": 18, "y": 6},
  {"id": "perdomo", "nombre": "Perdomo", "tipo": "barrio", "zona": "baja", "lat": 4.58945, "lng": -74.16434, "direccion": "CL 63 Sur - KR 70D", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (213B10, 193B10)", "x": 19, "y": 12},
  {"id": "meissen", "nombre": "Meissen", "tipo": "barrio", "zona": "baja", "lat": 4.55955, "lng": -74.13771, "direccion": "AC 60G Sur - KR 17", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (337A11, 342A11, 341A11)", "x": 70, "y": 41},
  {"id": "candelaria", "nombre": "Candelaria La Nueva", "tipo": "barrio", "zona": "media", "lat": 4.57349, "lng": -74.1531, "direccion": "AV. V/cio - KR 44C", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (453B11, 030B11, 453A11, 030A11)", "x": 41, "y": 27},
  {"id": "sierramorena", "nombre": "Sierra Morena", "tipo": "barrio", "zona": "media", "lat": 4.57781, "lng": -74.16987, "direccion": "DG 75 Sur - TV 73B", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (110A10, 111A10, 104A10)", "x": 9, "y": 23},
  {"id": "arborizadora", "nombre": "Arborizadora Alta", "tipo": "barrio", "zona": "alta", "lat": 4.56728, "lng": -74.15695, "direccion": "CL 69J Sur - KR 32", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (193A11, 192A11, 604A11)", "x": 33, "y": 33},
  {"id": "lucero", "nombre": "Lucero Alto", "tipo": "barrio", "zona": "alta", "lat": 4.55788, "lng": -74.14009, "direccion": "AV. Boyacá - KR 18Q", "fuente": "OpenStreetMap (Nominatim) / IDECA", "x": 65, "y": 42},
  {"id": "jerusalen", "nombre": "Jerusalén", "tipo": "barrio", "zona": "alta", "lat": 4.56725, "lng": -74.16771, "direccion": "KR 40 - CL 76 Sur", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (163A11, 161A11)", "x": 13, "y": 33},
  {"id": "paraiso", "nombre": "Paraíso Alto", "tipo": "barrio", "zona": "alta", "lat": 4.54916, "lng": -74.16325, "direccion": "DG 72A Sur - KR 27N", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (124A11)", "x": 21, "y": 51},
  {"id": "quiba", "nombre": "Quiba (rural)", "tipo": "vereda", "zona": "rural", "lat": 4.54278, "lng": -74.17021, "direccion": "Vereda Quiba", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (435A11)", "x": 8, "y": 57},
  {"id": "mochuelo", "nombre": "Mochuelo Bajo", "tipo": "vereda", "zona": "rural", "lat": 4.50828, "lng": -74.14819, "direccion": "Vía Mochuelo Bajo", "fuente": "OpenStreetMap (Nominatim) / IDECA", "x": 50, "y": 90},
  {"id": "pasquilla", "nombre": "Pasquilla (rural)", "tipo": "vereda", "zona": "rural", "lat": 4.44462, "lng": -74.15597, "direccion": "Vía Mochuelo - Pasquilla, centro poblado", "fuente": "OpenStreetMap (Nominatim) / IDECA", "x": 35, "y": 96},
  {"id": "hospital", "nombre": "Hospital Meissen", "tipo": "salud", "zona": "baja", "lat": 4.55957, "lng": -74.13845, "direccion": "KR 18B, Meissen (paradero Av. Boyacá - KR 18B)", "fuente": "OpenStreetMap (Nominatim) / IDECA", "x": 69, "y": 44},
  {"id": "sena", "nombre": "SENA Ciudad Bolívar", "tipo": "educacion", "zona": "alta", "lat": 4.57196, "lng": -74.16358, "direccion": "KR 46B, La Pradera (convenio ISPA-SENA Jerusalén)", "fuente": "OpenStreetMap (Nominatim) / IDECA", "x": 21, "y": 29},
  {"id": "udtecno", "nombre": "U. Distrital Sede Tecnológica", "tipo": "educacion", "zona": "baja", "lat": 4.57926, "lng": -74.15794, "direccion": "Av. Villavicencio - Av. Jorge Gaitán Cortés", "fuente": "OpenStreetMap (Nominatim) / IDECA", "x": 31, "y": 22},
  {"id": "plaza", "nombre": "Plaza de mercado Los Luceros", "tipo": "comercio", "zona": "alta", "lat": 4.54934, "lng": -74.13966, "direccion": "CL 69B Sur, La Alameda (Lucero)", "fuente": "OpenStreetMap (Nominatim) / IDECA", "x": 66, "y": 51},
];

const TRAMOS = [
  {"de": "tunal", "a": "juanpablo", "modo": "cable", "min": 5, "cop": 2950, "freqMin": 1, "ruta": "Cable L1", "geom": [[4.56919, -74.13968], [4.55581, -74.14742], [4.55579, -74.14743]], "fuente": "ArcGIS TransMilenio · BRT/consulta_trazados_cable"},
  {"de": "juanpablo", "a": "manitas", "modo": "cable", "min": 4, "cop": 0, "freqMin": 1, "ruta": "Cable L1", "geom": [[4.55581, -74.14742], [4.55028, -74.15052]], "fuente": "ArcGIS TransMilenio · BRT/consulta_trazados_cable"},
  {"de": "manitas", "a": "mirador", "modo": "cable", "min": 5, "cop": 0, "freqMin": 1, "ruta": "Cable L1", "geom": [[4.55028, -74.15052], [4.5501, -74.15885]], "fuente": "ArcGIS TransMilenio · BRT/consulta_trazados_cable"},
  {"de": "tunal", "a": "meissen", "modo": "sitp", "min": 4, "cop": 2950, "freqMin": 12, "ruta": "H602", "geom": [[4.56957, -74.13924], [4.5717, -74.13945], [4.56231, -74.13914], [4.55955, -74.13771]], "via": "Portal Tunal → Br. San Benito", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta H602, 2 paradas, 1.0 km); frecuencia estimada"},
  {"de": "tunal", "a": "hospital", "modo": "sitp", "min": 6, "cop": 2950, "freqMin": 12, "ruta": "H608", "geom": [[4.56957, -74.13924], [4.5717, -74.13945], [4.56206, -74.13917], [4.55891, -74.13923], [4.55957, -74.13845]], "via": "Portal Tunal → Br. Lucero Alto", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta H608, 3 paradas, 1.4 km); frecuencia estimada"},
  {"de": "tunal", "a": "perdomo", "modo": "sitp", "min": 18, "cop": 2950, "freqMin": 12, "ruta": "H622", "geom": [[4.56957, -74.13924], [4.57205, -74.13956], [4.56693, -74.1431], [4.56893, -74.14618], [4.57072, -74.14879], [4.57194, -74.15058], [4.5743, -74.15362], [4.57692, -74.15538], [4.57905, -74.15651], [4.58154, -74.15784], [4.58374, -74.1589], [4.58562, -74.15985], [4.58843, -74.16103], [4.58878, -74.164], [4.58945, -74.16434]], "via": "Portal Tunal → Br. Ismael Perdomo", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta H622, 13 paradas, 4.2 km); frecuencia estimada"},
  {"de": "tunal", "a": "candelaria", "modo": "sitp", "min": 9, "cop": 2950, "freqMin": 15, "ruta": "T25", "geom": [[4.56957, -74.13924], [4.56756, -74.13653], [4.56675, -74.14342], [4.56763, -74.14782], [4.5691, -74.14998], [4.57027, -74.15167], [4.57031, -74.15363], [4.57096, -74.15447], [4.57349, -74.1531]], "via": "Br. San Carlos → Br. Arborizadora", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta T25, 7 paradas, 2.1 km); frecuencia estimada"},
  {"de": "tunal", "a": "paraiso", "modo": "sitp", "min": 22, "cop": 2950, "freqMin": 15, "ruta": "H610", "geom": [[4.56957, -74.13924], [4.5717, -74.13945], [4.56206, -74.13917], [4.55891, -74.13923], [4.55455, -74.13858], [4.55396, -74.14005], [4.55294, -74.14287], [4.5534, -74.14383], [4.55194, -74.14499], [4.55015, -74.14748], [4.54785, -74.14792], [4.54693, -74.14938], [4.54518, -74.15106], [4.54585, -74.15291], [4.54787, -74.15465], [4.54895, -74.15657], [4.54646, -74.15866], [4.54717, -74.16106], [4.54916, -74.16325]], "via": "Portal Tunal → Br. Bella Flor", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta H610, 17 paradas, 5.2 km); frecuencia estimada"},
  {"de": "tunal", "a": "mochuelo", "modo": "alimentador", "min": 39, "cop": 2950, "freqMin": 20, "ruta": "6-18", "geom": [[4.56957, -74.13924], [4.57191, -74.13902], [4.57388, -74.13747], [4.57545, -74.13354], [4.57523, -74.13028], [4.57212, -74.12942], [4.57068, -74.13004], [4.56934, -74.13346], [4.56738, -74.13301], [4.56567, -74.13107], [4.56444, -74.12973], [4.56246, -74.13026], [4.56088, -74.13169], [4.55867, -74.13642], [4.55972, -74.13805], [4.56206, -74.13917], [4.55872, -74.13915], [4.5547, -74.13779], [4.5526, -74.13707], [4.54809, -74.13725], [4.54671, -74.13773], [4.54448, -74.13769], [4.54068, -74.13815], [4.53796, -74.13983], [4.53489, -74.14146], [4.53397, -74.14184], [4.531, -74.14214], [4.5225, -74.14273], [4.52012, -74.14559], [4.51422, -74.14646], [4.50899, -74.14702], [4.50828, -74.14819]], "via": "Pq. El Tunal → Br. Lagunitas", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta 6-18, 30 paradas, 10.5 km); frecuencia estimada"},
  {"de": "meissen", "a": "perdomo", "modo": "sitp", "min": 18, "cop": 2950, "freqMin": 15, "ruta": "C612", "geom": [[4.55955, -74.13771], [4.5589, -74.13875], [4.56278, -74.13858], [4.56693, -74.1431], [4.56853, -74.14553], [4.57111, -74.14932], [4.57177, -74.15027], [4.57399, -74.15328], [4.5767, -74.15525], [4.57871, -74.15632], [4.58154, -74.15784], [4.58374, -74.1589], [4.58562, -74.15985], [4.58843, -74.16103], [4.58945, -74.16434]], "via": "Hsp. de Meissen → Br. Madelena", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta C612, 13 paradas, 4.3 km); frecuencia estimada"},
  {"de": "meissen", "a": "mochuelo", "modo": "sitp", "min": 27, "cop": 2950, "freqMin": 30, "ruta": "796A", "geom": [[4.55955, -74.13771], [4.55868, -74.13867], [4.55472, -74.13729], [4.55278, -74.13662], [4.54687, -74.13665], [4.54619, -74.1376], [4.5444, -74.1376], [4.54173, -74.13782], [4.53807, -74.13967], [4.53449, -74.14156], [4.53081, -74.14197], [4.52248, -74.14261], [4.51988, -74.14554], [4.51424, -74.14641], [4.5092, -74.14689], [4.50719, -74.1473], [4.50698, -74.14746], [4.50899, -74.14702], [4.50828, -74.14819]], "via": "Hsp. de Meissen → Br. Lagunitas", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta 796A, 17 paradas, 6.3 km); frecuencia estimada"},
  {"de": "hospital", "a": "plaza", "modo": "sitp", "min": 5, "cop": 2950, "freqMin": 12, "ruta": "H633", "geom": [[4.55957, -74.13845], [4.55872, -74.13915], [4.5547, -74.13779], [4.5526, -74.13707], [4.54809, -74.13725], [4.54934, -74.13966]], "via": "Br. Lucero Alto → Br. Quintas del Sur", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta H633, 4 paradas, 1.2 km); frecuencia estimada"},
  {"de": "perdomo", "a": "sierramorena", "modo": "sitp", "min": 16, "cop": 2950, "freqMin": 15, "ruta": "T04", "geom": [[4.58945, -74.16434], [4.58924, -74.16739], [4.58691, -74.1669], [4.58497, -74.16875], [4.58382, -74.16963], [4.58227, -74.16951], [4.58081, -74.1688], [4.57933, -74.16735], [4.57846, -74.16651], [4.57844, -74.16773], [4.57923, -74.16997], [4.57712, -74.16912], [4.57471, -74.16747], [4.57314, -74.16697], [4.57049, -74.16868], [4.57302, -74.16694], [4.57462, -74.16726], [4.57724, -74.16903], [4.57781, -74.16987]], "via": "Br. Barlovento → Br. Sierra Morena III Sector", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta T04, 17 paradas, 3.8 km); frecuencia estimada"},
  {"de": "perdomo", "a": "sena", "modo": "sitp", "min": 12, "cop": 2950, "freqMin": 15, "ruta": "H600", "geom": [[4.58945, -74.16434], [4.58878, -74.164], [4.58822, -74.1658], [4.58768, -74.16762], [4.58649, -74.16876], [4.58497, -74.16875], [4.58382, -74.16963], [4.58227, -74.16951], [4.58081, -74.1688], [4.57933, -74.16735], [4.57846, -74.16651], [4.57844, -74.16773], [4.57923, -74.16997], [4.57712, -74.16912], [4.57547, -74.16737], [4.57429, -74.16579], [4.57196, -74.16358]], "via": "Br. Ismael Perdomo → Br. Sierra Morena III Sector", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta H600, 15 paradas, 2.8 km); frecuencia estimada"},
  {"de": "sierramorena", "a": "arborizadora", "modo": "sitp", "min": 9, "cop": 2950, "freqMin": 15, "ruta": "A618", "geom": [[4.57781, -74.16987], [4.57736, -74.17005], [4.57724, -74.16903], [4.57908, -74.16995], [4.57815, -74.16776], [4.57823, -74.16653], [4.57806, -74.16574], [4.57669, -74.16396], [4.57424, -74.16194], [4.57235, -74.16043], [4.57193, -74.15922], [4.57022, -74.1564], [4.56728, -74.15695]], "via": "Br. Sierra Morena TV 73G Bis B → Br. Arborizadora Alta Cl 69D S", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta A618, 11 paradas, 2.2 km); frecuencia estimada"},
  {"de": "candelaria", "a": "arborizadora", "modo": "sitp", "min": 3, "cop": 2950, "freqMin": 15, "ruta": "H618", "geom": [[4.57349, -74.1531], [4.5717, -74.15169], [4.57046, -74.15357], [4.57096, -74.15463], [4.56883, -74.15483], [4.56728, -74.15695]], "via": "Br. Candelaria La Nueva → Br. Arborizadora Alta", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta H618, 4 paradas, 0.6 km); frecuencia estimada"},
  {"de": "candelaria", "a": "juanpablo", "modo": "sitp", "min": 10, "cop": 2950, "freqMin": 15, "ruta": "H627", "geom": [[4.57349, -74.1531], [4.57412, -74.15385], [4.57274, -74.15228], [4.57047, -74.14892], [4.56763, -74.14782], [4.56647, -74.14672], [4.56277, -74.1456], [4.56161, -74.14719], [4.55908, -74.14957], [4.55579, -74.14743]], "via": "Br. Candelaria La Nueva → Br. Millán", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta H627, 8 paradas, 2.2 km); frecuencia estimada"},
  {"de": "hospital", "a": "juanpablo", "modo": "sitp", "min": 4, "cop": 2950, "freqMin": 15, "ruta": "D627", "geom": [[4.55957, -74.13845], [4.56236, -74.14135], [4.56184, -74.14297], [4.56112, -74.14532], [4.56034, -74.14803], [4.55916, -74.14947], [4.55579, -74.14743]], "via": "Br. Acacias Sur → Br. Millán", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta D627, 5 paradas, 1.0 km); frecuencia estimada"},
  {"de": "arborizadora", "a": "jerusalen", "modo": "alimentador", "min": 5, "cop": 2950, "freqMin": 10, "ruta": "6-9", "geom": [[4.56728, -74.15695], [4.56821, -74.15724], [4.57002, -74.1585], [4.56871, -74.16025], [4.56825, -74.16355], [4.56743, -74.16686], [4.56725, -74.16771]], "via": "Br. Arborizadora Alta I → Br. Jerusalén las Brisas", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta 6-9, 5 paradas, 1.2 km); frecuencia estimada"},
  {"de": "manitas", "a": "quiba", "modo": "sitp", "min": 14, "cop": 2950, "freqMin": 30, "ruta": "624", "geom": [[4.55028, -74.15052], [4.55034, -74.15085], [4.54802, -74.15084], [4.54659, -74.15051], [4.5451, -74.15111], [4.54569, -74.15215], [4.54615, -74.15368], [4.54784, -74.15472], [4.5488, -74.15661], [4.54672, -74.15935], [4.54761, -74.161], [4.54846, -74.16102], [4.54916, -74.16325], [4.54278, -74.17021], [4.54278, -74.17021]], "via": "Las Manitas → Quiba", "fuente": "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas (ruta 624, 13 paradas, 3.4 km); frecuencia estimada"},
  {"de": "udtecno", "a": "hospital", "modo": "sitp", "min": 20, "cop": 2950, "freqMin": 10, "ruta": "HG712", "geom": [[4.5797, -74.1571], [4.57576, -74.15499], [4.574, -74.15363], [4.57294, -74.1524], [4.5678, -74.1449], [4.56761, -74.14507], [4.56744, -74.14499], [4.56619, -74.14388], [4.56317, -74.14197], [4.56265, -74.1414], [4.56188, -74.14015], [4.56173, -74.13914], [4.56032, -74.13934], [4.55927, -74.13924]], "fuente": "ArcGIS TransMilenio (trazado) · Google Maps (tiempos, 24/09/2026)"},
  {"de": "udtecno", "a": "hospital", "modo": "sitp", "min": 22, "cop": 2950, "freqMin": 20, "ruta": "HC612", "geom": [[4.5797, -74.1571], [4.57576, -74.15499], [4.574, -74.15363], [4.57294, -74.1524], [4.5678, -74.1449], [4.56761, -74.14507], [4.56744, -74.14499], [4.56619, -74.14388], [4.56317, -74.14197], [4.56265, -74.1414], [4.56188, -74.14015], [4.56173, -74.13914], [4.56032, -74.13934], [4.55927, -74.13924]], "fuente": "ArcGIS TransMilenio (trazado) · Google Maps (tiempos, 24/09/2026)"},
  {"de": "udtecno", "a": "hospital", "modo": "sitp", "min": 22, "cop": 2950, "freqMin": 20, "ruta": "P44", "geom": [[4.5797, -74.1571], [4.57576, -74.15499], [4.574, -74.15363], [4.57294, -74.1524], [4.5678, -74.1449], [4.56761, -74.14507], [4.56744, -74.14499], [4.56619, -74.14388], [4.56317, -74.14197], [4.56265, -74.1414], [4.56188, -74.14015], [4.56173, -74.13914], [4.56032, -74.13934], [4.55927, -74.13924]], "fuente": "ArcGIS TransMilenio (trazado) · Google Maps (tiempos, 24/09/2026)"},
  {"de": "udtecno", "a": "hospital", "modo": "sitp", "min": 24, "cop": 2950, "freqMin": 7, "ruta": "H318", "geom": [[4.5797, -74.1571], [4.57576, -74.15499], [4.574, -74.15363], [4.57294, -74.1524], [4.5678, -74.1449], [4.56761, -74.14507], [4.56744, -74.14499], [4.56619, -74.14388], [4.56317, -74.14197], [4.56265, -74.1414], [4.56188, -74.14015], [4.56173, -74.13914], [4.56032, -74.13934], [4.55927, -74.13924]], "fuente": "ArcGIS TransMilenio (trazado) · Google Maps (tiempos, 24/09/2026)"},
  {"de": "udtecno", "a": "hospital", "modo": "sitp", "min": 28, "cop": 2950, "freqMin": 15, "ruta": "L613", "geom": [[4.5797, -74.1571], [4.57576, -74.15499], [4.574, -74.15363], [4.57294, -74.1524], [4.5678, -74.1449], [4.56761, -74.14507], [4.56744, -74.14499], [4.56619, -74.14388], [4.56317, -74.14197], [4.56265, -74.1414], [4.56188, -74.14015], [4.56173, -74.13914], [4.56032, -74.13934], [4.55927, -74.13924], [4.5527, -74.13703], [4.55254, -74.13683], [4.55265, -74.13669], [4.55283, -74.13668], [4.5591, -74.13886], [4.56029, -74.139], [4.56035, -74.13861], [4.55989, -74.1384]], "fuente": "ArcGIS TransMilenio (trazado) · Google Maps (tiempos, 24/09/2026)"},
  {"de": "meissen", "a": "hospital", "modo": "caminando", "min": 2, "cop": 0, "freqMin": 0, "ruta": "a pie", "fuente": "Distancia real 107 m"},
  {"de": "hospital", "a": "lucero", "modo": "caminando", "min": 6, "cop": 0, "freqMin": 0, "ruta": "a pie", "fuente": "Distancia real 340 m"},
  {"de": "estperdomo", "a": "perdomo", "modo": "caminando", "min": 15, "cop": 0, "freqMin": 0, "ruta": "a pie", "fuente": "Distancia real 920 m"},
  {"de": "candelaria", "a": "udtecno", "modo": "caminando", "min": 18, "cop": 0, "freqMin": 0, "ruta": "a pie", "fuente": "Distancia real 1087 m"},
  {"de": "jerusalen", "a": "sena", "modo": "caminando", "min": 15, "cop": 0, "freqMin": 0, "ruta": "a pie", "fuente": "Distancia real 904 m"},
  {"de": "mirador", "a": "paraiso", "modo": "jeep", "min": 8, "cop": 1500, "freqMin": 20, "ruta": "Jeep Paraíso", "fuente": "Conocimiento comunitario (por validar con reporte ciudadano)"},
  {"de": "manitas", "a": "lucero", "modo": "colectivo", "min": 10, "cop": 1800, "freqMin": 18, "ruta": "Colectivo Lucero", "fuente": "Conocimiento comunitario (por validar con reporte ciudadano)"},
  {"de": "arborizadora", "a": "jerusalen", "modo": "colectivo", "min": 9, "cop": 1700, "freqMin": 25, "ruta": "Colectivo Jerusalén", "fuente": "Conocimiento comunitario (por validar con reporte ciudadano)"},
  {"de": "lucero", "a": "paraiso", "modo": "jeep", "min": 12, "cop": 2000, "freqMin": 30, "ruta": "Jeep Alto", "fuente": "Conocimiento comunitario (por validar con reporte ciudadano)"},
  {"de": "tunal", "a": "mochuelo", "modo": "veredal", "min": 35, "cop": 3000, "freqMin": 40, "ruta": "Veredal Mochuelo", "fuente": "Conocimiento comunitario (por validar con reporte ciudadano)"},
  {"de": "mochuelo", "a": "quiba", "modo": "veredal", "min": 25, "cop": 2500, "freqMin": 60, "ruta": "Veredal Quiba", "fuente": "Conocimiento comunitario (por validar con reporte ciudadano)"},
  {"de": "mochuelo", "a": "pasquilla", "modo": "veredal", "min": 35, "cop": 2500, "freqMin": 90, "ruta": "Veredal Pasquilla", "fuente": "Conocimiento comunitario (por validar con reporte ciudadano)"},
  {"de": "manitas", "a": "quiba", "modo": "jeep", "min": 15, "cop": 3500, "freqMin": 60, "ruta": "Jeep Quiba", "fuente": "Conocimiento comunitario (por validar con reporte ciudadano)"},
];

const CAMARAS = [
  {"id": "cam-villavicencio", "nombre": "Fotodetección Av. Villavicencio (Candelaria)", "tramo": {"de": "tunal", "a": "perdomo", "modo": "sitp"}, "lat": 4.5727, "lng": -74.1522},
  {"id": "cam-tunal", "nombre": "Fotodetección Portal Tunal (Av. Boyacá)", "tramo": {"de": "tunal", "a": "meissen", "modo": "sitp"}, "lat": 4.5717, "lng": -74.1395},
  {"id": "cam-boyaca", "nombre": "Fotodetección Av. Boyacá (Br. México)", "tramo": {"de": "hospital", "a": "plaza", "modo": "sitp"}, "lat": 4.555, "lng": -74.1374},
  {"id": "cam-paraiso", "nombre": "Fotodetección subida a Paraíso", "tramo": {"de": "mirador", "a": "paraiso", "modo": "jeep"}, "lat": 4.5496, "lng": -74.161},
];

// Alias / apodos que la gente usa (para el buscador y el chat de IA)
const ALIAS = {
  "el cable": "tunal",
  "transmicable": "tunal",
  "portal": "tunal",
  "portal tunal": "tunal",
  "tunal": "tunal",
  "paraiso": "paraiso",
  "el paraiso": "paraiso",
  "mirador": "mirador",
  "mirador del paraiso": "mirador",
  "sierra": "sierramorena",
  "sierra morena": "sierramorena",
  "arborizadora": "arborizadora",
  "la arborizadora": "arborizadora",
  "lucero": "lucero",
  "jerusalen": "jerusalen",
  "quiba": "quiba",
  "quiba baja": "quiba",
  "pasquilla": "pasquilla",
  "mochuelo": "mochuelo",
  "meissen": "meissen",
  "perdomo": "perdomo",
  "ismael perdomo": "perdomo",
  "estacion perdomo": "estperdomo",
  "candelaria": "candelaria",
  "la candelaria": "candelaria",
  "hospital": "hospital",
  "sena": "sena",
  "universidad": "udtecno",
  "u distrital": "udtecno",
  "universidad distrital": "udtecno",
  "tecnologica": "udtecno",
  "sede tecnologica": "udtecno",
  "plaza": "plaza",
  "mercado": "plaza",
  "los luceros": "plaza",
  "manitas": "manitas",
  "juan pablo": "juanpablo",
  "juan pablo ii": "juanpablo",
};

// Exponer global (sin módulos, para máxima compatibilidad offline)
window.DB = { MODOS, PARADEROS, TRAMOS, CAMARAS, ALIAS };
