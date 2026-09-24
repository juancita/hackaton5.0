"""Motor de rutas multimodal: port fiel de web/js/engine.js (spec 03)."""

import heapq
from dataclasses import dataclass, replace
from itertools import count

from app.domain.models import Leg, Network, Penalty, Prioridad, RouteOption
from app.domain.text import redondear

ETIQUETAS: dict[Prioridad, str] = {
    "rapido": "La más rápida",
    "barato": "La más económica",
    "transbordos": "Menos transbordos",
}

Penalties = dict[str, Penalty]


def clave_tramo(de: str, a: str, modo: str) -> str:
    return f"{de}|{a}|{modo}"


@dataclass(frozen=True)
class _Arista:
    de: str
    a: str
    modo: str
    ruta: str
    min: float
    cop: float
    espera: float
    motivo: str | None


class RoutingService:
    def __init__(self, network: Network):
        self._net = network

    def _grafo(self, pen: Penalties) -> dict[str, list[_Arista]]:
        adj: dict[str, list[_Arista]] = {p.id: [] for p in self._net.paraderos}
        for t in self._net.tramos:
            p = pen.get(clave_tramo(t.de, t.a, t.modo)) or pen.get(clave_tramo(t.a, t.de, t.modo))
            if p and p.bloqueado:
                continue  # tramo caído por reporte ciudadano
            factor = p.factor if p else 1
            espera = t.freqMin / 2 if t.freqMin else 0  # espera promedio = mitad de la frecuencia
            base = _Arista(t.de, t.a, t.modo, t.ruta, t.min * factor, t.cop, espera, p.motivo if p else None)
            adj[t.de].append(base)
            adj[t.a].append(replace(base, de=t.a, a=t.de))
        return adj

    @staticmethod
    def _costo(ar: _Arista, prioridad: Prioridad) -> float:
        tiempo = ar.min + ar.espera
        if prioridad == "barato":
            return ar.cop + tiempo * 5
        if prioridad == "transbordos":
            return tiempo + 100
        return tiempo

    def mejor_ruta(
        self, origen: str, destino: str, prioridad: Prioridad = "rapido", pen: Penalties | None = None
    ) -> RouteOption | None:
        if origen == destino:
            return None
        adj = self._grafo(pen or {})
        dist = {pid: float("inf") for pid in adj}
        prev: dict[str, _Arista] = {}
        dist[origen] = 0
        # (costo, orden de inserción, nodo): el desempate por orden replica el sort estable de JS
        seq = count()
        pq = [(0.0, next(seq), origen)]
        while pq:
            d, _, u = heapq.heappop(pq)
            if u == destino:
                break
            if d > dist[u]:
                continue
            for ar in adj[u]:
                nd = d + self._costo(ar, prioridad)
                if nd < dist[ar.a]:
                    dist[ar.a] = nd
                    prev[ar.a] = ar
                    heapq.heappush(pq, (nd, next(seq), ar.a))

        if dist[destino] == float("inf"):
            return None
        pasos: list[_Arista] = []
        cur = destino
        while cur != origen:
            ar = prev[cur]
            pasos.insert(0, ar)
            cur = ar.de
        return self._resumir(pasos, origen, destino)

    def _resumir(self, pasos: list[_Arista], origen: str, destino: str) -> RouteOption:
        tramos: list[Leg] = []
        for ar in pasos:
            ultimo = tramos[-1] if tramos else None
            if ultimo and ultimo.ruta == ar.ruta and ultimo.modo == ar.modo:
                ultimo.hasta = ar.a
                ultimo.min += ar.min
                ultimo.cop += ar.cop
                ultimo.paradas.append(ar.a)
            else:
                tramos.append(Leg(
                    modo=ar.modo, ruta=ar.ruta, desde=ar.de, hasta=ar.a,
                    min=ar.min + ar.espera, cop=ar.cop, espera=ar.espera,
                    motivo=ar.motivo, paradas=[ar.de, ar.a],
                ))
        modos = self._net.modos
        return RouteOption(
            origen=origen,
            destino=destino,
            tramos=tramos,
            totalMin=redondear(sum(t.min for t in tramos)),
            totalCop=sum(t.cop for t in tramos),
            transbordos=max(0, len(tramos) - 1),
            usaInformal=any(not modos[t.modo].formal and t.modo != "caminando" for t in tramos),
            alertas=[t.motivo for t in tramos if t.motivo],
        )

    def opciones(
        self, origen: str, destino: str, pen: Penalties | None = None, preferida: Prioridad | None = None
    ) -> list[RouteOption]:
        """Rápida, económica y con menos transbordos, sin repetir la misma secuencia de rutas.

        Si dos prioridades dan la misma ruta, se queda con la etiqueta de `preferida`
        (la que pidió el usuario); el orden de salida no cambia.
        """
        vistos: set[str] = set()
        elegidas: dict[str, RouteOption] = {}
        for prio in sorted(ETIQUETAS, key=lambda p: p != preferida):
            r = self.mejor_ruta(origen, destino, prio, pen)
            if not r:
                continue
            firma = ">".join(t.ruta for t in r.tramos)
            if firma in vistos:
                continue
            vistos.add(firma)
            elegidas[prio] = r.model_copy(update={"etiqueta": ETIQUETAS[prio], "prioridad": prio})
        return [elegidas[p] for p in ETIQUETAS if p in elegidas]
