"""Reconstruye la red semilla (fuente de verdad) desde las fuentes oficiales del reto.

    python -m scripts.build_network            # desde backend/, consulta en vivo
    python -m scripts.build_network --cache .cache/fuentes   # guarda/reutiliza las respuestas

Escribe:
  - backend/data/network.json  (lo carga el backend: JsonCatalog)
  - web/js/data.js             (lo carga el front offline; mismo contenido)

Fuentes (IMG_0473, "Fuentes de Datos y Referencias Territoriales"):
  - TransMilenio / Secretaría Distrital de Movilidad, ArcGIS REST (el mismo que publica
    datos.gov.co y Datos Abiertos Bogotá):
      BRT/ConsultaEstacionesCable      estaciones TransMiCable
      BRT/consulta_trazados_cable      trazado del cable
      Troncal/consulta_estaciones_troncales
      Zonal/consulta_paraderos_rutas   paraderos SITP con el orden de cada ruta
  - OpenStreetMap / IDECA: veredas y equipamientos que el SITP no cubre.
  - Conocimiento comunitario: tramos informales (jeeps, colectivos, veredales).

Ojo: la capa Zonal/consulta_paraderos_zonales trae nombres y coordenadas cruzados
(p. ej. "Br. Juan Pablo II" en el norte de Bogotá). Por eso se usa consulta_paraderos_rutas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

ARCGIS = "https://gis.transmilenio.gov.co/arcgis/rest/services"
# OSRM sobre OpenStreetMap (servidor público de FOSSGIS): pega los trazados a las calles.
OSRM = {"carro": "https://routing.openstreetmap.de/routed-car", "pie": "https://routing.openstreetmap.de/routed-foot"}
BBOX_CB = "-74.215,4.47,-74.105,4.605"  # lngMin,latMin,lngMax,latMax (Ciudad Bolívar + borde)
BACKEND = Path(__file__).resolve().parents[1]
NETWORK_JSON = BACKEND / "data" / "network.json"
DATA_JS = BACKEND.parent / "web" / "js" / "data.js"

FUENTE_SITP = "ArcGIS TransMilenio · Zonal/consulta_paraderos_rutas"
FUENTE_CABLE = "ArcGIS TransMilenio · BRT/ConsultaEstacionesCable"
FUENTE_TRONCAL = "ArcGIS TransMilenio · Troncal/consulta_estaciones_troncales"
FUENTE_OSM = "OpenStreetMap (Nominatim) / IDECA"
FUENTE_COMUNIDAD = "Conocimiento comunitario (por validar con reporte ciudadano)"
FUENTE_CALLES = "trazado por las calles: OSRM / OpenStreetMap"

VEL_SITP_KMH = 14      # bus zonal en ladera, con paradas
VEL_ALIM_KMH = 16      # alimentador
VEL_PIE_M_MIN = 60     # a pie, con pendiente
VEL_INFORMAL_KMH = {"jeep": 14, "colectivo": 15, "veredal": 20}  # ladera y destapado, con paradas a pedido
TARIFA = 2950          # tarifa usada en todo el prototipo

MODOS = {
    "cable": {"nombre": "TransMiCable", "icono": "🚡", "color": "#7B2FF7", "formal": True},
    "troncal": {"nombre": "TransMilenio", "icono": "🚍", "color": "#E4002B", "formal": True},
    "alimentador": {"nombre": "Alimentador TM", "icono": "🚌", "color": "#00A650", "formal": True},
    "sitp": {"nombre": "SITP zonal", "icono": "🚌", "color": "#1B75BB", "formal": True},
    "jeep": {"nombre": "Jeep / camperos", "icono": "🚙", "color": "#F5A623", "formal": False},
    "colectivo": {"nombre": "Colectivo", "icono": "🚐", "color": "#F58220", "formal": False},
    "veredal": {"nombre": "Ruta veredal", "icono": "🛻", "color": "#8B5A2B", "formal": False},
    "caminando": {"nombre": "Caminando", "icono": "🚶", "color": "#6B7280", "formal": True},
}

# --- Lugares ------------------------------------------------------------------
# ancla: ("cable", NOMBRE) | ("troncal", nombre) | ("paraderos", [cenefas]) | ("fijo", lat, lng)
LUGARES = [
    # TransMiCable Ciudad Bolívar (4 estaciones oficiales)
    dict(id="tunal", nombre="Portal Tunal", tipo="portal", zona="baja", ancla=("troncal", "Portal Tunal")),
    dict(id="juanpablo", nombre="Juan Pablo II", tipo="cable", zona="media", ancla=("cable", "JUAN PABLO II")),
    dict(id="manitas", nombre="Manitas", tipo="cable", zona="media", ancla=("cable", "MANITAS")),
    dict(id="mirador", nombre="Mirador (El Paraíso)", tipo="cable", zona="alta", ancla=("cable", "MIRADOR DEL PARAISO")),
    dict(id="estperdomo", nombre="Estación Perdomo (TransMilenio)", tipo="estacion", zona="baja",
         ancla=("troncal", "Perdomo")),
    # Barrios: centro de sus paraderos SITP oficiales
    dict(id="perdomo", nombre="Perdomo", tipo="barrio", zona="baja", ancla=("paraderos", ["213B10", "193B10"])),
    dict(id="meissen", nombre="Meissen", tipo="barrio", zona="baja", ancla=("paraderos", ["337A11", "342A11", "341A11"])),
    dict(id="candelaria", nombre="Candelaria La Nueva", tipo="barrio", zona="media",
         ancla=("paraderos", ["453B11", "030B11", "453A11", "030A11"])),
    dict(id="sierramorena", nombre="Sierra Morena", tipo="barrio", zona="media",
         ancla=("paraderos", ["110A10", "111A10", "104A10"])),
    dict(id="arborizadora", nombre="Arborizadora Alta", tipo="barrio", zona="alta",
         ancla=("paraderos", ["193A11", "192A11", "604A11"])),
    dict(id="lucero", nombre="Lucero Alto", tipo="barrio", zona="alta", ancla=("fijo", 4.55788, -74.14009),
         fuente=FUENTE_OSM),
    dict(id="jerusalen", nombre="Jerusalén", tipo="barrio", zona="alta", ancla=("paraderos", ["163A11", "161A11"])),
    dict(id="paraiso", nombre="Paraíso Alto", tipo="barrio", zona="alta", ancla=("paraderos", ["124A11"])),
    # Rural
    dict(id="quiba", nombre="Quiba (rural)", tipo="vereda", zona="rural", ancla=("paraderos", ["435A11"])),
    dict(id="mochuelo", nombre="Mochuelo Bajo", tipo="vereda", zona="rural", ancla=("fijo", 4.50828, -74.14819),
         direccion="Vía Mochuelo Bajo", fuente=FUENTE_OSM),
    dict(id="pasquilla", nombre="Pasquilla (rural)", tipo="vereda", zona="rural", ancla=("fijo", 4.44462, -74.15597),
         direccion="Vía Mochuelo - Pasquilla, centro poblado", fuente=FUENTE_OSM),
    # Puntos de interés
    dict(id="hospital", nombre="Hospital Meissen", tipo="salud", zona="baja", ancla=("fijo", 4.55957, -74.13845),
         direccion="KR 18B, Meissen (paradero Av. Boyacá - KR 18B)", fuente=FUENTE_OSM),
    dict(id="sena", nombre="SENA Ciudad Bolívar", tipo="educacion", zona="alta", ancla=("fijo", 4.57196, -74.16358),
         direccion="KR 46B, La Pradera (convenio ISPA-SENA Jerusalén)", fuente=FUENTE_OSM),
    dict(id="udtecno", nombre="U. Distrital Sede Tecnológica", tipo="educacion", zona="baja",
         ancla=("fijo", 4.57926, -74.15794), direccion="Av. Villavicencio - Av. Jorge Gaitán Cortés", fuente=FUENTE_OSM),
    dict(id="plaza", nombre="Plaza de mercado Los Luceros", tipo="comercio", zona="alta",
         ancla=("fijo", 4.54934, -74.13966), direccion="CL 69B Sur, La Alameda (Lucero)", fuente=FUENTE_OSM),
    # Barrios altos y veredas que viven del transporte informal (centro del barrio en OpenStreetMap/Nominatim)
    dict(id="bellaflor", nombre="Bella Flor", tipo="barrio", zona="alta", ancla=("fijo", 4.54437, -74.16162),
         fuente=FUENTE_OSM),
    dict(id="caracoli", nombre="Caracolí", tipo="barrio", zona="alta", ancla=("fijo", 4.57307, -74.17121),
         fuente=FUENTE_OSM),
    dict(id="santodomingo", nombre="Santo Domingo", tipo="barrio", zona="alta", ancla=("fijo", 4.57951, -74.17842),
         fuente=FUENTE_OSM),
    dict(id="tesoro", nombre="El Tesoro (Arabia)", tipo="barrio", zona="alta", ancla=("fijo", 4.53898, -74.14628),
         fuente=FUENTE_OSM),
    dict(id="quibaalta", nombre="Quiba Alta (rural)", tipo="vereda", zona="rural", ancla=("fijo", 4.51446, -74.16445),
         fuente=FUENTE_OSM),
    dict(id="mochueloalto", nombre="Mochuelo Alto (rural)", tipo="vereda", zona="rural",
         ancla=("fijo", 4.48836, -74.14834), direccion="Vía Mochuelo - Pasquilla", fuente=FUENTE_OSM),
]

# --- Tramos formales derivados del orden oficial de paradas -------------------
# (de, a, modo, ruta, freqMin). Tiempo, trazado y "via" salen de la ruta oficial.
# Cada ruta aparece en un solo tramo: el motor fusiona tramos seguidos de la misma
# ruta sumando su tarifa, así que encadenarlos cobraría dos pasajes.
SITP = [
    ("tunal", "meissen", "sitp", "H602", 12),         # Av. Boyacá
    ("tunal", "hospital", "sitp", "H608", 12),
    ("tunal", "perdomo", "sitp", "H622", 12),         # Av. Villavicencio
    ("tunal", "candelaria", "sitp", "T25", 15),
    ("tunal", "paraiso", "sitp", "H610", 15),         # sube por Lucero / Vista Hermosa
    ("tunal", "mochuelo", "alimentador", "6-18", 20),
    ("meissen", "perdomo", "sitp", "C612", 15),
    ("meissen", "mochuelo", "sitp", "796A", 30),
    ("hospital", "plaza", "sitp", "H633", 12),
    ("perdomo", "sierramorena", "sitp", "T04", 15),
    ("perdomo", "sena", "sitp", "H600", 15),
    ("sierramorena", "arborizadora", "sitp", "A618", 15),
    ("candelaria", "arborizadora", "sitp", "H618", 15),
    ("candelaria", "juanpablo", "sitp", "H627", 15),   # complementa al cable
    ("hospital", "juanpablo", "sitp", "D627", 15),
    ("arborizadora", "jerusalen", "alimentador", "6-9", 10),
    ("manitas", "quiba", "sitp", "624", 30),
]
CABLE = [  # tiempos oficiales de operación (~13,5 min de Tunal a Mirador)
    ("tunal", "juanpablo", 5, TARIFA),
    ("juanpablo", "manitas", 4, 0),
    ("manitas", "mirador", 5, 0),
]
A_PIE = [  # conexiones cortas reales (distancia en línea recta x 1,3)
    ("meissen", "hospital"), ("hospital", "lucero"), ("estperdomo", "perdomo"),
    ("candelaria", "udtecno"), ("jerusalen", "sena"),
]
# Tramos con trazado propio (ya validados en Google Maps el 24/09/2026)
_GEOM_UD = [[4.5797, -74.1571], [4.57576, -74.15499], [4.574, -74.15363], [4.57294, -74.1524], [4.5678, -74.1449],
            [4.56761, -74.14507], [4.56744, -74.14499], [4.56619, -74.14388], [4.56317, -74.14197], [4.56265, -74.1414],
            [4.56188, -74.14015], [4.56173, -74.13914], [4.56032, -74.13934], [4.55927, -74.13924]]
_GEOM_L613 = _GEOM_UD + [[4.5527, -74.13703], [4.55254, -74.13683], [4.55265, -74.13669], [4.55283, -74.13668],
                         [4.5591, -74.13886], [4.56029, -74.139], [4.56035, -74.13861], [4.55989, -74.1384]]
_FUENTE_UD = "ArcGIS TransMilenio (trazado) · Google Maps (tiempos, 24/09/2026)"
TRAMOS_FIJOS = [
    dict(de="udtecno", a="hospital", modo="sitp", min=20, cop=TARIFA, freqMin=10, ruta="HG712", geom=_GEOM_UD, fuente=_FUENTE_UD),
    dict(de="udtecno", a="hospital", modo="sitp", min=22, cop=TARIFA, freqMin=20, ruta="HC612", geom=_GEOM_UD, fuente=_FUENTE_UD),
    dict(de="udtecno", a="hospital", modo="sitp", min=22, cop=TARIFA, freqMin=20, ruta="P44", geom=_GEOM_UD, fuente=_FUENTE_UD),
    dict(de="udtecno", a="hospital", modo="sitp", min=24, cop=TARIFA, freqMin=7, ruta="H318", geom=_GEOM_UD, fuente=_FUENTE_UD),
    dict(de="udtecno", a="hospital", modo="sitp", min=28, cop=TARIFA, freqMin=15, ruta="L613", geom=_GEOM_L613, fuente=_FUENTE_UD),
]
# Informal: no existe en ninguna fuente oficial (es el diferenciador). Tiempos revisados
# contra la distancia real entre los puntos.
INFORMAL = [
    dict(de="mirador", a="paraiso", modo="jeep", min=8, cop=1500, freqMin=20, ruta="Jeep Paraíso"),
    dict(de="manitas", a="lucero", modo="colectivo", min=10, cop=1800, freqMin=18, ruta="Colectivo Lucero"),
    dict(de="arborizadora", a="jerusalen", modo="colectivo", min=9, cop=1700, freqMin=25, ruta="Colectivo Jerusalén"),
    dict(de="lucero", a="paraiso", modo="jeep", min=12, cop=2000, freqMin=30, ruta="Jeep Alto"),
    dict(de="tunal", a="mochuelo", modo="veredal", min=35, cop=3000, freqMin=40, ruta="Veredal Mochuelo"),
    dict(de="mochuelo", a="quiba", modo="veredal", min=25, cop=2500, freqMin=60, ruta="Veredal Quiba"),
    dict(de="mochuelo", a="pasquilla", modo="veredal", min=35, cop=2500, freqMin=90, ruta="Veredal Pasquilla"),
    dict(de="manitas", a="quiba", modo="jeep", min=15, cop=3500, freqMin=60, ruta="Jeep Quiba"),
    # Barrios altos y veredas sin SITP: el tiempo sale del recorrido real por las calles (min=None)
    dict(de="mirador", a="bellaflor", modo="jeep", min=None, cop=2000, freqMin=15, ruta="Jeep Bella Flor"),
    dict(de="quiba", a="quibaalta", modo="jeep", min=None, cop=3000, freqMin=60, ruta="Jeep Quiba Alta"),
    dict(de="candelaria", a="caracoli", modo="colectivo", min=None, cop=2000, freqMin=15, ruta="Colectivo Caracolí"),
    dict(de="perdomo", a="santodomingo", modo="colectivo", min=None, cop=2000, freqMin=15,
         ruta="Colectivo Santo Domingo"),
    dict(de="plaza", a="tesoro", modo="colectivo", min=None, cop=2000, freqMin=15, ruta="Colectivo El Tesoro"),
    dict(de="tunal", a="lucero", modo="colectivo", min=None, cop=2000, freqMin=10, ruta="Colectivo Tunal - Lucero"),
    dict(de="mochuelo", a="mochueloalto", modo="veredal", min=None, cop=2500, freqMin=45, ruta="Veredal Mochuelo Alto"),
]
# Cámaras de fotodetección: referencia visual sobre avenidas reales (sin dataset oficial abierto).
CAMARAS = [
    dict(id="cam-villavicencio", nombre="Fotodetección Av. Villavicencio (Candelaria)",
         tramo={"de": "tunal", "a": "perdomo", "modo": "sitp"}, lat=4.5727, lng=-74.1522),
    dict(id="cam-tunal", nombre="Fotodetección Portal Tunal (Av. Boyacá)",
         tramo={"de": "tunal", "a": "meissen", "modo": "sitp"}, lat=4.5717, lng=-74.1395),
    dict(id="cam-boyaca", nombre="Fotodetección Av. Boyacá (Br. México)",
         tramo={"de": "hospital", "a": "plaza", "modo": "sitp"}, lat=4.5550, lng=-74.1374),
    dict(id="cam-paraiso", nombre="Fotodetección subida a Paraíso",
         tramo={"de": "mirador", "a": "paraiso", "modo": "jeep"}, lat=4.5496, lng=-74.1610),
]
ALIAS = {
    "el cable": "tunal", "transmicable": "tunal", "portal": "tunal", "portal tunal": "tunal", "tunal": "tunal",
    "paraiso": "paraiso", "el paraiso": "paraiso", "mirador": "mirador", "mirador del paraiso": "mirador",
    "sierra": "sierramorena", "sierra morena": "sierramorena",
    "arborizadora": "arborizadora", "la arborizadora": "arborizadora",
    "lucero": "lucero", "jerusalen": "jerusalen", "quiba": "quiba", "quiba baja": "quiba",
    "pasquilla": "pasquilla", "mochuelo": "mochuelo", "meissen": "meissen",
    "perdomo": "perdomo", "ismael perdomo": "perdomo", "estacion perdomo": "estperdomo",
    "candelaria": "candelaria", "la candelaria": "candelaria",
    "hospital": "hospital", "sena": "sena",
    "universidad": "udtecno", "u distrital": "udtecno", "universidad distrital": "udtecno",
    "tecnologica": "udtecno", "sede tecnologica": "udtecno",
    "plaza": "plaza", "mercado": "plaza", "los luceros": "plaza",
    "manitas": "manitas", "juan pablo": "juanpablo", "juan pablo ii": "juanpablo",
    "bella flor": "bellaflor", "caracoli": "caracoli", "santo domingo": "santodomingo",
    "el tesoro": "tesoro", "tesoro": "tesoro", "arabia": "tesoro", "tesorito": "tesoro",
    "quiba alta": "quibaalta", "mochuelo alto": "mochueloalto",
}

# --- Utilidades ----------------------------------------------------------------

_ARREGLOS = {"Boyac�": "Boyacá", "Gait�n": "Gaitán", "Bol�var": "Bolívar", " � ": " - "}


def limpiar(texto: str) -> str:
    for mal, bien in _ARREGLOS.items():
        texto = texto.replace(mal, bien)
    return texto.replace("�", "").strip()


def hav(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def consultar(servicio: str, cache: Path | None, **params) -> list[dict]:
    """Query paginado a un FeatureServer; devuelve [{**attributes, lat, lng}] o features GeoJSON."""
    nombre = re.sub(r"\W+", "_", servicio) + ".json"
    if cache and (cache / nombre).exists():
        return json.loads((cache / nombre).read_text(encoding="utf-8"))
    filas, offset = [], 0
    while True:
        q = dict(where="1=1", outFields="*", outSR=4326, f="json", resultOffset=offset,
                 resultRecordCount=2000, orderByFields="objectid", **params)
        url = f"{ARCGIS}/{servicio}/query?{urllib.parse.urlencode(q)}"
        with urllib.request.urlopen(url, timeout=120) as r:
            d = json.load(r)
        if "error" in d:
            raise RuntimeError(f"{servicio}: {d['error']}")
        for f in d.get("features", []):
            g = f.get("geometry") or {}
            fila = dict(f["attributes"])
            if "x" in g:
                fila.update(lat=g["y"], lng=g["x"])
            if "paths" in g:
                fila["paths"] = g["paths"]
            filas.append(fila)
        if not d.get("exceededTransferLimit"):
            break
        offset += 2000
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / nombre).write_text(json.dumps(filas, ensure_ascii=False), encoding="utf-8")
    return filas


def simplificar(puntos: list[list[float]], tol_m: float = 6) -> list[list[float]]:
    """Douglas-Peucker en metros: menos vértices, misma forma (data.js viaja al celular)."""
    if len(puntos) < 3:
        return puntos
    la0 = math.radians(puntos[0][0])
    xy = [(p[1] * 111320 * math.cos(la0), p[0] * 110540) for p in puntos]

    def dist(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx == dy == 0:
            return math.hypot(p[0] - a[0], p[1] - a[1])
        t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
        return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)

    guardar = [False] * len(puntos)
    guardar[0] = guardar[-1] = True
    pila = [(0, len(puntos) - 1)]
    while pila:
        i, j = pila.pop()
        k, dmax = i, 0.0
        for m in range(i + 1, j):
            d = dist(xy[m], xy[i], xy[j])
            if d > dmax:
                k, dmax = m, d
        if dmax > tol_m:
            guardar[k] = True
            pila += [(i, k), (k, j)]
    return [p for p, g in zip(puntos, guardar) if g]


def largo(geom) -> float:
    return sum(hav(a, b) for a, b in zip(geom, geom[1:]))


def osrm(puntos: list[list[float]], perfil: str, cache: Path | None) -> list[list[float]] | None:
    """Ruta por las calles que pasa por `puntos` ([lat, lng]); None si OSRM no responde."""
    coords = ";".join(f"{lng:.5f},{lat:.5f}" for lat, lng in puntos)
    url = f"{OSRM[perfil]}/route/v1/driving/{coords}?overview=full&geometries=geojson"
    nombre = f"osrm_{perfil}_{hashlib.sha1(coords.encode()).hexdigest()[:16]}.json"
    archivo = cache / nombre if cache else None
    if archivo and archivo.exists():
        d = json.loads(archivo.read_text(encoding="utf-8"))
    else:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MueveteCB-hackaton/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
        except Exception as e:  # sin red: se queda el trazado por paradas
            print(f"  OSRM no respondió ({e}); se deja el trazado por paradas")
            return None
        if archivo:
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text(json.dumps(d), encoding="utf-8")
    if d.get("code") != "Ok":
        return None
    return [[round(y, 5), round(x, 5)] for x, y in d["routes"][0]["geometry"]["coordinates"]]


def por_calles(t: dict, pos: dict, cache: Path | None) -> None:
    """Reemplaza la geom del tramo por su recorrido real por las calles (el cable va por el aire: no se toca).

    Pasa por las paradas oficiales (máx. 25). Si al forzar las paradas OSRM da vueltas raras
    (p. ej. retornos en avenidas de doble calzada), usa solo los extremos.
    """
    if t["modo"] == "cable":
        return
    base = t.get("geom") or [list(pos[t["de"]]), list(pos[t["a"]])]
    if len(base) > 25:
        paso = (len(base) - 1) / 24
        base = [base[round(i * paso)] for i in range(25)]
    perfil = "pie" if t["modo"] == "caminando" else "carro"
    candidatos = [g for g in (osrm(base, perfil, cache),
                              osrm([base[0], base[-1]], perfil, cache) if len(base) > 2 else None) if g]
    if not candidatos:
        return
    g = candidatos[0]
    if len(candidatos) > 1 and largo(g) > 1.4 * largo(candidatos[1]):
        g = candidatos[1]
    t["geom"] = simplificar(g)
    t["fuente"] = f"{t['fuente']}; {FUENTE_CALLES}"


def en_bbox() -> dict:
    return dict(geometry=BBOX_CB, geometryType="esriGeometryEnvelope", inSR=4326,
                spatialRel="esriSpatialRelIntersects")


# --- Construcción --------------------------------------------------------------

def construir(cache: Path | None) -> dict:
    cable = consultar("BRT/ConsultaEstacionesCable/FeatureServer/0", cache)
    trazados = consultar("BRT/consulta_trazados_cable/FeatureServer/0", cache)
    troncales = consultar("Troncal/consulta_estaciones_troncales/FeatureServer/0", cache, **en_bbox())
    paradas = consultar("Zonal/consulta_paraderos_rutas/FeatureServer/0", cache, **en_bbox())

    por_cenefa = {p["cenefa"]: p for p in paradas}
    rutas: dict[str, list[dict]] = {}
    for p in paradas:
        rutas.setdefault(p["ruta"], []).append(p)
    for lista in rutas.values():
        lista.sort(key=lambda p: (p["orden"][:3], int(re.sub(r"\D", "", p["orden"][3:]) or 0)))

    def parada_cercana(pt, lista):
        return min(lista, key=lambda p: hav(pt, (p["lat"], p["lng"])))

    # Lugares
    paraderos = []
    for l in LUGARES:
        tipo_ancla, *arg = l["ancla"]
        fuente, direccion = l.get("fuente"), l.get("direccion")
        if tipo_ancla == "cable":
            e = next(e for e in cable if e["nombre_estacion_cable"] == arg[0])
            lat, lng, fuente = e["lat"], e["lng"], FUENTE_CABLE
        elif tipo_ancla == "troncal":
            e = next(e for e in troncales if limpiar(e["nombre_estacion"]) == arg[0])
            lat, lng, fuente = e["latitud_estacion"], e["longitud_estacion"], FUENTE_TRONCAL
            direccion = direccion or limpiar(e["ubicacion_estacion"] or "")
        elif tipo_ancla == "paraderos":
            ps = [por_cenefa[c] for c in arg[0]]
            lat, lng = sum(p["lat"] for p in ps) / len(ps), sum(p["lng"] for p in ps) / len(ps)
            fuente = FUENTE_SITP + " (" + ", ".join(arg[0]) + ")"
            direccion = direccion or limpiar(ps[0]["direccion_bandera"])
        else:
            lat, lng = arg
        if not direccion:
            direccion = limpiar(parada_cercana((lat, lng), paradas)["direccion_bandera"])
        paraderos.append(dict(id=l["id"], nombre=l["nombre"], tipo=l["tipo"], zona=l["zona"],
                              lat=round(lat, 5), lng=round(lng, 5), direccion=direccion, fuente=fuente))
    pos = {p["id"]: (p["lat"], p["lng"]) for p in paraderos}
    _esquema(paraderos)

    tramos = []
    # Cable, con su trazado oficial
    ids_cable = {e["nombre_estacion_cable"]: l["id"] for l in LUGARES if l["ancla"][0] == "cable"
                 for e in cable if e["nombre_estacion_cable"] == l["ancla"][1]}
    ids_cable["TUNAL"] = "tunal"
    geom_cable = {}
    for t in trazados:
        de, a = ids_cable[t["origen_trazado_cable"]], ids_cable[t["destino_trazado_cable"]]
        geom_cable[(de, a)] = [[round(y, 5), round(x, 5)] for x, y in t["paths"][0]]
    for de, a, minutos, cop in CABLE:
        g = geom_cable.get((de, a)) or list(reversed(geom_cable[(a, de)]))
        tramos.append(dict(de=de, a=a, modo="cable", min=minutos, cop=cop, freqMin=1, ruta="Cable L1",
                           geom=g, fuente="ArcGIS TransMilenio · BRT/consulta_trazados_cable"))

    # SITP / alimentadores, desde el orden oficial de paradas
    for de, a, modo, ruta, freq in SITP:
        lista = rutas[ruta]
        ia = lista.index(parada_cercana(pos[de], lista))
        ib = lista.index(parada_cercana(pos[a], lista))
        paso = 1 if ib >= ia else -1
        seq = lista[ia: ib + paso: paso] if paso == 1 else lista[ia: (ib - 1 if ib else None): -1]
        metros = sum(hav((p["lat"], p["lng"]), (q["lat"], q["lng"])) for p, q in zip(seq, seq[1:]))
        for extremo, parada in ((de, seq[0]), (a, seq[-1])):
            d = hav(pos[extremo], (parada["lat"], parada["lng"]))
            if d > 500:
                raise ValueError(f"{ruta}: la parada más cercana a {extremo} está a {d:.0f} m")
        vel = VEL_ALIM_KMH if modo == "alimentador" else VEL_SITP_KMH
        geom = [list(pos[de])] + [[round(p["lat"], 5), round(p["lng"], 5)] for p in seq] + [list(pos[a])]
        tramos.append(dict(de=de, a=a, modo=modo, min=max(2, round(metros / 1000 / vel * 60)), cop=TARIFA,
                           freqMin=freq, ruta=ruta, geom=geom,
                           via=f"{limpiar(seq[0]['nombre'])} → {limpiar(seq[-1]['nombre'])}",
                           fuente=f"{FUENTE_SITP} (ruta {ruta}, {len(seq)} paradas, {metros / 1000:.1f} km); "
                                  "frecuencia estimada"))

    tramos += TRAMOS_FIJOS
    for de, a in A_PIE:
        m = hav(pos[de], pos[a]) * 1.3
        tramos.append(dict(de=de, a=a, modo="caminando", min=max(2, round(m / VEL_PIE_M_MIN)), cop=0, freqMin=0,
                           ruta="a pie", fuente=f"Distancia real {m:.0f} m"))
    tramos += [dict(t, fuente=FUENTE_COMUNIDAD) for t in INFORMAL]

    osrm_cache = cache / "osrm" if cache else None
    for t in tramos:
        por_calles(t, pos, osrm_cache)
        if t["min"] is None:  # informal nuevo: tiempo por la distancia real recorrida
            metros = largo(t.get("geom") or [pos[t["de"]], pos[t["a"]]]) * (1 if t.get("geom") else 1.3)
            t["min"] = max(3, round(metros / 1000 / VEL_INFORMAL_KMH[t["modo"]] * 60))

    ids = set(pos)
    for t in tramos:
        assert t["de"] in ids and t["a"] in ids, t
    for c in CAMARAS:
        assert any({t["de"], t["a"]} == {c["tramo"]["de"], c["tramo"]["a"]} and t["modo"] == c["tramo"]["modo"]
                   for t in tramos), c
    assert all(v in ids for v in ALIAS.values())

    return dict(modos=MODOS, paraderos=paraderos, tramos=tramos, camaras=CAMARAS, alias=ALIAS)


def _esquema(paraderos: list[dict]) -> None:
    """x,y del mapa offline (lienzo 0..100, norte arriba). Pasquilla queda al borde: está lejos."""
    urb = [p for p in paraderos if p["id"] != "pasquilla"]
    la0, la1 = min(p["lat"] for p in urb), max(p["lat"] for p in urb)
    lo0, lo1 = min(p["lng"] for p in urb), max(p["lng"] for p in urb)
    for p in paraderos:
        p["x"] = round(8 + (p["lng"] - lo0) / (lo1 - lo0) * 62)
        p["y"] = min(96, round(6 + (la1 - p["lat"]) / (la1 - la0) * 84))
    # separa puntos que quedarían encima (p. ej. Meissen y su hospital, a 100 m)
    for i, p in enumerate(paraderos):
        while any(abs(p["x"] - q["x"]) < 4 and abs(p["y"] - q["y"]) < 3 for q in paraderos[:i]):
            p["y"] += 3


# --- Salida ---------------------------------------------------------------------

def _js(v) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(", ", ": "))


def escribir_data_js(red: dict, destino: Path) -> None:
    modos = "\n".join(f"  {k}: {_js(v)}," for k, v in red["modos"].items())
    lugares = "\n".join(f"  {_js(p)}," for p in red["paraderos"])
    tramos = "\n".join(f"  {_js(t)}," for t in red["tramos"])
    camaras = "\n".join(f"  {_js(c)}," for c in red["camaras"])
    alias = "\n".join(f"  {_js(k)}: {_js(v)}," for k, v in red["alias"].items())
    destino.write_text(f"""/*
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
 * geom: trazado [lat, lng] por las calles (OSRM/OpenStreetMap), pasando por las paradas
 *       reales de la ruta. El cable va por el aire: usa su trazado oficial.
 */

const MODOS = {{
{modos}
}};

const PARADEROS = [
{lugares}
];

const TRAMOS = [
{tramos}
];

const CAMARAS = [
{camaras}
];

// Alias / apodos que la gente usa (para el buscador y el chat de IA)
const ALIAS = {{
{alias}
}};

// Exponer global (sin módulos, para máxima compatibilidad offline)
window.DB = {{ MODOS, PARADEROS, TRAMOS, CAMARAS, ALIAS }};
""", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache", type=Path, help="carpeta para guardar/reutiliza las respuestas de ArcGIS")
    args = ap.parse_args()
    red = construir(args.cache)
    NETWORK_JSON.write_text(json.dumps(red, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    escribir_data_js(red, DATA_JS)
    print(f"{len(red['paraderos'])} paraderos, {len(red['tramos'])} tramos -> {NETWORK_JSON.name}, {DATA_JS.name}")


if __name__ == "__main__":
    main()
