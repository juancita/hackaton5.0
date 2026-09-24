"""API REST: lugares, rutas, red de transporte y reportes."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.adapters.inbound.deps import get_actor, get_container, require_admin
from app.container import Container
from app.domain.models import (
    Actor,
    IncidentType,
    IncidentView,
    Network,
    Prioridad,
    ReporterProfile,
    Resolution,
    Suggestion,
    TripPlan,
)
from app.domain.reports import TIPOS

router = APIRouter()


@router.get("/health", tags=["sistema"])
def health() -> dict:
    return {"ok": True}


# --- Red y lugares -------------------------------------------------------------

@router.get("/network", response_model=Network, response_model_exclude={"alias"}, tags=["mapa"])
def network(c: Container = Depends(get_container)) -> Network:
    return c.network


@router.get("/places/suggest", response_model=list[Suggestion], tags=["lugares"])
def suggest(
    q: str = "",
    limit: int = Query(8, ge=1, le=20),
    c: Container = Depends(get_container),
) -> list[Suggestion]:
    return c.places.suggest(q, limit)


@router.get("/places/resolve", response_model=Resolution, tags=["lugares"])
def resolve(q: str, c: Container = Depends(get_container)) -> Resolution:
    return c.places.resolve(q)


# --- Rutas ---------------------------------------------------------------------

class RouteRequest(BaseModel):
    origen_id: str = Field(min_length=1)
    destino_id: str = Field(min_length=1)
    prioridad: Prioridad | None = None


@router.post("/routes", response_model=TripPlan, tags=["rutas"])
def routes(body: RouteRequest, c: Container = Depends(get_container)) -> TripPlan:
    return c.trip.ejecutar(body.origen_id, body.destino_id, body.prioridad)


# --- Reportes ------------------------------------------------------------------

class IncidentRequest(BaseModel):
    tipo: str
    de_id: str
    a_id: str
    modo: str | None = None
    nota: str = Field(default="", max_length=280)


class VoteRequest(BaseModel):
    valor: Literal["confirma", "niega"]


@router.get("/incident-types", response_model=dict[str, IncidentType], tags=["reportes"])
def incident_types() -> dict[str, IncidentType]:
    return TIPOS


@router.get("/incidents", response_model=list[IncidentView], tags=["reportes"])
def incidents(c: Container = Depends(get_container)) -> list[IncidentView]:
    return [c.reports.vista(i) for i in c.reports.vigentes()]


@router.post("/incidents", response_model=IncidentView, status_code=201, tags=["reportes"])
def create_incident(
    body: IncidentRequest, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)
) -> IncidentView:
    inc = c.reports.reportar(actor, body.tipo, body.de_id, body.a_id, body.modo, body.nota)
    return c.reports.vista(inc)


@router.post("/incidents/{incident_id}/votos", response_model=IncidentView, tags=["reportes"])
def vote(
    incident_id: str, body: VoteRequest, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)
) -> IncidentView:
    return c.reports.vista(c.reports.votar(actor, incident_id, body.valor))


@router.get("/reporters/me", response_model=ReporterProfile, tags=["reportes"])
def me(actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> ReporterProfile:
    return c.reports.perfil(actor)


# --- Admin ---------------------------------------------------------------------

@router.post("/admin/incidents/{incident_id}/verificar", response_model=IncidentView, tags=["admin"])
def verify(incident_id: str, admin: Actor = Depends(require_admin), c: Container = Depends(get_container)) -> IncidentView:
    return c.reports.vista(c.reports.verificar(admin, incident_id))


@router.post("/admin/incidents/{incident_id}/rechazar", response_model=IncidentView, tags=["admin"])
def reject(incident_id: str, admin: Actor = Depends(require_admin), c: Container = Depends(get_container)) -> IncidentView:
    return c.reports.vista(c.reports.rechazar(admin, incident_id))


@router.delete("/admin/incidents", tags=["admin"])
def clear(_: Actor = Depends(require_admin), c: Container = Depends(get_container)) -> dict:
    return {"eliminados": c.reports.limpiar()}
