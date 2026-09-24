"""Implementaciones en memoria. Conversaciones en producción; repos de feedback solo para pruebas o demo sin BD."""

from datetime import datetime

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
