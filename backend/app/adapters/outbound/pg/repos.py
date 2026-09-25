"""Repositorios de feedback sobre PostgreSQL."""

import json

from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.outbound.pg.tables import (
    DriverProfileRow,
    IdentityLinkRow,
    IncidentRow,
    ReporterRow,
    ReportRow,
    RouteEventRow,
    SavedPlaceRow,
    SeatRequestRow,
    TripRow,
    VoteRow,
)
from app.domain.analytics import ReporteResumen
from app.domain.drivers import DriverProfile, RouteEvent, SavedPlace, SeatRequest, Trip
from app.domain.models import Incident, IncidentState, ReportEntry, Reporter, Role, VoteEntry

ABIERTOS = (IncidentState.activo.value, IncidentState.verificado.value)


def _mismo_tramo(de_id: str, a_id: str):
    return or_(
        and_(IncidentRow.de_id == de_id, IncidentRow.a_id == a_id),
        and_(IncidentRow.de_id == a_id, IncidentRow.a_id == de_id),
    )


def _a_dominio(row: IncidentRow) -> Incident:
    return Incident(
        id=row.id, tipo=row.tipo, de_id=row.de_id, a_id=row.a_id, modo=row.modo, lat=row.lat, lng=row.lng,
        nota=row.nota, estado=IncidentState(row.estado), confianza=row.confianza, creado_en=row.creado_en,
        expira_en=row.expira_en, verificado_por=row.verificado_por, resuelto=row.resuelto,
        reports=[
            ReportEntry(id=r.id, reporter_id=r.reporter_id, peso=r.peso, nota=r.nota, canal=r.canal, creado_en=r.creado_en)
            for r in row.reports
        ],
        votes=[
            VoteEntry(id=v.id, reporter_id=v.reporter_id, valor=v.valor, peso=v.peso, creado_en=v.creado_en)
            for v in row.votes
        ],
    )


class PgIncidentRepository:
    def __init__(self, sessions: sessionmaker[Session]):
        self._sessions = sessions

    def get(self, incident_id: str) -> Incident | None:
        with self._sessions() as s:
            row = s.get(IncidentRow, incident_id)
            return _a_dominio(row) if row else None

    def save(self, incident: Incident) -> Incident:
        with self._sessions.begin() as s:
            row = s.get(IncidentRow, incident.id)
            if row is None:
                row = IncidentRow(id=incident.id)
                s.add(row)
            for campo in ("tipo", "de_id", "a_id", "modo", "lat", "lng", "nota", "confianza",
                          "creado_en", "expira_en", "verificado_por", "resuelto"):
                setattr(row, campo, getattr(incident, campo))
            row.estado = incident.estado.value

            # Los reportes solo se agregan; los votos se actualizan por reportero (unique incident+reporter)
            for r in incident.reports:
                if r.id is None:
                    row.reports.append(ReportRow(
                        reporter_id=r.reporter_id, peso=r.peso, nota=r.nota, canal=r.canal, creado_en=r.creado_en
                    ))
            votos = {v.reporter_id: v for v in row.votes}
            for v in incident.votes:
                if existente := votos.get(v.reporter_id):
                    existente.valor, existente.peso, existente.creado_en = v.valor, v.peso, v.creado_en
                else:
                    row.votes.append(VoteRow(reporter_id=v.reporter_id, valor=v.valor, peso=v.peso, creado_en=v.creado_en))
            s.flush()
            return _a_dominio(row)

    def find_open(self, de_id: str, a_id: str, tipo: str, now: datetime) -> Incident | None:
        with self._sessions() as s:
            row = s.scalars(
                select(IncidentRow)
                .where(_mismo_tramo(de_id, a_id), IncidentRow.tipo == tipo,
                       IncidentRow.estado.in_(ABIERTOS), IncidentRow.expira_en > now)
                .order_by(IncidentRow.creado_en.desc())
                .limit(1)
            ).first()
            return _a_dominio(row) if row else None

    def list_current(self, now: datetime) -> list[Incident]:
        with self._sessions() as s:
            rows = s.scalars(
                select(IncidentRow)
                .where(IncidentRow.expira_en > now, IncidentRow.estado.in_(ABIERTOS))
                .order_by(IncidentRow.creado_en.desc())
            ).all()
            return [_a_dominio(r) for r in rows]

    def list_recent(self, limit: int, since: datetime | None = None, before: datetime | None = None) -> list[Incident]:
        q = select(IncidentRow).where(IncidentRow.estado != IncidentState.rechazado.value)
        if since is not None:
            q = q.where(IncidentRow.creado_en >= since)
        if before is not None:
            q = q.where(IncidentRow.creado_en < before)
        with self._sessions() as s:
            rows = s.scalars(q.order_by(IncidentRow.creado_en.desc()).limit(limit)).all()
            return [_a_dominio(r) for r in rows]

    def ratings(self, reporter_ids: list[str]) -> dict[str, tuple[int, int]]:
        if not reporter_ids:
            return {}
        with self._sessions() as s:
            filas = s.execute(
                select(
                    ReportRow.reporter_id,
                    func.count().filter(VoteRow.valor == "confirma"),
                    func.count().filter(VoteRow.valor == "niega"),
                )
                .join(VoteRow, VoteRow.incident_id == ReportRow.incident_id)
                .where(ReportRow.reporter_id.in_(reporter_ids), VoteRow.reporter_id != ReportRow.reporter_id)
                .group_by(ReportRow.reporter_id)
            ).all()
            return {rid: (likes, dislikes) for rid, likes, dislikes in filas}

    def list_expired_unresolved(self, now: datetime) -> list[Incident]:
        with self._sessions() as s:
            rows = s.scalars(
                select(IncidentRow).where(IncidentRow.expira_en <= now, IncidentRow.resuelto.is_(False))
            ).all()
            return [_a_dominio(r) for r in rows]

    def count_recent_reports(self, reporter_id: str, de_id: str, a_id: str, tipo: str, since: datetime) -> int:
        with self._sessions() as s:
            return s.scalar(
                select(func.count(ReportRow.id))
                .join(IncidentRow, ReportRow.incident_id == IncidentRow.id)
                .where(ReportRow.reporter_id == reporter_id, ReportRow.creado_en >= since,
                       IncidentRow.tipo == tipo, _mismo_tramo(de_id, a_id))
            ) or 0

    def delete_all(self) -> int:
        with self._sessions.begin() as s:
            return s.execute(delete(IncidentRow)).rowcount


