"""API REST: lugares, rutas, red de transporte y reportes."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field, model_validator

from app.adapters.inbound.deps import get_actor, get_container, get_viewer_id, require_admin
from app.container import Container
from app.domain.models import (
    Actor,
    IncidentType,
    IncidentView,
    MapaRuta,
    Network,
    Prioridad,
    ReporterProfile,
    Resolution,
    Suggestion,
    TripPlan,
)
from app.domain import mapas
from app.domain.errors import InvalidInput
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
    # Medios permitidos (claves de /network modos). Vacío/None = todos; caminar siempre vale.
    modos: list[str] | None = None


@router.post("/routes", response_model=TripPlan, tags=["rutas"])
def routes(body: RouteRequest, c: Container = Depends(get_container)) -> TripPlan:
    return c.trip.ejecutar(body.origen_id, body.destino_id, body.prioridad, body.modos or None)


_cache_mapas: dict[tuple[str, str], bytes] = {}


def parametros_mapa(mapa: MapaRuta) -> dict[str, str]:
    q = {"r": mapa.ruta}
    if mapa.ubicacion:
        q["u"] = f"{mapa.ubicacion[0]:.5f},{mapa.ubicacion[1]:.5f}"
    return q


def imagen_mapa(c: Container, r: str, u: str = "") -> bytes:
    """JPEG de la ruta, cacheado: el webhook lo genera antes de responder y Telegram luego lo descarga."""
    clave = (r, u)
    if clave not in _cache_mapas:
        try:
            lat, lng = (float(v) for v in u.split(",")) if u else (None, None)
        except ValueError:
            raise InvalidInput("Ubicación inválida: usa lat,lng") from None
        ubicacion = (lat, lng) if lat is not None and -90 <= lat <= 90 and -180 <= lng <= 180 else None
        imagen = c.mapas.render(mapas.construir(r, c.network, ubicacion))
        if len(_cache_mapas) > 200:
            _cache_mapas.clear()
        _cache_mapas[clave] = imagen
    return _cache_mapas[clave]


@router.get("/mapas/ruta.jpg", tags=["rutas"], response_class=Response,
            responses={200: {"content": {"image/jpeg": {}}}})
def route_map(
    r: str = Query(max_length=300, description="Ruta codificada (la que trae `mapa.ruta` en el chat)"),
    u: str = Query("", max_length=40, description="Ubicación del usuario `lat,lng` (opcional)"),
    c: Container = Depends(get_container),
) -> Response:
    """Imagen de la ruta: trazado por modo, A (origen), B (destino), transbordos y la ubicación."""
    return Response(imagen_mapa(c, r, u), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})


# --- Reportes ------------------------------------------------------------------

class IncidentRequest(BaseModel):
    """Por ubicación (lat/lng, como Waze) o, para integraciones, por tramo explícito (de_id/a_id)."""
    tipo: str
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    de_id: str | None = None
    a_id: str | None = None
    modo: str | None = None
    nota: str = Field(default="", max_length=280)

    @model_validator(mode="after")
    def _ubicacion_o_tramo(self) -> "IncidentRequest":
        if (self.lat is None or self.lng is None) and not (self.de_id and self.a_id):
            raise ValueError("Envía tu ubicación (lat, lng) o el tramo (de_id, a_id)")
        return self


class VoteRequest(BaseModel):
    valor: Literal["confirma", "niega"]


@router.get("/incident-types", response_model=dict[str, IncidentType], tags=["reportes"])
def incident_types() -> dict[str, IncidentType]:
    return TIPOS


@router.get("/incidents", response_model=list[IncidentView], tags=["reportes"])
def incidents(viewer: str | None = Depends(get_viewer_id), c: Container = Depends(get_container)) -> list[IncidentView]:
    return c.reports.vistas(c.reports.vigentes(), viewer)


@router.get("/incidents/recent", response_model=list[IncidentView], tags=["reportes"])
def recent_incidents(
    horas: int | None = Query(None, ge=1, le=168),
    antes: datetime | None = None,
    limit: int = Query(30, ge=1, le=100),
    viewer: str | None = Depends(get_viewer_id),
    c: Container = Depends(get_container),
) -> list[IncidentView]:
    """Últimos reportes guardados (vigentes y vencidos), más nuevos primero.
    `horas`: solo los de las últimas N horas. `antes`: los creados antes de esa fecha (scroll infinito)."""
    return c.reports.vistas(c.reports.recientes(horas, limit, antes), viewer)


@router.post("/incidents", response_model=IncidentView, status_code=201, tags=["reportes"])
def create_incident(
    body: IncidentRequest, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)
) -> IncidentView:
    if body.de_id and body.a_id:
        pos = (body.lat, body.lng) if body.lat is not None and body.lng is not None else None
        inc = c.reports.reportar(actor, body.tipo, body.de_id, body.a_id, body.modo, body.nota, posicion=pos)
    else:
        inc = c.reports.reportar_aqui(actor, body.tipo, body.lat, body.lng, body.nota)
    return c.reports.vista(inc, actor.reporter_id)


@router.post("/incidents/{incident_id}/votos", response_model=IncidentView, tags=["reportes"])
def vote(
    incident_id: str, body: VoteRequest, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)
) -> IncidentView:
    return c.reports.vista(c.reports.votar(actor, incident_id, body.valor), actor.reporter_id)


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
