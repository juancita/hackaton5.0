"""Reportes ciudadanos con roles, reputación y confianza (spec 05)."""

import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.domain.errors import Conflict, InvalidInput, NotFound, RateLimited
from app.domain.models import (
    Actor,
    Incident,
    IncidentState,
    IncidentType,
    IncidentView,
    Network,
    Penalty,
    ReportEntry,
    Reporter,
    ReporterProfile,
    Role,
    VoteEntry,
)
from app.domain.routing import clave_tramo
from app.ports.outbound import IncidentRepository, ReporterRepository

TIPOS: dict[str, IncidentType] = {
    "derrumbe": IncidentType(label="Derrumbe / cierre vial", icono="⛰️", color="#8e44ad", bloquea=True, factor=None, vidaMin=180, sev=5),
    "bloqueo": IncidentType(label="Bloqueo / manifestación", icono="🚧", color="#e74c3c", bloquea=True, factor=None, vidaMin=120, sev=5),
    "trancon": IncidentType(label="Trancón fuerte", icono="🐢", color="#e67e22", bloquea=False, factor=1.8, vidaMin=60, sev=3),
    "lleno": IncidentType(label="Muy lleno / no para", icono="🧍", color="#f1c40f", bloquea=False, factor=1.4, vidaMin=45, sev=2),
    "sinservicio": IncidentType(label="Sin servicio", icono="⛔", color="#c0392b", bloquea=True, factor=None, vidaMin=90, sev=4),
    "novedad": IncidentType(label="Novedad / cambio", icono="ℹ️", color="#3498db", bloquea=False, factor=1.2, vidaMin=180, sev=1),
}

UMBRAL_EFECTO = 0.4       # por debajo no afecta rutas
UMBRAL_BLOQUEO = 0.7      # desde aquí un tipo que bloquea, bloquea
FACTOR_BLOQUEO_PARCIAL = 2.5
PESO_ADMIN = 1.0
VENTANA_ANTISPAM = timedelta(minutes=10)
RADIO_REPORTE_M = 1500    # un reporte por ubicación se asigna al tramo más cercano dentro de este radio


def reporter_id_para(canal: str, id_externo: str, salt: str) -> str:
    """Identidad anónima y estable: no se guarda el teléfono ni el id del canal en claro."""
    return hashlib.sha256(f"{salt}{canal}:{id_externo}".encode()).hexdigest()


def reputacion(r: Reporter) -> float:
    return (r.aciertos + 1) / (r.aciertos + r.fallos + 2)


def peso(r: Reporter) -> float:
    if r.rol == Role.admin:
        return PESO_ADMIN
    return 0.1 + 0.6 * reputacion(r)


def calcular_confianza(inc: Incident) -> float:
    if inc.estado == IncidentState.verificado:
        return 1.0
    if inc.estado == IncidentState.rechazado:
        return 0.0
    no_ocurre = 1.0
    for w in [r.peso for r in inc.reports] + [v.peso for v in inc.votes if v.valor == "confirma"]:
        no_ocurre *= 1 - w
    conf = 1 - no_ocurre
    for v in inc.votes:
        if v.valor == "niega":
            conf *= 1 - v.peso
    return round(conf, 4)


def utcnow() -> datetime:
    return datetime.now(UTC)


