"""Composición: conecta el dominio con los adaptadores según la configuración."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.adapters.outbound.json_catalog import JsonCatalog
from app.adapters.outbound.memory_repos import (
    MemoryConversationStore,
    MemoryIncidentRepository,
    MemoryReporterRepository,
)
from app.adapters.outbound.refiners import GeminiRefiner, NoopRefiner
from app.config import Settings
from app.domain.assistant import AssistantService
from app.domain.models import Network
from app.domain.places import PlaceService
from app.domain.reports import ReportService, utcnow
from app.domain.routing import RoutingService
from app.domain.trip import PlanTripUseCase
from app.ports.outbound import IncidentRepository, ReporterRepository, ResponseRefiner


@dataclass
class Container:
    settings: Settings
    network: Network
    places: PlaceService
    routing: RoutingService
    reports: ReportService
    trip: PlanTripUseCase
    assistant: AssistantService


def build_container(
    settings: Settings,
    *,
    incidents: IncidentRepository | None = None,
    reporters: ReporterRepository | None = None,
    refiner: ResponseRefiner | None = None,
    clock: Callable[[], datetime] = utcnow,
) -> Container:
    network = JsonCatalog().load()

    if incidents is None or reporters is None:
        if settings.storage == "postgres":
            from app.adapters.outbound.pg.db import make_session_factory
            from app.adapters.outbound.pg.repos import PgIncidentRepository, PgReporterRepository

            sessions = make_session_factory(settings.database_url)
            incidents, reporters = PgIncidentRepository(sessions), PgReporterRepository(sessions)
        else:
            incidents, reporters = MemoryIncidentRepository(), MemoryReporterRepository()

    if refiner is None:
        if settings.llm_provider == "gemini" and settings.gemini_api_key:
            refiner = GeminiRefiner(settings.gemini_api_key, settings.gemini_model)
        else:
            refiner = NoopRefiner()

    places = PlaceService(network)
    routing = RoutingService(network)
    reports = ReportService(network, incidents, reporters, settings.id_salt, clock)
    trip = PlanTripUseCase(network, routing, reports)
    assistant = AssistantService(
        network, places, trip, reports, MemoryConversationStore(), refiner,
        ttl=timedelta(minutes=settings.conversation_ttl_min),
        refine_timeout_s=settings.llm_timeout_s,
        clock=clock,
    )
    return Container(settings, network, places, routing, reports, trip, assistant)
