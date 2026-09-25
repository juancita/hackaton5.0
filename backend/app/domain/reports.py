"""Reportes ciudadanos con roles, reputación y confianza (spec 05)."""

import hashlib
import re
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
    "derrumbe": IncidentType(label="Derrumbe / cierre vial", icono="⛰️", color="#8e44ad", bloquea=True, factor=None, vidaMin=120, sev=5),
    "bloqueo": IncidentType(label="Bloqueo / manifestación", icono="🚧", color="#e74c3c", bloquea=True, factor=None, vidaMin=120, sev=5),
    "trancon": IncidentType(label="Trancón fuerte", icono="🐢", color="#e67e22", bloquea=False, factor=1.8, vidaMin=60, sev=3),
    "lleno": IncidentType(label="Muy lleno / no para", icono="🧍", color="#f1c40f", bloquea=False, factor=1.4, vidaMin=45, sev=2),
    "sinservicio": IncidentType(label="Sin servicio", icono="⛔", color="#c0392b", bloquea=True, factor=None, vidaMin=90, sev=4),
    "novedad": IncidentType(label="Novedad / cambio", icono="ℹ️", color="#3498db", bloquea=False, factor=1.2, vidaMin=120, sev=1),
}

UMBRAL_EFECTO = 0.4       # por debajo no afecta rutas
UMBRAL_BLOQUEO = 0.7      # desde aquí un tipo que bloquea, bloquea
FACTOR_BLOQUEO_PARCIAL = 2.5
PESO_ADMIN = 1.0
VENTANA_ANTISPAM = timedelta(minutes=10)
RADIO_REPORTE_M = 1500    # un reporte por ubicación se asigna al tramo más cercano dentro de este radio

# Reputación en estrellas (0 a 5) calificada por la comunidad: cada 👍 ("sigue ahí") que otra
# persona da a uno de tus reportes vale 5 y cada 👎 ("ya no está") vale 0. Se promedia con un 5
# inicial, así que todos empiezan con 5 estrellas y un solo 👎 no te deja en cero.
ESTRELLAS_MAX = 5.0


def reporter_id_para(canal: str, id_externo: str, salt: str) -> str:
    """Identidad anónima y estable: no se guarda el teléfono ni el id del canal en claro."""
    return hashlib.sha256(f"{salt}{canal}:{id_externo}".encode()).hexdigest()


def normalizar_telefono(telefono: str) -> str:
    """Deja solo dígitos y toma los últimos 10 (Colombia). Así '573001234567' y '3001234567'
    (WhatsApp/Telegram vs. app) son la MISMA persona."""
    return re.sub(r"\D", "", telefono or "")[-10:]


def reporter_id_por_telefono(telefono: str, salt: str) -> str:
    """Identidad UNIFICADA por teléfono, independiente del canal (app, Telegram, WhatsApp).
    Se hashea con sal: el número nunca queda en claro en la base de datos."""
    return hashlib.sha256(f"{salt}tel:{normalizar_telefono(telefono)}".encode()).hexdigest()


def estrellas(likes: int, dislikes: int) -> float:
    return round(ESTRELLAS_MAX * (1 + likes) / (1 + likes + dislikes), 1)