class ReportService:
    def __init__(
        self,
        network: Network,
        incidents: IncidentRepository,
        reporters: ReporterRepository,
        salt: str,
        clock: Callable[[], datetime] = utcnow,
    ):
        self._net = network
        self._incidents = incidents
        self._reporters = reporters
        self._salt = salt
        self._now = clock

    # --- Identidad -----------------------------------------------------------

    def actor_de_canal(self, canal: str, id_externo: str) -> Actor:
        return Actor(reporter_id=reporter_id_para(canal, id_externo, self._salt), canal=canal)

    @staticmethod
    def actor_admin(nombre: str | None = None) -> Actor:
        return Actor(reporter_id=f"admin:{nombre or 'default'}", canal="admin", rol=Role.admin)

    def _reporter(self, actor: Actor) -> Reporter:
        return self._reporters.get_or_create(actor.reporter_id, actor.canal, actor.rol, self._now())

    def perfil(self, actor: Actor) -> ReporterProfile:
        r = self._reporters.get(actor.reporter_id) or Reporter(id=actor.reporter_id, canal=actor.canal, rol=actor.rol)
        return ReporterProfile(rol=r.rol, aciertos=r.aciertos, fallos=r.fallos, reputacion=round(reputacion(r), 4), peso=round(peso(r), 4))

    # --- Reportar y votar ----------------------------------------------------

    def reportar_aqui(self, actor: Actor, tipo: str, lat: float, lng: float, nota: str = "") -> Incident:
        """Como Waze: el reporte se ubica donde está quien reporta y se asigna al tramo más cercano."""
        cercano = self._net.tramo_cercano(lat, lng)
        if not cercano or cercano[1] > RADIO_REPORTE_M:
            raise InvalidInput("Estás lejos de las rutas de Ciudad Bolívar. Acércate a una vía o ajusta el pin en el mapa.")
        tramo = cercano[0]
        return self.reportar(actor, tipo, tramo.de, tramo.a, tramo.modo, nota, posicion=(lat, lng))

    def reportar(
        self, actor: Actor, tipo: str, de_id: str, a_id: str, modo: str | None = None, nota: str = "",
        posicion: tuple[float, float] | None = None,
    ) -> Incident:
        if tipo not in TIPOS:
            raise InvalidInput(f"Tipo de incidente desconocido: {tipo}")
        tramo = self._net.tramo_entre(de_id, a_id, modo)
        if not tramo:
            raise InvalidInput(f"No existe un tramo {de_id} ↔ {a_id}" + (f" en {modo}" if modo else ""))
        now = self._now()
        if actor.rol != Role.admin and self._incidents.count_recent_reports(
            actor.reporter_id, de_id, a_id, tipo, now - VENTANA_ANTISPAM
        ):
            raise RateLimited("Ya reportaste esto hace poco. Gracias, lo tenemos en cuenta.")

        reporter = self._reporter(actor)
        inc = self._incidents.find_open(de_id, a_id, tipo, now)
        if inc is None:
            de, a = self._net.lugar(tramo.de), self._net.lugar(tramo.a)
            lat, lng = posicion or ((de.lat + a.lat) / 2, (de.lng + a.lng) / 2)
            inc = Incident(
                id=str(uuid.uuid4()), tipo=tipo, de_id=tramo.de, a_id=tramo.a, modo=tramo.modo,
                lat=lat, lng=lng, nota=nota or "",
                creado_en=now, expira_en=now + timedelta(minutes=TIPOS[tipo].vidaMin),
            )
        if any(r.reporter_id == actor.reporter_id for r in inc.reports):
            return inc  # el mismo reportero no suma dos veces
        inc.reports.append(ReportEntry(reporter_id=actor.reporter_id, peso=peso(reporter), nota=nota or "", canal=actor.canal, creado_en=now))
        if nota and not inc.nota:
            inc.nota = nota
        if actor.rol == Role.admin:
            return self._verificar(inc, actor)
        inc.confianza = calcular_confianza(inc)
        return self._incidents.save(inc)

    def votar(self, actor: Actor, incident_id: str, valor: str) -> Incident:
        if valor not in ("confirma", "niega"):
            raise InvalidInput("valor debe ser 'confirma' o 'niega'")
        inc = self._abierto(incident_id)
        reporter = self._reporter(actor)
        voto = VoteEntry(reporter_id=actor.reporter_id, valor=valor, peso=peso(reporter), creado_en=self._now())
        previo = next((v for v in inc.votes if v.reporter_id == actor.reporter_id), None)
        if previo:
            previo.valor, previo.peso, previo.creado_en = voto.valor, voto.peso, voto.creado_en
        else:
            inc.votes.append(voto)
        inc.confianza = calcular_confianza(inc)
        return self._incidents.save(inc)

    # --- Moderación (admin) --------------------------------------------------

    def verificar(self, admin: Actor, incident_id: str) -> Incident:
        return self._verificar(self._abierto(incident_id), admin)

    def rechazar(self, admin: Actor, incident_id: str) -> Incident:
        inc = self._abierto(incident_id)
        self._reporter(admin)
        inc.estado = IncidentState.rechazado
        inc.verificado_por = admin.reporter_id
        inc.confianza = 0.0
        inc.resuelto = True
        a_favor, en_contra = self._partes(inc)
        self._reporters.add_outcome(a_favor, fallos=1)
        self._reporters.add_outcome(en_contra, aciertos=1)
        return self._incidents.save(inc)

    def _verificar(self, inc: Incident, admin: Actor) -> Incident:
        self._reporter(admin)
        if inc.estado == IncidentState.verificado:
            return self._incidents.save(inc)  # ya se premió a los reporteros
        inc.estado = IncidentState.verificado
        inc.verificado_por = admin.reporter_id
        inc.confianza = 1.0
        inc.resuelto = True
        a_favor, en_contra = self._partes(inc)
        self._reporters.add_outcome(a_favor, aciertos=1)
        self._reporters.add_outcome(en_contra, fallos=1)
        return self._incidents.save(inc)

    @staticmethod
    def _partes(inc: Incident) -> tuple[list[str], list[str]]:
        """Reporteros (no admin) que apoyaron el incidente y los que lo negaron."""
        a_favor = {r.reporter_id for r in inc.reports} | {v.reporter_id for v in inc.votes if v.valor == "confirma"}
        en_contra = {v.reporter_id for v in inc.votes if v.valor == "niega"}
        es_usuario = lambda rid: not rid.startswith("admin:")  # noqa: E731
        return sorted(filter(es_usuario, a_favor)), sorted(filter(es_usuario, en_contra))

    def _abierto(self, incident_id: str) -> Incident:
        inc = self._incidents.get(incident_id)
        if not inc:
            raise NotFound("Incidente no encontrado")
        if inc.estado == IncidentState.rechazado or inc.expira_en <= self._now():
            raise Conflict("El incidente ya no está vigente")
        return inc

    def limpiar(self) -> int:
        return self._incidents.delete_all()

    # --- Lectura y efecto en rutas -------------------------------------------

    def _liquidar_vencidos(self) -> None:
        """Al vencer sin moderación, si la comunidad tenía razón (conf alta) se premia a quienes reportaron."""
        for inc in self._incidents.list_expired_unresolved(self._now()):
            if inc.estado == IncidentState.activo:
                if inc.confianza >= UMBRAL_BLOQUEO:
                    self._reporters.add_outcome(self._partes(inc)[0], aciertos=1)
                inc.estado = IncidentState.expirado
            inc.resuelto = True
            self._incidents.save(inc)

    def vigentes(self) -> list[Incident]:
        self._liquidar_vencidos()
        return self._incidents.list_current(self._now())

    @staticmethod
    def afecta_rutas(inc: Incident) -> bool:
        return inc.estado == IncidentState.verificado or (
            inc.estado == IncidentState.activo and inc.confianza >= UMBRAL_EFECTO
        )

    def penalizaciones(self) -> dict[str, Penalty]:
        pen: dict[str, Penalty] = {}
        for inc in self.vigentes():
            if not self.afecta_rutas(inc):
                continue
            t = TIPOS[inc.tipo]
            conf = inc.confianza
            if t.bloquea:
                bloqueado = conf >= UMBRAL_BLOQUEO or inc.estado == IncidentState.verificado
                factor = 1.0 if bloqueado else 1 + (FACTOR_BLOQUEO_PARCIAL - 1) * conf
            else:
                bloqueado = False
                factor = 1 + ((t.factor or 1) - 1) * conf
            nota = f": {inc.nota}" if inc.nota else ""
            motivo = f"{t.icono} {t.label}{nota} (confianza {round(conf * 100)}%)"
            key = clave_tramo(inc.de_id, inc.a_id, inc.modo)
            prev = pen.get(key)
            if prev:
                prev.bloqueado = prev.bloqueado or bloqueado
                prev.factor = max(prev.factor, factor)
                prev.motivo = f"{prev.motivo} · {motivo}"
                prev.incident_ids.append(inc.id)
            else:
                pen[key] = Penalty(bloqueado=bloqueado, factor=factor, motivo=motivo, incident_ids=[inc.id])
        return pen

    def vista(self, inc: Incident) -> IncidentView:
        t = TIPOS[inc.tipo]
        return IncidentView(
            id=inc.id, tipo=inc.tipo, label=t.label, icono=t.icono, de_id=inc.de_id, a_id=inc.a_id,
            modo=inc.modo, lat=inc.lat, lng=inc.lng, nota=inc.nota, estado=inc.estado,
            confianza=inc.confianza, n_reportes=len(inc.reports),
            n_confirma=sum(v.valor == "confirma" for v in inc.votes),
            n_niega=sum(v.valor == "niega" for v in inc.votes),
            afecta_rutas=self.afecta_rutas(inc), creado_en=inc.creado_en, expira_en=inc.expira_en,
        )
