"""Puertos de salida: lo que el dominio necesita del mundo exterior."""

from datetime import datetime
from typing import Protocol

from app.domain.models import (
    Conversation,
    Incident,
    InterpretContext,
    Interpretation,
    Network,
    RefineContext,
    Reporter,
    Role,
)


class NetworkCatalog(Protocol):
    def load(self) -> Network: ...


class IncidentRepository(Protocol):
    def get(self, incident_id: str) -> Incident | None: ...
    def save(self, incident: Incident) -> Incident: ...
    def find_open(self, de_id: str, a_id: str, tipo: str, now: datetime) -> Incident | None:
        """Incidente activo o verificado, vigente, sobre el tramo (en cualquier sentido) y del tipo dado."""
        ...
    def list_current(self, now: datetime) -> list[Incident]:
        """Incidentes vigentes que no fueron rechazados."""
        ...
    def list_expired_unresolved(self, now: datetime) -> list[Incident]: ...
    def list_recent(self, limit: int, since: datetime | None = None, before: datetime | None = None) -> list[Incident]:
        """Últimos incidentes (vigentes o no, sin los rechazados), más nuevos primero.
        `since`: creados desde entonces; `before`: creados antes (cursor para paginar hacia atrás)."""
        ...
    def ratings(self, reporter_ids: list[str]) -> dict[str, tuple[int, int]]:
        """(👍, 👎) que otras personas dieron a los incidentes que reportó cada reportero."""
        ...
    def count_recent_reports(self, reporter_id: str, de_id: str, a_id: str, tipo: str, since: datetime) -> int: ...
    def delete_all(self) -> int: ...


class ReporterRepository(Protocol):
    def get(self, reporter_id: str) -> Reporter | None: ...
    def get_or_create(self, reporter_id: str, canal: str, rol: Role, now: datetime) -> Reporter: ...
    def add_outcome(self, reporter_ids: list[str], aciertos: int = 0, fallos: int = 0) -> None: ...


class ConversationStore(Protocol):
    def get(self, key: str) -> Conversation | None: ...
    def save(self, conv: Conversation) -> None: ...


class ResponseRefiner(Protocol):
    """Puerto universal de LLM: recibe el texto del dominio y devuelve una versión más natural."""

    async def refine(self, ctx: RefineContext) -> str: ...


class MessageInterpreter(Protocol):
    """Puerto de LLM para entender texto libre. `None` = no hay LLM o no entendió."""

    async def interpret(self, ctx: InterpretContext) -> Interpretation | None: ...
