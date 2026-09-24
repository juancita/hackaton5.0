"""Modelos del dominio. No dependen de FastAPI, SQLAlchemy ni del canal.

Los campos de ruta (`totalMin`, `freqMin`…) conservan el camelCase del front
(`web/js/engine.js`) para que el contrato JSON sea el mismo que ya consume la UI.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

Prioridad = Literal["rapido", "barato", "transbordos"]
PRIORIDADES: tuple[Prioridad, ...] = ("rapido", "barato", "transbordos")


# --- Red de transporte -------------------------------------------------------

class Mode(BaseModel):
    nombre: str
    icono: str
    color: str
    formal: bool


class Place(BaseModel):
    id: str
    nombre: str
    tipo: str
    zona: str
    lat: float
    lng: float
    x: float = 0
    y: float = 0


class Segment(BaseModel):
    """Tramo: arista no dirigida entre dos paraderos con un modo de transporte."""
    de: str
    a: str
    modo: str
    min: float
    cop: float
    freqMin: float
    ruta: str


class Camera(BaseModel):
    id: str
    nombre: str
    tramo: dict[str, str]
    lat: float
    lng: float


class Network(BaseModel):
    modos: dict[str, Mode]
    paraderos: list[Place]
    tramos: list[Segment]
    camaras: list[Camera] = []
    alias: dict[str, str] = {}

    def lugar(self, place_id: str) -> Place | None:
        return next((p for p in self.paraderos if p.id == place_id), None)

    def tramo_entre(self, de: str, a: str, modo: str | None = None) -> Segment | None:
        for t in self.tramos:
            if {t.de, t.a} == {de, a} and (modo is None or t.modo == modo):
                return t
        return None


# --- Lugares -----------------------------------------------------------------

class Suggestion(Place):
    via: Literal["nombre", "alias"]


class Resolution(BaseModel):
    estado: Literal["exacto", "ambiguo", "ninguno"]
    lugar: Place | None = None
    candidatos: list[Place] = []


# --- Rutas -------------------------------------------------------------------

class Penalty(BaseModel):
    bloqueado: bool = False
    factor: float = 1.0
    motivo: str | None = None
    incident_ids: list[str] = []


class Leg(BaseModel):
    modo: str
    ruta: str
    desde: str
    hasta: str
    min: float
    cop: float
    espera: float
    motivo: str | None = None
    paradas: list[str]


class RouteOption(BaseModel):
    origen: str
    destino: str
    tramos: list[Leg]
    totalMin: int
    totalCop: float
    transbordos: int
    usaInformal: bool
    alertas: list[str]
    etiqueta: str = ""
    prioridad: Prioridad = "rapido"


class PlaceRef(BaseModel):
    id: str
    nombre: str


class TripPlan(BaseModel):
    origen: PlaceRef
    destino: PlaceRef
    opciones: list[RouteOption]
    recomendada: int = 0
    incidentes_aplicados: list[str] = []


# --- Reportes ----------------------------------------------------------------

class Role(StrEnum):
    usuario = "usuario"
    admin = "admin"


class IncidentState(StrEnum):
    activo = "activo"
    verificado = "verificado"
    rechazado = "rechazado"
    expirado = "expirado"


class IncidentType(BaseModel):
    label: str
    icono: str
    color: str
    bloquea: bool
    factor: float | None
    vidaMin: int
    sev: int


class Actor(BaseModel):
    """Quién hace la petición. Se deriva del canal; nunca se pide una cuenta."""
    reporter_id: str
    canal: str
    rol: Role = Role.usuario


class Reporter(BaseModel):
    id: str
    canal: str
    rol: Role = Role.usuario
    aciertos: int = 0
    fallos: int = 0
    creado_en: datetime | None = None
    ultimo_en: datetime | None = None


class ReportEntry(BaseModel):
    id: int | None = None
    reporter_id: str
    peso: float
    nota: str = ""
    canal: str
    creado_en: datetime


class VoteEntry(BaseModel):
    id: int | None = None
    reporter_id: str
    valor: Literal["confirma", "niega"]
    peso: float
    creado_en: datetime


class Incident(BaseModel):
    id: str
    tipo: str
    de_id: str
    a_id: str
    modo: str
    lat: float
    lng: float
    nota: str = ""
    estado: IncidentState = IncidentState.activo
    confianza: float = 0.0
    creado_en: datetime
    expira_en: datetime
    verificado_por: str | None = None
    resuelto: bool = False
    reports: list[ReportEntry] = []
    votes: list[VoteEntry] = []


class IncidentView(BaseModel):
    id: str
    tipo: str
    label: str
    icono: str
    de_id: str
    a_id: str
    modo: str
    lat: float
    lng: float
    nota: str
    estado: IncidentState
    confianza: float
    n_reportes: int
    n_confirma: int
    n_niega: int
    afecta_rutas: bool
    creado_en: datetime
    expira_en: datetime


class ReporterProfile(BaseModel):
    rol: Role
    aciertos: int
    fallos: int
    reputacion: float
    peso: float


# --- Asistente ---------------------------------------------------------------

Canal = Literal["web", "telegram", "whatsapp"]


class InboundMessage(BaseModel):
    """Lo que cualquier canal entrega al asistente."""
    canal: Canal
    user_id: str
    texto: str = ""
    nombre: str | None = None


class QuickReply(BaseModel):
    id: str
    label: str


class OutboundMessage(BaseModel):
    """Respuesta completa: cada canal muestra lo que pueda."""
    texto: str
    texto_base: str
    opciones_rapidas: list[QuickReply] = []
    paso: str
    modo: str | None = None
    plan: TripPlan | None = None
    reporte: IncidentView | None = None


class Conversation(BaseModel):
    key: str
    modo: Literal["guiada", "manual"] | None = None
    paso: str = "inicio"
    origen_id: str | None = None
    destino_id: str | None = None
    prioridad: Prioridad | None = None
    pendiente: Literal["origen", "destino"] | None = None
    candidatos: list[str] = []
    ultimo_plan: TripPlan | None = None
    updated_at: datetime | None = None


class RefineContext(BaseModel):
    mensaje_usuario: str
    texto_base: str
    hechos: dict[str, Any] = Field(default_factory=dict)
    canal: str