def peso(r: Reporter, estrellas_r: float = ESTRELLAS_MAX) -> float:
    """5 estrellas pesan 0.4 (un solo reporte afecta rutas pero no bloquea); 0 estrellas, 0.1."""
    if r.rol == Role.admin:
        return PESO_ADMIN
    return 0.1 + 0.3 * estrellas_r / ESTRELLAS_MAX


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

    def actor_por_telefono(self, canal: str, telefono: str) -> Actor:
        """Identidad unificada por teléfono: la misma persona en la app y en Telegram/WhatsApp."""
        return Actor(reporter_id=reporter_id_por_telefono(telefono, self._salt), canal=canal)

    def registrar_perfil(self, actor: Actor, nombre: str | None, modo: str | None) -> Reporter:
        """Guarda/actualiza el nombre de usuario y el modo (pasajero/conductor)."""
        self._reporters.get_or_create(actor.reporter_id, actor.canal, actor.rol, self._now())
        modo_ok = modo if modo in ("pasajero", "conductor") else None
        return self._reporters.set_perfil(actor.reporter_id, (nombre or "").strip()[:40] or None, modo_ok)

    @staticmethod
    def actor_admin(nombre: str | None = None) -> Actor:
        return Actor(reporter_id=f"admin:{nombre or 'default'}", canal="admin", rol=Role.admin)

    def _reporter(self, actor: Actor) -> Reporter:
        return self._reporters.get_or_create(actor.reporter_id, actor.canal, actor.rol, self._now())

    def calificacion(self, reporter_id: str) -> tuple[int, int, float]:
        likes, dislikes = self._incidents.ratings([reporter_id]).get(reporter_id, (0, 0))
        return likes, dislikes, estrellas(likes, dislikes)

    def _peso(self, r: Reporter) -> float:
        return peso(r) if r.rol == Role.admin else peso(r, self.calificacion(r.id)[2])

    def perfil(self, actor: Actor) -> ReporterProfile:
        r = self._reporters.get(actor.reporter_id) or Reporter(id=actor.reporter_id, canal=actor.canal, rol=actor.rol)
        likes, dislikes, est = self.calificacion(r.id)
        return ReporterProfile(
            rol=r.rol, nombre=r.nombre, modo=r.modo, es_conductor=(r.modo == "conductor"),
            aciertos=r.aciertos, fallos=r.fallos, estrellas=est, likes=likes, dislikes=dislikes,
            reputacion=round(est / ESTRELLAS_MAX, 4), peso=round(self._peso(r), 4),
        )

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
        inc.reports.append(ReportEntry(reporter_id=actor.reporter_id, peso=self._peso(reporter), nota=nota or "", canal=actor.canal, creado_en=now))
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
        if any(r.reporter_id == actor.reporter_id for r in inc.reports):
            raise Conflict("No puedes calificar tu propio reporte")
        voto = VoteEntry(reporter_id=actor.reporter_id, valor=valor, peso=self._peso(reporter), creado_en=self._now())
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

    def recientes(self, horas: int | None = 24, limite: int = 30, antes: datetime | None = None) -> list[Incident]:
        """Últimos reportes (incluye los ya vencidos, como historial). `antes` pagina hacia atrás."""
        self._liquidar_vencidos()
        desde = self._now() - timedelta(hours=horas) if horas else None
        return self._incidents.list_recent(limite, since=desde, before=antes)

    def vistas(self, incidentes: list[Incident], viewer_id: str | None = None) -> list[IncidentView]:
        """Vistas con las estrellas de quien reportó, en una sola consulta."""
        autores = sorted({i.reports[0].reporter_id for i in incidentes if i.reports})
        cal = self._incidents.ratings([a for a in autores if not a.startswith("admin:")])
        out = []
        for inc in incidentes:
            v = self.vista(inc, viewer_id)
            autor = inc.reports[0].reporter_id if inc.reports else None
            v.estrellas_autor = None if not autor or autor.startswith("admin:") else estrellas(*cal.get(autor, (0, 0)))
            out.append(v)
        return out

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

    def vista(self, inc: Incident, viewer_id: str | None = None) -> IncidentView:
        """`viewer_id`: quien consulta, para marcar si el reporte es suyo y cuál fue su voto."""
        t = TIPOS[inc.tipo]
        mi_voto = next((v.valor for v in inc.votes if viewer_id and v.reporter_id == viewer_id), None)
        return IncidentView(
            id=inc.id, tipo=inc.tipo, label=t.label, icono=t.icono, de_id=inc.de_id, a_id=inc.a_id,
            modo=inc.modo, lat=inc.lat, lng=inc.lng, nota=inc.nota, estado=inc.estado,
            confianza=inc.confianza, n_reportes=len(inc.reports),
            n_confirma=sum(v.valor == "confirma" for v in inc.votes),
            n_niega=sum(v.valor == "niega" for v in inc.votes),
            afecta_rutas=self.afecta_rutas(inc) and inc.expira_en > self._now(),
            vigente=inc.expira_en > self._now() and inc.estado != IncidentState.rechazado,
            es_mio=bool(viewer_id) and any(r.reporter_id == viewer_id for r in inc.reports),
            mi_voto=mi_voto,
            creado_en=inc.creado_en, expira_en=inc.expira_en,
        )
