"""API del módulo de conductores informales, login por celular, lugares guardados,
cámaras de fotodetección y datos agregados (negocio)."""

import asyncio

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.adapters.inbound.deps import get_actor, get_container
from app.container import Container
from app.domain.drivers import DriverProfile, SavedPlace, Trip
from app.domain.errors import InvalidInput
from app.domain.models import Actor, RefineContext, ReporterProfile
from app.domain.reports import normalizar_telefono

router = APIRouter()


# --- Login por celular (identidad unificada app ↔ Telegram) -------------------

class LoginRequest(BaseModel):
    telefono: str = Field(min_length=7, max_length=20)
    nombre: str | None = Field(default=None, max_length=40)
    modo: str | None = None  # "pasajero" | "conductor"


class LoginResponse(BaseModel):
    client_id: str  # el front lo guarda y lo manda como header X-Client-Id
    perfil: ReporterProfile


@router.post("/auth/login", response_model=LoginResponse, tags=["identidad"])
def login(body: LoginRequest, c: Container = Depends(get_container)) -> LoginResponse:
    tel = normalizar_telefono(body.telefono)
    if len(tel) < 7:
        raise InvalidInput("Número de celular inválido")
    actor = c.reports.actor_por_telefono("web", tel)
    c.reports.registrar_perfil(actor, body.nombre, body.modo)
    return LoginResponse(client_id=f"tel:{tel}", perfil=c.reports.perfil(actor))


class PerfilRequest(BaseModel):
    nombre: str | None = Field(default=None, max_length=40)
    modo: str | None = None


