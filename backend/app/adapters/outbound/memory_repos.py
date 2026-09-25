"""Implementaciones en memoria. Conversaciones en producción; repos de feedback solo para pruebas o demo sin BD."""

from collections import Counter
from datetime import datetime

from app.domain.analytics import ReporteResumen
from app.domain.drivers import DriverProfile, RouteEvent, SavedPlace, SeatRequest, Trip
from app.domain.models import Conversation, Incident, IncidentState, Reporter, Role


class MemoryConversationStore:
    def __init__(self):
        self._data: dict[str, Conversation] = {}

    def get(self, key: str) -> Conversation | None:
        conv = self._data.get(key)
        return conv.model_copy(deep=True) if conv else None

    def save(self, conv: Conversation) -> None:
        self._data[conv.key] = conv.model_copy(deep=True)


class MemoryIncidentRepository:
    def __init__(self):
        self._data: dict[str, Incident] = {}
        self._seq = 0

    def get(self, incident_id: str) -> Incident | None:
        inc = self._data.get(incident_id)
        return inc.model_copy(deep=True) if inc else None

    def save(self, incident: Incident) -> Incident:
        for entry in [*incident.reports, *incident.votes]:
            if entry.id is None:
                self._seq += 1
                entry.id = self._seq
        self._data[incident.id] = incident.model_copy(deep=True)
        return incident.model_copy(deep=True)

    def find_open(self, de_id: str, a_id: str, tipo: str, now: datetime) -> Incident | None:
        for inc in self._data.values():
            if (
                {inc.de_id, inc.a_id} == {de_id, a_id}
                and inc.tipo == tipo
                and inc.estado in (IncidentState.activo, IncidentState.verificado)
                and inc.expira_en > now
            ):
                return inc.model_copy(deep=True)
        return None

    def list_current(self, now: datetime) -> list[Incident]:
        vigentes = [
            i for i in self._data.values()
            if i.expira_en > now and i.estado in (IncidentState.activo, IncidentState.verificado)
        ]
        return [i.model_copy(deep=True) for i in sorted(vigentes, key=lambda i: i.creado_en, reverse=True)]

    def list_recent(self, limit: int, since: datetime | None = None, before: datetime | None = None) -> list[Incident]:
        recientes = [
            i for i in self._data.values()
            if i.estado != IncidentState.rechazado
            and (since is None or i.creado_en >= since)
            and (before is None or i.creado_en < before)
        ]
        return [i.model_copy(deep=True) for i in sorted(recientes, key=lambda i: i.creado_en, reverse=True)[:limit]]

    def ratings(self, reporter_ids: list[str]) -> dict[str, tuple[int, int]]:
        out: dict[str, tuple[int, int]] = {}
        for rid in reporter_ids:
            votos = [
                v.valor for i in self._data.values() if any(r.reporter_id == rid for r in i.reports)
                for v in i.votes if v.reporter_id != rid
            ]
            if votos:
                out[rid] = (votos.count("confirma"), votos.count("niega"))
        return out

    def list_expired_unresolved(self, now: datetime) -> list[Incident]:
        return [i.model_copy(deep=True) for i in self._data.values() if i.expira_en <= now and not i.resuelto]

    def count_recent_reports(self, reporter_id: str, de_id: str, a_id: str, tipo: str, since: datetime) -> int:
        return sum(
            1
            for i in self._data.values()
            if {i.de_id, i.a_id} == {de_id, a_id} and i.tipo == tipo
            for r in i.reports
            if r.reporter_id == reporter_id and r.creado_en >= since
        )

    def delete_all(self) -> int:
        n = len(self._data)
        self._data.clear()
        return n


class MemoryReporterRepository:
    def __init__(self):
        self._data: dict[str, Reporter] = {}

    def get(self, reporter_id: str) -> Reporter | None:
        r = self._data.get(reporter_id)
        return r.model_copy() if r else None

    def get_or_create(self, reporter_id: str, canal: str, rol: Role, now: datetime) -> Reporter:
        r = self._data.get(reporter_id)
        if r is None:
            r = Reporter(id=reporter_id, canal=canal, rol=rol, creado_en=now)
            self._data[reporter_id] = r
        r.ultimo_en = now
        return r.model_copy()

    def add_outcome(self, reporter_ids: list[str], aciertos: int = 0, fallos: int = 0) -> None:
        for rid in reporter_ids:
            if r := self._data.get(rid):
                r.aciertos += aciertos
                r.fallos += fallos

    def set_perfil(self, reporter_id: str, nombre: str | None, modo: str | None) -> Reporter:
        r = self._data.get(reporter_id)
        if r is None:
            r = Reporter(id=reporter_id, canal="web")
            self._data[reporter_id] = r
        if nombre is not None:
            r.nombre = nombre
        if modo is not None:
            r.modo = modo
        return r.model_copy()


