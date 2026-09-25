"""Módulo de conductores informales, cupos, tracking y lugares guardados.

Automatiza la logística que hoy los jeeperos/colectiveros hacen a mano y de boca en boca:
- El conductor anuncia a qué hora sale, por qué ruta y con cuántos cupos.
- El pasajero aparta un cupo o avisa que va a salir; el conductor ve cuántos lo esperan.
- El conductor avisa "ya salí" y comparte ubicación; si no quedan cupos, se marca "lleno".
- Se guarda el historial de viajes → se infiere la TENDENCIA de horarios de cada conductor,
  que alimenta el modo OFFLINE (horarios típicos) y el asistente de IA.

Identidad: todo se ata al reporter_id (derivado del teléfono), así el mismo número es la
misma persona en la app y en WhatsApp. No se guardan datos personales en claro.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel

from app.domain.errors import InvalidInput
from app.domain.models import Network
from app.domain.reports import utcnow

ModoUso = Literal["pasajero", "conductor"]
EstadoViaje = Literal["programado", "en_ruta", "finalizado"]


# --- Modelos -----------------------------------------------------------------

class DriverProfile(BaseModel):
    reporter_id: str
    ruta: str = ""                 # ej. "Jeep Paraíso"
    barrio_base: str | None = None  # place_id de referencia
    placa: str | None = None
    activo: bool = True
    creado_en: datetime | None = None


class Trip(BaseModel):
    id: str
    driver_id: str
    driver_nombre: str = ""
    ruta: str
    origen_id: str
    destino_id: str
    hora: str                      # "HH:MM" (hora local de salida programada)
    cupos_total: int
    cupos_libres: int
    estado: EstadoViaje = "programado"
    lleno: bool = False
    lat: float | None = None
    lng: float | None = None
    salio_en: datetime | None = None
    creado_en: datetime
    desvio: str | None = None      # aviso del conductor: "voy por X porque la vía está cerrada"
    paradas: list[str] = []        # recorrido [origen, ...intermedias, destino] (se puede bajar a mitad)
    corta_en: str | None = None    # el conductor avisa que el viaje llega solo hasta esta parada
    esperando: int = 0             # pasajeros que apartaron cupo


class SeatRequest(BaseModel):
    id: str
    trip_id: str
    passenger_id: str
    passenger_nombre: str = ""
    baja_en: str | None = None     # parada donde se baja (None = destino final)
    estado: Literal["reservado", "cancelado"] = "reservado"
    creado_en: datetime


class SavedPlace(BaseModel):
    id: str
    reporter_id: str
    etiqueta: str                  # "casa" | "paradero" | libre
    nombre: str
    lat: float
    lng: float
    place_id: str | None = None
    creado_en: datetime


class RouteEvent(BaseModel):
    """Tracking anónimo: qué rutas consulta la gente (dato valioso, sin identidad en claro)."""
    id: int | None = None
    reporter_id: str
    origen_id: str
    destino_id: str
    canal: str
    creado_en: datetime


# --- Puerto de repositorio ---------------------------------------------------

class DriverRepository(Protocol):
    def get_profile(self, reporter_id: str) -> DriverProfile | None: ...
    def save_profile(self, p: DriverProfile) -> DriverProfile: ...
    def create_trip(self, t: Trip) -> Trip: ...
    def get_trip(self, trip_id: str) -> Trip | None: ...
    def save_trip(self, t: Trip) -> Trip: ...
    def list_trips(self, estados: list[str], barrio_id: str | None = None, limit: int = 50) -> list[Trip]: ...
    def driver_trips(self, driver_id: str, limit: int = 200) -> list[Trip]: ...
    def add_seat(self, sr: SeatRequest) -> SeatRequest: ...
    def seats_for_trip(self, trip_id: str) -> list[SeatRequest]: ...
    def save_place(self, sp: SavedPlace) -> SavedPlace: ...
    def list_places(self, reporter_id: str) -> list[SavedPlace]: ...
    def add_route_event(self, ev: RouteEvent) -> None: ...
    def route_stats(self, limit: int = 20) -> list[tuple[str, str, int]]: ...
    def link_identity(self, canal_key: str, reporter_id: str, now: datetime) -> None: ...
    def get_link(self, canal_key: str) -> str | None: ...


# --- Servicio ----------------------------------------------------------------

class DriverService:
    def __init__(self, network: Network, repo: DriverRepository, clock=utcnow):
        self._net = network
        self._repo = repo
        self._now = clock

    @property
    def network(self) -> Network:
        return self._net

    def pasajeros(self, trip_id: str) -> list[SeatRequest]:
        """Cupos apartados (vigentes) de un viaje."""
        return [s for s in self._repo.seats_for_trip(trip_id) if s.estado == "reservado"]

    # -- Perfil de conductor --
    def perfil(self, reporter_id: str) -> DriverProfile | None:
        return self._repo.get_profile(reporter_id)

    def registrar_conductor(self, reporter_id: str, ruta: str, barrio_base: str | None = None,
                            placa: str | None = None) -> DriverProfile:
        p = self._repo.get_profile(reporter_id) or DriverProfile(reporter_id=reporter_id, creado_en=self._now())
        p.ruta = (ruta or p.ruta or "").strip()
        p.barrio_base = barrio_base or p.barrio_base
        p.placa = placa or p.placa
        p.activo = True
        return self._repo.save_profile(p)

    # -- Anunciar / gestionar viajes --
    def recorrido(self, origen_id: str, destino_id: str, via: list[str] | None = None) -> list[str]:
        """Paradas del viaje. Con vías dadas: [origen, *vías, destino]. Si no, busca en la red una cadena
        de tramos informales de la MISMA ruta que una origen y destino (p. ej. El Ensueño → Sierra Morena
        → Potosí) para que el pasajero se pueda bajar a mitad del trayecto."""
        if via:
            return [origen_id, *[v for v in via if v not in (origen_id, destino_id)], destino_id]
        informales = [t for t in self._net.tramos if not self._net.modos[t.modo].formal]
        for ruta in {t.ruta for t in informales}:
            vecinos: dict[str, list[str]] = {}
            for t in informales:
                if t.ruta == ruta:
                    vecinos.setdefault(t.de, []).append(t.a)
                    vecinos.setdefault(t.a, []).append(t.de)
            if origen_id not in vecinos or destino_id not in vecinos:
                continue
            camino, pila = None, [(origen_id, [origen_id])]
            while pila:
                nodo, hecho = pila.pop()
                if nodo == destino_id:
                    camino = hecho
                    break
                pila += [(v, hecho + [v]) for v in vecinos[nodo] if v not in hecho]
            if camino:
                return camino
        return [origen_id, destino_id]

    def anunciar(self, driver_id: str, driver_nombre: str, origen_id: str, destino_id: str,
                 hora: str, cupos: int, ruta: str | None = None, via: list[str] | None = None) -> Trip:
        if not self._net.lugar(origen_id) or not self._net.lugar(destino_id):
            raise InvalidInput("Origen o destino no existe en la red")
        if cupos < 1 or cupos > 30:
            raise InvalidInput("Los cupos deben estar entre 1 y 30")
        perfil = self._repo.get_profile(driver_id)
        ruta_final = (ruta or (perfil.ruta if perfil else "") or "Ruta informal").strip()
        t = Trip(
            id=str(uuid.uuid4()), driver_id=driver_id, driver_nombre=driver_nombre, ruta=ruta_final,
            origen_id=origen_id, destino_id=destino_id, hora=hora, cupos_total=cupos, cupos_libres=cupos,
            paradas=self.recorrido(origen_id, destino_id, via), creado_en=self._now(),
        )
        return self._repo.create_trip(t)

    def proximos(self, barrio_id: str | None = None, limit: int = 50) -> list[Trip]:
        viajes = self._repo.list_trips(["programado", "en_ruta"], barrio_id, limit)
        for t in viajes:
            t.esperando = sum(1 for s in self._repo.seats_for_trip(t.id) if s.estado == "reservado")
        return sorted(viajes, key=lambda t: t.hora)

    def _con_esperando(self, t: Trip) -> Trip:
        t.esperando = sum(1 for s in self._repo.seats_for_trip(t.id) if s.estado == "reservado")
        return t

    def _trip_de(self, trip_id: str) -> Trip:
        t = self._repo.get_trip(trip_id)
        if not t:
            raise InvalidInput("Ese viaje no existe o ya terminó")
        return t

    def reservar(self, trip_id: str, passenger_id: str, passenger_nombre: str = "",
                 baja_en: str | None = None) -> Trip:
        t = self._trip_de(trip_id)
        if baja_en and t.paradas and (baja_en not in t.paradas or baja_en == t.paradas[0]):
            raise InvalidInput("Esa parada no está en el recorrido de este viaje")
        if t.estado == "finalizado":
            raise InvalidInput("Ese viaje ya finalizó")
        seats = self._repo.seats_for_trip(trip_id)
        if any(s.passenger_id == passenger_id and s.estado == "reservado" for s in seats):
            t.esperando = sum(1 for s in seats if s.estado == "reservado")
            return t  # ya tenía cupo, no duplica
        if t.cupos_libres <= 0:
            raise InvalidInput("Ese viaje ya está lleno. Mira otros horarios.")
        self._repo.add_seat(SeatRequest(
            id=str(uuid.uuid4()), trip_id=trip_id, passenger_id=passenger_id,
            passenger_nombre=passenger_nombre, baja_en=baja_en if baja_en != t.destino_id else None,
            creado_en=self._now(),
        ))
        t.cupos_libres -= 1
        if t.cupos_libres == 0:
            t.lleno = True
        t.esperando = sum(1 for s in seats if s.estado == "reservado") + 1
        return self._repo.save_trip(t)

    def salir(self, trip_id: str, driver_id: str, lat: float | None = None, lng: float | None = None) -> Trip:
        t = self._trip_de(trip_id)
        if t.driver_id != driver_id:
            raise InvalidInput("Solo el conductor del viaje puede marcar la salida")
        t.estado = "en_ruta"
        t.salio_en = self._now()
        if lat is not None and lng is not None:
            t.lat, t.lng = lat, lng
        if t.cupos_libres == 0:
            t.lleno = True
        return self._con_esperando(self._repo.save_trip(t))

    def marcar_lleno(self, trip_id: str, driver_id: str) -> Trip:
        t = self._trip_de(trip_id)
        if t.driver_id != driver_id:
            raise InvalidInput("Solo el conductor puede marcar lleno")
        t.lleno = True
        t.cupos_libres = 0
        return self._con_esperando(self._repo.save_trip(t))

    def finalizar(self, trip_id: str, driver_id: str) -> Trip:
        t = self._trip_de(trip_id)
        if t.driver_id != driver_id:
            raise InvalidInput("Solo el conductor puede finalizar el viaje")
        t.estado = "finalizado"
        return self._con_esperando(self._repo.save_trip(t))

    def desvio(self, trip_id: str, driver_id: str, nota: str) -> Trip:
        """El conductor avisa que toma otra vía (protesta, cierre, derrumbe): los pasajeros lo ven."""
        t = self._trip_de(trip_id)
        if t.driver_id != driver_id:
            raise InvalidInput("Solo el conductor puede avisar un desvío")
        t.desvio = (nota or "").strip()[:200] or "Desvío por novedad en la vía"
        return self._con_esperando(self._repo.save_trip(t))

    def cortar(self, trip_id: str, driver_id: str, parada_id: str) -> tuple[Trip, int]:
        """El conductor avisa que el viaje llega solo hasta una parada intermedia (lo que pasa a menudo:
        "hasta aquí llego"). Devuelve el viaje y cuántos pasajeros iban más allá y deben buscar otra opción."""
        t = self._trip_de(trip_id)
        if t.driver_id != driver_id:
            raise InvalidInput("Solo el conductor puede cortar el viaje")
        paradas = t.paradas or [t.origen_id, t.destino_id]
        if parada_id not in paradas[1:-1]:
            raise InvalidInput("Solo se puede cortar en una parada intermedia del recorrido")
        t.corta_en = parada_id
        corte = paradas.index(parada_id)
        afectados = sum(
            1 for sr in self._repo.seats_for_trip(t.id)
            if sr.estado == "reservado" and (sr.baja_en is None or paradas.index(sr.baja_en) > corte)
        )
        return self._con_esperando(self._repo.save_trip(t)), afectados

    def mis_viajes(self, driver_id: str, limit: int = 50) -> list[Trip]:
        return [self._con_esperando(t) for t in self._repo.driver_trips(driver_id, limit)]

    def viaje_activo(self, driver_id: str) -> Trip | None:
        """El viaje más reciente del conductor que no ha terminado (para comandos por chat)."""
        return next((t for t in self._repo.driver_trips(driver_id, 20) if t.estado != "finalizado"), None)

    # -- Vínculo de identidad (Telegram ↔ celular) --
    def vincular(self, canal_key: str, reporter_id: str) -> None:
        self._repo.link_identity(canal_key, reporter_id, self._now())

    def vinculo(self, canal_key: str) -> str | None:
        return self._repo.get_link(canal_key)

    # -- Demanda: cuántos pasajeros esperan salir de un barrio a cierta hora --
    def demanda(self, barrio_id: str, hora: str | None = None) -> dict:
        viajes = self._repo.list_trips(["programado", "en_ruta"], barrio_id, 100)
        total = 0
        detalle = []
        for t in viajes:
            n = sum(1 for s in self._repo.seats_for_trip(t.id) if s.estado == "reservado")
            if hora and t.hora != hora:
                continue
            total += n
            detalle.append({"trip_id": t.id, "hora": t.hora, "ruta": t.ruta, "esperando": n})
        return {"barrio_id": barrio_id, "hora": hora, "total_esperando": total, "viajes": detalle}

    # -- Tendencia de horarios (memoria + IA/heurística) --
    def tendencia(self, driver_id: str) -> dict:
        """Infiere el patrón de salidas de un conductor a partir de su historial."""
        trips = self._repo.driver_trips(driver_id, 300)
        if not trips:
            return {"total": 0, "horas_frecuentes": [], "viajes_por_dia": 0, "texto": "Aún no hay historial suficiente."}
        horas = Counter(t.hora for t in trips)
        top = [h for h, _ in horas.most_common(4)]
        dias = {t.creado_en.date() for t in trips}
        por_dia = round(len(trips) / max(1, len(dias)), 1)
        rutas = Counter(t.ruta for t in trips).most_common(1)
        ruta = rutas[0][0] if rutas else ""
        texto = (f"Este conductor ({ruta}) suele salir alrededor de {', '.join(top)} "
                 f"y hace ~{por_dia} viajes al día.")
        return {"total": len(trips), "horas_frecuentes": top, "viajes_por_dia": por_dia, "ruta": ruta, "texto": texto}

    def horarios_tipicos(self) -> dict[str, list[str]]:
        """Horarios típicos por ruta (para el modo OFFLINE): agrega historial + viajes programados."""
        por_ruta: dict[str, Counter] = {}
        for t in self._repo.list_trips(["programado", "en_ruta", "finalizado"], None, 500):
            por_ruta.setdefault(t.ruta, Counter())[t.hora] += 1
        return {ruta: [h for h, _ in c.most_common(6)] for ruta, c in por_ruta.items()}

    # -- Lugares guardados (casa / paradero) --
    def guardar_lugar(self, reporter_id: str, etiqueta: str, nombre: str, lat: float, lng: float,
                      place_id: str | None = None) -> SavedPlace:
        sp = SavedPlace(id=str(uuid.uuid4()), reporter_id=reporter_id, etiqueta=etiqueta[:24],
                        nombre=nombre[:80], lat=lat, lng=lng, place_id=place_id, creado_en=self._now())
        return self._repo.save_place(sp)

    def lugares(self, reporter_id: str) -> list[SavedPlace]:
        return self._repo.list_places(reporter_id)

    # -- Tracking anónimo de rutas consultadas (dato de negocio) --
    def registrar_consulta(self, reporter_id: str, origen_id: str, destino_id: str, canal: str) -> None:
        self._repo.add_route_event(RouteEvent(
            reporter_id=reporter_id, origen_id=origen_id, destino_id=destino_id, canal=canal, creado_en=self._now(),
        ))

    def rutas_mas_pedidas(self, limit: int = 20) -> list[dict]:
        return [{"origen_id": o, "destino_id": d, "consultas": n} for o, d, n in self._repo.route_stats(limit)]