class PgReporterRepository:
    def __init__(self, sessions: sessionmaker[Session]):
        self._sessions = sessions

    @staticmethod
    def _a_dominio(row: ReporterRow) -> Reporter:
        return Reporter(id=row.id, canal=row.canal, rol=Role(row.rol), nombre=row.nombre,
                        modo=row.modo or "pasajero", aciertos=row.aciertos, fallos=row.fallos,
                        creado_en=row.creado_en, ultimo_en=row.ultimo_en)

    def get(self, reporter_id: str) -> Reporter | None:
        with self._sessions() as s:
            row = s.get(ReporterRow, reporter_id)
            return self._a_dominio(row) if row else None

    def get_or_create(self, reporter_id: str, canal: str, rol: Role, now: datetime) -> Reporter:
        with self._sessions.begin() as s:
            s.execute(
                insert(ReporterRow)
                .values(id=reporter_id, canal=canal, rol=rol.value, aciertos=0, fallos=0, creado_en=now, ultimo_en=now)
                .on_conflict_do_update(index_elements=[ReporterRow.id], set_={"ultimo_en": now})
            )
            return self._a_dominio(s.get(ReporterRow, reporter_id))

    def add_outcome(self, reporter_ids: list[str], aciertos: int = 0, fallos: int = 0) -> None:
        if not reporter_ids:
            return
        with self._sessions.begin() as s:
            s.execute(
                update(ReporterRow)
                .where(ReporterRow.id.in_(reporter_ids))
                .values(aciertos=ReporterRow.aciertos + aciertos, fallos=ReporterRow.fallos + fallos)
            )

    def set_perfil(self, reporter_id: str, nombre: str | None, modo: str | None) -> Reporter:
        cambios: dict = {}
        if nombre is not None:
            cambios["nombre"] = nombre
        if modo is not None:
            cambios["modo"] = modo
        with self._sessions.begin() as s:
            if cambios:
                s.execute(update(ReporterRow).where(ReporterRow.id == reporter_id).values(**cambios))
            return self._a_dominio(s.get(ReporterRow, reporter_id))


# --- Módulo de conductores ---------------------------------------------------

def _trip_dom(r: TripRow) -> Trip:
    return Trip(
        id=r.id, driver_id=r.driver_id, driver_nombre=r.driver_nombre, ruta=r.ruta,
        origen_id=r.origen_id, destino_id=r.destino_id, hora=r.hora, cupos_total=r.cupos_total,
        cupos_libres=r.cupos_libres, estado=r.estado, lleno=r.lleno, lat=r.lat, lng=r.lng,
        salio_en=r.salio_en, desvio=r.desvio, paradas=json.loads(r.paradas) if r.paradas else [],
        corta_en=r.corta_en, creado_en=r.creado_en,
    )


