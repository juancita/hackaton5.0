"""Mapa de una ruta: trazado real por tramo, puntos A/B, transbordos y la ubicación del usuario.

La ruta viaja codificada en texto corto (`codificar`) para que el mapa se pueda pedir por URL
sin guardar estado: "<origen_id>:<i>.<j>.<k>", donde cada número es el índice de un tramo de
la red en el orden en que se recorre.
"""

import math
from urllib.parse import urlencode

from pydantic import BaseModel

from app.domain.errors import InvalidInput
from app.domain.models import MapaRuta, Network, RouteOption, Segment

Punto = tuple[float, float]  # (lat, lng)

MAX_TRAMOS = 40
MAX_WAYPOINTS = 8  # Google Maps admite hasta 9 paradas intermedias en un enlace


class LineaMapa(BaseModel):
    color: str
    formal: bool
    puntos: list[Punto]


class MarcaMapa(BaseModel):
    punto: Punto
    nombre: str


class RouteMap(BaseModel):
    lineas: list[LineaMapa]
    origen: MarcaMapa
    destino: MarcaMapa
    transbordos: list[Punto] = []
    ubicacion: Punto | None = None
    modos: list[tuple[str, str]] = []  # (nombre, color) de los modos usados, para la leyenda


def _paso(t: Segment, desde: str) -> str:
    return t.a if t.de == desde else t.de


def codificar(op: RouteOption, net: Network) -> str:
    indices = []
    for leg in op.tramos:
        paradas = leg.paradas or [leg.desde, leg.hasta]
        for de, a in zip(paradas, paradas[1:]):
            candidatos = [
                i for i, t in enumerate(net.tramos) if {t.de, t.a} == {de, a} and t.modo == leg.modo
            ]
            i = next((i for i in candidatos if net.tramos[i].ruta == leg.ruta), candidatos[0] if candidatos else None)
            if i is None:
                raise InvalidInput(f"No hay tramo {leg.modo} entre {de} y {a}")
            indices.append(str(i))
    return f"{op.origen}:{'.'.join(indices)}"


def decodificar(codigo: str, net: Network) -> list[tuple[Segment, str, str]]:
    """[(tramo, desde, hasta)] en el orden del recorrido. InvalidInput si el código no es una ruta válida."""
    origen, _, resto = codigo.partition(":")
    if not net.lugar(origen) or not resto:
        raise InvalidInput("Ruta de mapa inválida")
    partes = resto.split(".")
    if len(partes) > MAX_TRAMOS or not all(p.isdigit() for p in partes):
        raise InvalidInput("Ruta de mapa inválida")
    pasos, actual = [], origen
    for p in partes:
        i = int(p)
        if i >= len(net.tramos) or actual not in (net.tramos[i].de, net.tramos[i].a):
            raise InvalidInput("Ruta de mapa inválida")
        t = net.tramos[i]
        siguiente = _paso(t, actual)
        pasos.append((t, actual, siguiente))
        actual = siguiente
    return pasos


def construir(codigo: str, net: Network, ubicacion: Punto | None = None) -> RouteMap:
    pasos = decodificar(codigo, net)
    coord = lambda pid: (net.lugar(pid).lat, net.lugar(pid).lng)  # noqa: E731
    lineas, transbordos, modos = [], [], {}
    for k, (t, de, a) in enumerate(pasos):
        m = net.modos[t.modo]
        geom = list(t.geom) if t.geom else [coord(t.de), coord(t.a)]
        if t.de != de:
            geom.reverse()
        # Si el trazado real no arranca o no termina en el paradero, se une con una línea recta
        lineas.append(LineaMapa(color=m.color, formal=m.formal, puntos=[coord(de), *geom, coord(a)]))
        modos.setdefault(m.nombre, m.color)
        if k and (t.modo, t.ruta) != (pasos[k - 1][0].modo, pasos[k - 1][0].ruta):
            transbordos.append(coord(de))
    inicio, fin = net.lugar(pasos[0][1]), net.lugar(pasos[-1][2])
    return RouteMap(
        lineas=lineas,
        origen=MarcaMapa(punto=(inicio.lat, inicio.lng), nombre=inicio.nombre),
        destino=MarcaMapa(punto=(fin.lat, fin.lng), nombre=fin.nombre),
        transbordos=transbordos,
        ubicacion=ubicacion,
        modos=list(modos.items()),
    )


def distancia_m(p: Punto, q: Punto) -> float:
    """Haversine en metros."""
    la1, lo1, la2, lo2 = map(math.radians, (*p, *q))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def _fmt(p: Punto) -> str:
    return f"{p[0]:.6f},{p[1]:.6f}"


def google_maps(codigo: str, net: Network, ubicacion: Punto | None = None) -> str:
    """Enlace de Google Maps que pasa por los puntos de transbordo. Si el usuario compartió su
    ubicación y está cerca, el recorrido arranca donde está y pasa por el paradero de salida."""
    mapa = construir(codigo, net)
    paradas = list(mapa.transbordos)
    origen = mapa.origen.punto
    if ubicacion and 30 < distancia_m(ubicacion, origen) < 5_000:
        paradas.insert(0, origen)
        origen = ubicacion
    params = {"api": "1", "origin": _fmt(origen), "destination": _fmt(mapa.destino.punto)}
    if paradas:
        params["waypoints"] = "|".join(_fmt(p) for p in paradas[:MAX_WAYPOINTS])
    return "https://www.google.com/maps/dir/?" + urlencode(params)


def mapa_de(op: RouteOption, net: Network, ubicacion: Punto | None = None) -> MapaRuta:
    codigo = codificar(op, net)
    return MapaRuta(ruta=codigo, ubicacion=ubicacion, google_maps=google_maps(codigo, net, ubicacion))