class MemoryDriverRepository:
    """Conductores, viajes, cupos, lugares y tracking en memoria (demo sin BD)."""

    def __init__(self):
        self._profiles: dict[str, DriverProfile] = {}
        self._trips: dict[str, Trip] = {}
        self._seats: list[SeatRequest] = []
        self._places: list[SavedPlace] = []
        self._events: list[RouteEvent] = []
        self._links: dict[str, str] = {}
        self._seq = 0

    def get_profile(self, reporter_id: str) -> DriverProfile | None:
        p = self._profiles.get(reporter_id)
        return p.model_copy() if p else None

    def save_profile(self, p: DriverProfile) -> DriverProfile:
        self._profiles[p.reporter_id] = p.model_copy()
        return p.model_copy()

    def create_trip(self, t: Trip) -> Trip:
        self._trips[t.id] = t.model_copy()
        return t.model_copy()

    def get_trip(self, trip_id: str) -> Trip | None:
        t = self._trips.get(trip_id)
        return t.model_copy() if t else None

    def save_trip(self, t: Trip) -> Trip:
        self._trips[t.id] = t.model_copy()
        return t.model_copy()

    def list_trips(self, estados: list[str], barrio_id: str | None = None, limit: int = 50) -> list[Trip]:
        out = [
            t for t in self._trips.values()
            if t.estado in estados and (barrio_id is None or barrio_id in (t.origen_id, t.destino_id))
        ]
        out.sort(key=lambda t: t.creado_en, reverse=True)
        return [t.model_copy() for t in out[:limit]]

    def driver_trips(self, driver_id: str, limit: int = 200) -> list[Trip]:
        out = [t for t in self._trips.values() if t.driver_id == driver_id]
        out.sort(key=lambda t: t.creado_en, reverse=True)
        return [t.model_copy() for t in out[:limit]]

    def add_seat(self, sr: SeatRequest) -> SeatRequest:
        self._seats.append(sr.model_copy())
        return sr.model_copy()

    def seats_for_trip(self, trip_id: str) -> list[SeatRequest]:
        return [s.model_copy() for s in self._seats if s.trip_id == trip_id]

    def save_place(self, sp: SavedPlace) -> SavedPlace:
        self._places = [p for p in self._places if not (p.reporter_id == sp.reporter_id and p.etiqueta == sp.etiqueta)]
        self._places.append(sp.model_copy())
        return sp.model_copy()

    def list_places(self, reporter_id: str) -> list[SavedPlace]:
        return [p.model_copy() for p in self._places if p.reporter_id == reporter_id]

    def add_route_event(self, ev: RouteEvent) -> None:
        self._seq += 1
        ev.id = self._seq
        self._events.append(ev.model_copy())

    def route_stats(self, limit: int = 20) -> list[tuple[str, str, int]]:
        c = Counter((e.origen_id, e.destino_id) for e in self._events)
        return [(o, d, n) for (o, d), n in c.most_common(limit)]

    def link_identity(self, canal_key: str, reporter_id: str, now) -> None:
        self._links[canal_key] = reporter_id

    def get_link(self, canal_key: str) -> str | None:
        return self._links.get(canal_key)


class MemoryAnalyticsSource:
    """Lectura para el tablero sobre los repositorios en memoria (tests y demo sin BD)."""

    def __init__(self, drivers: "MemoryDriverRepository", incidents: MemoryIncidentRepository,
                 reporters: MemoryReporterRepository):
        self._d, self._i, self._r = drivers, incidents, reporters

    def consultas(self, desde: datetime) -> list[RouteEvent]:
        return [e for e in self._d._events if e.creado_en >= desde]

    def viajes(self, desde: datetime) -> list[Trip]:
        return [t for t in self._d._trips.values() if t.creado_en >= desde]

    def cupos(self, desde: datetime) -> list[SeatRequest]:
        return [s for s in self._d._seats if s.creado_en >= desde]

    def reportes(self, desde: datetime) -> list[ReporteResumen]:
        return [ReporteResumen(tipo=i.tipo, canal=r.canal, estado=i.estado.value, de_id=i.de_id, creado_en=r.creado_en)
                for i in self._i._data.values() for r in i.reports if r.creado_en >= desde]

    def usuarios(self) -> dict[str, int]:
        todos = list(self._r._data.values())
        return {"total": len(todos), "conductores": sum(getattr(r, "modo", "") == "conductor" for r in todos)}