class PgDriverRepository:
    def __init__(self, sessions: sessionmaker[Session]):
        self._sessions = sessions

    def get_profile(self, reporter_id: str) -> DriverProfile | None:
        with self._sessions() as s:
            r = s.get(DriverProfileRow, reporter_id)
            return DriverProfile(reporter_id=r.reporter_id, ruta=r.ruta, barrio_base=r.barrio_base,
                                 placa=r.placa, activo=r.activo, creado_en=r.creado_en) if r else None

    def save_profile(self, p: DriverProfile) -> DriverProfile:
        with self._sessions.begin() as s:
            row = s.get(DriverProfileRow, p.reporter_id)
            if row is None:
                row = DriverProfileRow(reporter_id=p.reporter_id, creado_en=p.creado_en)
                s.add(row)
            row.ruta, row.barrio_base, row.placa, row.activo = p.ruta, p.barrio_base, p.placa, p.activo
        return p

    def create_trip(self, t: Trip) -> Trip:
        with self._sessions.begin() as s:
            s.add(TripRow(
                id=t.id, driver_id=t.driver_id, driver_nombre=t.driver_nombre, ruta=t.ruta,
                origen_id=t.origen_id, destino_id=t.destino_id, hora=t.hora, cupos_total=t.cupos_total,
                cupos_libres=t.cupos_libres, estado=t.estado, lleno=t.lleno, lat=t.lat, lng=t.lng,
                salio_en=t.salio_en, desvio=t.desvio, paradas=json.dumps(t.paradas) if t.paradas else None,
                corta_en=t.corta_en, creado_en=t.creado_en,
            ))
        return t

    def get_trip(self, trip_id: str) -> Trip | None:
        with self._sessions() as s:
            r = s.get(TripRow, trip_id)
            return _trip_dom(r) if r else None

    def save_trip(self, t: Trip) -> Trip:
        with self._sessions.begin() as s:
            row = s.get(TripRow, t.id)
            if row is None:
                return t
            for c in ("driver_nombre", "ruta", "hora", "cupos_total", "cupos_libres",
                      "estado", "lleno", "lat", "lng", "salio_en", "desvio", "corta_en"):
                setattr(row, c, getattr(t, c))
            row.paradas = json.dumps(t.paradas) if t.paradas else None
        return t

    def list_trips(self, estados: list[str], barrio_id: str | None = None, limit: int = 50) -> list[Trip]:
        q = select(TripRow).where(TripRow.estado.in_(estados))
        if barrio_id:
            q = q.where(or_(TripRow.origen_id == barrio_id, TripRow.destino_id == barrio_id))
        with self._sessions() as s:
            rows = s.scalars(q.order_by(TripRow.creado_en.desc()).limit(limit)).all()
            return [_trip_dom(r) for r in rows]

    def driver_trips(self, driver_id: str, limit: int = 200) -> list[Trip]:
        with self._sessions() as s:
            rows = s.scalars(
                select(TripRow).where(TripRow.driver_id == driver_id)
                .order_by(TripRow.creado_en.desc()).limit(limit)
            ).all()
            return [_trip_dom(r) for r in rows]

    def add_seat(self, sr: SeatRequest) -> SeatRequest:
        with self._sessions.begin() as s:
            s.add(SeatRequestRow(
                id=sr.id, trip_id=sr.trip_id, passenger_id=sr.passenger_id,
                passenger_nombre=sr.passenger_nombre, baja_en=sr.baja_en, estado=sr.estado, creado_en=sr.creado_en,
            ))
        return sr

    def seats_for_trip(self, trip_id: str) -> list[SeatRequest]:
        with self._sessions() as s:
            rows = s.scalars(select(SeatRequestRow).where(SeatRequestRow.trip_id == trip_id)).all()
            return [SeatRequest(id=r.id, trip_id=r.trip_id, passenger_id=r.passenger_id,
                                passenger_nombre=r.passenger_nombre, baja_en=r.baja_en, estado=r.estado,
                                creado_en=r.creado_en)
                    for r in rows]

    def save_place(self, sp: SavedPlace) -> SavedPlace:
        with self._sessions.begin() as s:
            s.execute(insert(SavedPlaceRow).values(
                id=sp.id, reporter_id=sp.reporter_id, etiqueta=sp.etiqueta, nombre=sp.nombre,
                lat=sp.lat, lng=sp.lng, place_id=sp.place_id, creado_en=sp.creado_en,
            ).on_conflict_do_update(
                index_elements=[SavedPlaceRow.reporter_id, SavedPlaceRow.etiqueta],
                set_={"nombre": sp.nombre, "lat": sp.lat, "lng": sp.lng, "place_id": sp.place_id, "creado_en": sp.creado_en},
            ))
        return sp

    def list_places(self, reporter_id: str) -> list[SavedPlace]:
        with self._sessions() as s:
            rows = s.scalars(select(SavedPlaceRow).where(SavedPlaceRow.reporter_id == reporter_id)).all()
            return [SavedPlace(id=r.id, reporter_id=r.reporter_id, etiqueta=r.etiqueta, nombre=r.nombre,
                               lat=r.lat, lng=r.lng, place_id=r.place_id, creado_en=r.creado_en) for r in rows]

    def add_route_event(self, ev: RouteEvent) -> None:
        with self._sessions.begin() as s:
            s.add(RouteEventRow(reporter_id=ev.reporter_id, origen_id=ev.origen_id,
                                destino_id=ev.destino_id, canal=ev.canal, creado_en=ev.creado_en,
                                prioridad=ev.prioridad, modo=ev.modo, destino_final=ev.destino_final))

    def route_stats(self, limit: int = 20) -> list[tuple[str, str, int]]:
        with self._sessions() as s:
            rows = s.execute(
                select(RouteEventRow.origen_id, RouteEventRow.destino_id, func.count())
                .group_by(RouteEventRow.origen_id, RouteEventRow.destino_id)
                .order_by(func.count().desc()).limit(limit)
            ).all()
            return [(o, d, n) for o, d, n in rows]

    def link_identity(self, canal_key: str, reporter_id: str, now) -> None:
        with self._sessions.begin() as s:
            s.execute(insert(IdentityLinkRow).values(canal_key=canal_key, reporter_id=reporter_id, creado_en=now)
                      .on_conflict_do_update(index_elements=[IdentityLinkRow.canal_key],
                                             set_={"reporter_id": reporter_id, "creado_en": now}))

    def get_link(self, canal_key: str) -> str | None:
        with self._sessions() as s:
            r = s.get(IdentityLinkRow, canal_key)
            return r.reporter_id if r else None


