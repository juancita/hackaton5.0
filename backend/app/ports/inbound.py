"""Puertos de entrada: lo que el dominio ofrece a cualquier canal (REST, Telegram, WhatsApp…)."""

from typing import Protocol

from app.domain.models import Actor, Incident, InboundMessage, OutboundMessage, Prioridad, TripPlan


class ChatPort(Protocol):
    async def handle(self, msg: InboundMessage) -> OutboundMessage: ...


class TripPort(Protocol):
    """Punto de entrada + punto de salida -> toda la información del viaje."""

    def ejecutar(self, origen_id: str, destino_id: str, prioridad: Prioridad | None = None) -> TripPlan: ...


class ReportPort(Protocol):
    def reportar(self, actor: Actor, tipo: str, de_id: str, a_id: str, modo: str | None = None, nota: str = "") -> Incident: ...
    def votar(self, actor: Actor, incident_id: str, valor: str) -> Incident: ...
