"""Repositorios de feedback sobre PostgreSQL."""

from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.outbound.pg.tables import IncidentRow, ReporterRow, ReportRow, VoteRow
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
        return Reporter(id=row.id, canal=row.canal, rol=Role(row.rol), aciertos=row.aciertos, fallos=row.fallos,
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