class PgAnalyticsSource:
    """Lectura para el tablero de analítica (solo SELECT; columnas mínimas, sin datos personales)."""

    def __init__(self, sessions: sessionmaker[Session]):
        self._sessions = sessions

    def consultas(self, desde: datetime) -> list[RouteEvent]:
        c = RouteEventRow
        with self._sessions() as s:
            rows = s.execute(select(c.reporter_id, c.origen_id, c.destino_id, c.canal, c.prioridad, c.modo,
                                    c.destino_final, c.creado_en).where(c.creado_en >= desde)).all()
        return [RouteEvent.model_construct(reporter_id=r[0], origen_id=r[1], destino_id=r[2], canal=r[3],
                                           prioridad=r[4], modo=r[5], destino_final=r[6], creado_en=r[7], id=None)
                for r in rows]

    def viajes(self, desde: datetime) -> list[Trip]:
        with self._sessions() as s:
            rows = s.scalars(select(TripRow).where(TripRow.creado_en >= desde)).all()
            return [_trip_dom(r) for r in rows]

    def cupos(self, desde: datetime) -> list[SeatRequest]:
        c = SeatRequestRow
        with self._sessions() as s:
            rows = s.execute(select(c.id, c.trip_id, c.passenger_id, c.baja_en, c.estado, c.creado_en)
                             .where(c.creado_en >= desde)).all()
        return [SeatRequest.model_construct(id=r[0], trip_id=r[1], passenger_id=r[2], passenger_nombre="",
                                            baja_en=r[3], estado=r[4], creado_en=r[5]) for r in rows]

    def reportes(self, desde: datetime) -> list[ReporteResumen]:
        with self._sessions() as s:
            rows = s.execute(
                select(IncidentRow.tipo, ReportRow.canal, IncidentRow.estado, IncidentRow.de_id, ReportRow.creado_en)
                .join(ReportRow, ReportRow.incident_id == IncidentRow.id).where(ReportRow.creado_en >= desde)
            ).all()
        return [ReporteResumen(tipo=r[0], canal=r[1], estado=r[2], de_id=r[3], creado_en=r[4]) for r in rows]

    def usuarios(self) -> dict[str, int]:
        with self._sessions() as s:
            total = s.scalar(select(func.count()).select_from(ReporterRow)) or 0
            conductores = s.scalar(select(func.count()).select_from(ReporterRow)
                                   .where(ReporterRow.modo == "conductor")) or 0
        return {"total": total, "conductores": conductores}