@router.post("/me/perfil", response_model=ReporterProfile, tags=["identidad"])
def set_perfil(body: PerfilRequest, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> ReporterProfile:
    c.reports.registrar_perfil(actor, body.nombre, body.modo)
    return c.reports.perfil(actor)


# --- Lugares guardados (casa / paradero de salida) ----------------------------

class LugarRequest(BaseModel):
    etiqueta: str = Field(max_length=24)   # "casa" | "paradero" | ...
    nombre: str = Field(max_length=80)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    place_id: str | None = None


@router.get("/me/lugares", response_model=list[SavedPlace], tags=["identidad"])
def mis_lugares(actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> list[SavedPlace]:
    return c.drivers.lugares(actor.reporter_id)


@router.post("/me/lugares", response_model=SavedPlace, tags=["identidad"])
def guardar_lugar(body: LugarRequest, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> SavedPlace:
    return c.drivers.guardar_lugar(actor.reporter_id, body.etiqueta, body.nombre, body.lat, body.lng, body.place_id)


# --- Conductores y viajes -----------------------------------------------------

class PerfilConductorRequest(BaseModel):
    ruta: str = Field(max_length=80)
    barrio_base: str | None = None
    placa: str | None = Field(default=None, max_length=16)


@router.post("/conductores/perfil", response_model=DriverProfile, tags=["conductores"])
def perfil_conductor(body: PerfilConductorRequest, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> DriverProfile:
    c.reports.registrar_perfil(actor, None, "conductor")
    return c.drivers.registrar_conductor(actor.reporter_id, body.ruta, body.barrio_base, body.placa)


class ViajeRequest(BaseModel):
    origen_id: str
    destino_id: str
    hora: str = Field(pattern=r"^\d{1,2}:\d{2}$")
    cupos: int = Field(ge=1, le=30)
    ruta: str | None = Field(default=None, max_length=80)


def _nombre(c: Container, actor: Actor) -> str:
    r = c.reports.perfil(actor)
    return r.nombre or "Conductor"


@router.post("/conductores/viajes", response_model=Trip, tags=["conductores"])
def anunciar_viaje(body: ViajeRequest, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> Trip:
    return c.drivers.anunciar(actor.reporter_id, _nombre(c, actor), body.origen_id, body.destino_id,
                              body.hora, body.cupos, body.ruta)


@router.get("/conductores/mios", response_model=list[Trip], tags=["conductores"])
def mis_viajes(actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> list[Trip]:
    return c.drivers._repo.driver_trips(actor.reporter_id, 50)


@router.get("/conductores/{driver_id}/tendencia", tags=["conductores"])
async def tendencia(driver_id: str, c: Container = Depends(get_container)) -> dict:
    """Patrón de horarios del conductor a partir de su historial (memoria de rutas). La cuenta la hace el
    dominio; si hay LLM (Gemini), solo la redacta en lenguaje natural para los pasajeros."""
    data = c.drivers.tendencia(driver_id)
    data["ia"] = False
    if data["total"] and c.refiner and c.settings.llm_provider == "gemini":
        try:
            texto = await asyncio.wait_for(c.refiner.refine(RefineContext(
                mensaje_usuario="Explica a los pasajeros, en una frase cálida, cuándo suele salir este conductor informal.",
                texto_base=data["texto"], hechos=data, canal="web")), timeout=c.settings.llm_timeout_s)
            if texto:
                data["texto"], data["ia"] = texto, True
        except Exception:
            pass
    return data


class SalirRequest(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


@router.post("/conductores/viajes/{trip_id}/salir", response_model=Trip, tags=["conductores"])
def salir(trip_id: str, body: SalirRequest, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> Trip:
    return c.drivers.salir(trip_id, actor.reporter_id, body.lat, body.lng)


@router.post("/conductores/viajes/{trip_id}/lleno", response_model=Trip, tags=["conductores"])
def lleno(trip_id: str, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> Trip:
    return c.drivers.marcar_lleno(trip_id, actor.reporter_id)


class DesvioRequest(BaseModel):
    nota: str = Field(default="", max_length=200)


@router.post("/conductores/viajes/{trip_id}/desvio", response_model=Trip, tags=["conductores"])
def desvio(trip_id: str, body: DesvioRequest, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> Trip:
    """El conductor informal avisa que toma otra vía (protesta, cierre, derrumbe). Los pasajeros lo ven
    en el viaje y, si hay un tramo directo, queda como novedad en el mapa para toda la comunidad."""
    t = c.drivers.desvio(trip_id, actor.reporter_id, body.nota)
    if c.network.tramo_entre(t.origen_id, t.destino_id):
        try:
            c.reports.reportar(actor, "novedad", t.origen_id, t.destino_id, None, f"Desvío de {t.ruta}: {t.desvio}")
        except Exception:
            pass
    return t


@router.post("/conductores/viajes/{trip_id}/finalizar", response_model=Trip, tags=["conductores"])
def finalizar(trip_id: str, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> Trip:
    return c.drivers.finalizar(trip_id, actor.reporter_id)


# --- Pasajeros: ver próximos viajes y apartar cupo ----------------------------

@router.get("/viajes/proximos", response_model=list[Trip], tags=["viajes"])
def proximos(
    barrio: str | None = Query(None, description="place_id de origen o destino para filtrar"),
    limit: int = Query(50, ge=1, le=100),
    c: Container = Depends(get_container),
) -> list[Trip]:
    return c.drivers.proximos(barrio, limit)


@router.post("/viajes/{trip_id}/reservar", response_model=Trip, tags=["viajes"])
def reservar(trip_id: str, actor: Actor = Depends(get_actor), c: Container = Depends(get_container)) -> Trip:
    return c.drivers.reservar(trip_id, actor.reporter_id, c.reports.perfil(actor).nombre or "Pasajero")


@router.get("/viajes/demanda", tags=["viajes"])
def demanda(barrio: str, hora: str | None = None, c: Container = Depends(get_container)) -> dict:
    return c.drivers.demanda(barrio, hora)


# --- Horarios típicos (alimentan el modo OFFLINE) -----------------------------

@router.get("/conductores/horarios", tags=["conductores"])
def horarios(c: Container = Depends(get_container)) -> dict[str, list[str]]:
    return c.drivers.horarios_tipicos()


# --- Cámaras de fotodetección (Edge): reportan congestión a las rutas ---------

class CameraReading(BaseModel):
    """Lectura de una cámara de semáforo/fotodetección: nivel de congestión 0..1."""
    nivel: float = Field(ge=0, le=1)
    vehiculos: int | None = Field(default=None, ge=0)


@router.post("/cameras/{camera_id}/lectura", tags=["camaras"])
def camera_reading(camera_id: str, body: CameraReading, c: Container = Depends(get_container)) -> dict:
    """La cámara detecta congestión y la publica como incidente en su tramo (se combina con los reportes
    ciudadanos: más fuentes = más confianza). Solo se envía el DATO, nunca el video ni placas."""
    cam = next((cam for cam in c.network.camaras if cam.id == camera_id), None)
    if not cam:
        raise InvalidInput("Cámara desconocida")
    if body.nivel < 0.6:
        return {"ok": True, "accion": "sin_congestion", "nivel": body.nivel}
    tipo = "trancon" if body.nivel < 0.95 else "bloqueo"  # bloqueo solo con tráfico casi detenido
    tramo = cam.tramo
    actor = c.reports.actor_admin(f"camara:{camera_id}")  # sensor autoritativo → alta confianza
    nota = f"Cámara {cam.nombre}: congestión {int(body.nivel * 100)}%" + (f" ({body.vehiculos} vehículos)" if body.vehiculos else "")
    inc = c.reports.reportar(actor, tipo, tramo["de"], tramo["a"], tramo.get("modo"), nota)
    return {"ok": True, "accion": "incidente", "tipo": tipo, "incident_id": inc.id, "confianza": inc.confianza}


# --- Datos agregados de negocio (dashboard / venta de insights) ---------------

@router.get("/stats/rutas", tags=["negocio"])
def rutas_pedidas(limit: int = Query(20, ge=1, le=100), c: Container = Depends(get_container)) -> list[dict]:
    """Rutas más consultadas (dato agregado y anónimo). Base del modelo de negocio B2G."""
    return c.drivers.rutas_mas_pedidas(limit)


# --- Moovit / GTFS-realtime (integración preparada para alianza) --------------

@router.get("/integraciones/buses_tiempo_real", tags=["negocio"])
def buses_tiempo_real(c: Container = Depends(get_container)) -> dict:
    """Punto de integración para datos de buses en tiempo real (GTFS-realtime / alianza Moovit).
    Hoy devuelve el estado de la integración; cuando exista el feed/convenio, aquí se consumen las
    posiciones en vivo. Mantiene el mismo contrato para el front."""
    return {"disponible": False, "fuente": "GTFS-realtime / Moovit (pendiente de convenio)", "vehiculos": []}
