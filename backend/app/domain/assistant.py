"""Asistente conversacional con estado, modo guiado o manual (spec 02).

El asistente no sabe de qué canal viene el mensaje: recibe un `InboundMessage` y
devuelve un `OutboundMessage` con toda la información. Cada adaptador (web,
Telegram, WhatsApp) decide cómo mostrarlo.
"""

import asyncio
import copy
import logging
import re
from collections.abc import Callable
from datetime import datetime, timedelta

from app.domain.errors import DomainError, RateLimited
from app.domain.models import (
    Conversation,
    InboundMessage,
    Network,
    OutboundMessage,
    Place,
    Prioridad,
    QuickReply,
    RefineContext,
    Resolution,
    RouteOption,
    TripPlan,
)
from app.domain.places import PlaceService
from app.domain.reports import TIPOS, ReportService, utcnow
from app.domain.text import formato_cop, normalize, redondear
from app.domain.trip import PlanTripUseCase
from app.ports.outbound import ConversationStore, ResponseRefiner

log = logging.getLogger(__name__)

# --- Vocabulario ---------------------------------------------------------------

SALUDO = re.compile(r"^(hola|ola|buenas|buenos dias|buenas tardes|buenas noches|hey|hi)\b")
REINICIO = {"menu", "reiniciar", "inicio", "empezar", "volver a empezar", "cancelar"}
AYUDA = {"ayuda", "help", "que puedes hacer"}

OPC_MODO = [QuickReply(id="guiada", label="Guiada"), QuickReply(id="manual", label="Manual")]
OPC_PRIORIDAD = [
    QuickReply(id="rapido", label="Rápido"),
    QuickReply(id="barato", label="Barato"),
    QuickReply(id="transbordos", label="Menos transbordos"),
]
OPC_RESULTADO = [
    QuickReply(id="otra", label="Otra ruta"),
    QuickReply(id="alternativas", label="Ver alternativas"),
    QuickReply(id="reportar", label="Reportar"),
]

PREGUNTA_ORIGEN = "Paso 1 de 3 · ¿Desde dónde sales? 📍"
PREGUNTA_DESTINO = "Paso 2 de 3 · ¿A dónde te diriges? 🏁"
PREGUNTA_PRIORIDAD = "Paso 3 de 3 · ¿Qué prefieres?"
PREGUNTA_RESULTADO = "¿Qué sigue?"
INSTRUCCION_MANUAL = (
    "Modo manual ✍️ Escríbeme tu viaje como quieras, por ejemplo:\n"
    "• «de Sierra Morena al Hospital Meissen»\n"
    "• «voy a Paraíso, estoy en Lucero, lo más barato»"
)
INSTRUCCION_REPORTE = (
    "Cuéntame qué pasa y dónde, por ejemplo: «reporto un trancón en Perdomo» "
    "o «no está pasando el jeep en Paraíso»."
)

# Detección de reportes (port de detectarReporte en web/js/ai.js)
DISPARADOR_REPORTE = re.compile(
    r"report|hay un|hay una|se varo|varad|no esta pasando|no sube|bloque|derrumbe|trancon|"
    r"deslizamiento|manifestacion|protesta"
)
PALABRAS_TIPO: dict[str, list[str]] = {
    "derrumbe": ["derrumbe", "deslizamiento", "se cayo", "se vino"],
    "bloqueo": ["bloqueo", "bloquead", "manifestacion", "cerrada", "cierre", "protesta"],
    "trancon": ["trancon", "trafico", "atasco", "pegado"],
    "lleno": ["lleno", "no para", "repleto"],
    "sinservicio": ["no hay servicio", "sin servicio", "no esta pasando", "no sube", "no subio", "varado", "se varo"],
    "novedad": ["novedad", "cambio", "aviso"],
}

# Interpretación libre (port de interpretar en web/js/ai.js)
PATRON_DE_A = re.compile(r"\b(?:de|desde)\s+(.+?)\s+(?:a|al|hasta|para|hacia)\s+(.+)")
PATRON_DESTINO = re.compile(r"\b(?:ir|llegar|voy|vamos|vo)\s+(?:a|al|hasta|hacia|para)\s+(.+)")
PATRON_ORIGEN = re.compile(r"\b(?:estoy|salgo|sali|parto)\s+(?:en|de|desde|del)\s+(.+)")
CORTE = re.compile(r"\s+(?:y\s+)?(?:estoy|salgo|sali|parto|desde|voy|quiero|necesito|lo mas|la mas|por favor)\b")


def detectar_prioridad(n: str) -> Prioridad | None:
    if re.search(r"barat|econom|plata|cuesta menos", n):
        return "barato"
    if re.search(r"transbordo|cambios|directo|sin cambiar", n):
        return "transbordos"
    if re.search(r"rapid|pronto|afan", n):
        return "rapido"
    return None


def interpretar(n: str) -> tuple[str | None, str | None, Prioridad | None]:
    """Devuelve (texto de origen, texto de destino, prioridad) a partir de texto normalizado."""
    origen = destino = None
    if m := PATRON_DE_A.search(n):
        origen, destino = m.group(1), m.group(2)
    if not destino and (m := PATRON_DESTINO.search(n)):
        destino = m.group(1)
    if not origen and (m := PATRON_ORIGEN.search(n)):
        origen = m.group(1)
    cortar = lambda s: CORTE.split(s)[0].strip() if s else None  # noqa: E731
    return cortar(origen) or None, cortar(destino) or None, detectar_prioridad(n)


def explicar(op: RouteOption, net: Network) -> str:
    nombre = {p.id: p.nombre for p in net.paraderos}
    pasos = []
    for i, t in enumerate(op.tramos, 1):
        m = net.modos[t.modo]
        costo = f" · ${formato_cop(t.cop)}" if t.cop > 0 else ""
        alerta = f" ⚠️ {t.motivo}" if t.motivo else ""
        pasos.append(
            f"{i}. {m.icono} {m.nombre} ({t.ruta}): {nombre[t.desde]} → {nombre[t.hasta]} · {redondear(t.min)} min{costo}{alerta}"
        )
    sello = (
        "\n💡 Esta ruta usa transporte comunitario (informal) que no aparece en las apps tradicionales."
        if op.usaInformal else ""
    )
    return (
        f"🚀 {op.etiqueta}: ~{op.totalMin} min · ${formato_cop(op.totalCop)} · {op.transbordos} transbordo(s)\n\n"
        + "\n".join(pasos) + sello
    )


def _cifras(texto: str) -> set[str]:
    return set(re.findall(r"\d[\d.]*\d", texto))


def _reiniciar(conv: Conversation, **valores) -> None:
    """Deja la conversación como nueva (conservando la clave) y aplica `valores`."""
    for nombre, campo in Conversation.model_fields.items():
        if nombre != "key":
            setattr(conv, nombre, valores.get(nombre, copy.deepcopy(campo.get_default(call_default_factory=True))))


def _opciones_lugares(lugares: list[Place]) -> list[QuickReply]:
    return [QuickReply(id=p.id, label=p.nombre) for p in lugares]


class AssistantService:
    def __init__(
        self,
        network: Network,
        places: PlaceService,
        trip: PlanTripUseCase,
        reports: ReportService,
        store: ConversationStore,
        refiner: ResponseRefiner,
        ttl: timedelta = timedelta(minutes=30),
        refine_timeout_s: float = 4.0,
        clock: Callable[[], datetime] = utcnow,
    ):
        self._net = network
        self._places = places
        self._trip = trip
        self._reports = reports
        self._store = store
        self._refiner = refiner
        self._ttl = ttl
        self._timeout = refine_timeout_s
        self._now = clock

    # --- Punto de entrada (ChatPort) -------------------------------------------

    async def handle(self, msg: InboundMessage) -> OutboundMessage:
        key = f"{msg.canal}:{msg.user_id}"
        conv = self._store.get(key)
        if conv is None or (conv.updated_at and self._now() - conv.updated_at > self._ttl):
            conv = Conversation(key=key)
        out = await self._procesar(conv, msg)
        conv.updated_at = self._now()
        self._store.save(conv)
        return out

    async def _procesar(self, conv: Conversation, msg: InboundMessage) -> OutboundMessage:
        n = normalize(msg.texto)
        if not n:
            texto, opciones = self._pendiente(conv)
            return self._resp(conv, f"Por ahora solo entiendo mensajes de texto ✍️\n\n{texto}", opciones)

        # Comandos globales
        if n in REINICIO or SALUDO.match(n):
            _reiniciar(conv)  # vuelve a INICIO
            if SALUDO.match(n) and (directo := await self._consulta_directa(conv, msg, n)):
                return directo
            return self._saludo(conv, msg)
        if n in AYUDA:
            texto, opciones = self._pendiente(conv)
            return self._resp(conv, (
                "Esto es lo que puedo hacer:\n"
                "• Buscar rutas formales e informales en Ciudad Bolívar\n"
                "• Recibir reportes: «reporto un derrumbe en Paraíso»\n"
                "Escribe «menu» para empezar de nuevo, o «guiada» / «manual» para cambiar de modo."
                f"\n\n{texto}"
            ), opciones)
        if n in ("guiada", "guiado", "paso a paso"):
            return self._iniciar_guiada(conv)
        if n in ("manual", "libre"):
            return self._iniciar_manual(conv)

        # Reporte ciudadano: se atiende en cualquier paso sin perder el hilo
        if DISPARADOR_REPORTE.search(n):
            return await self._reporte(conv, msg, n)

        match conv.paso:
            case "inicio":
                if n in ("1",):
                    return self._iniciar_guiada(conv)
                if n in ("2",):
                    return self._iniciar_manual(conv)
                if directo := await self._consulta_directa(conv, msg, n):
                    return directo
                return self._saludo(conv, msg)
            case "origen" | "destino":
                return await self._paso_lugar(conv, msg, n)
            case "prioridad":
                conv.prioridad = self._prioridad_de_opcion(n)
                return await self._resultado(conv, msg)
            case "resultado":
                return await self._tras_resultado(conv, msg, n)
            case _:
                return await self._manual(conv, msg, n)

    # --- Inicio y modos --------------------------------------------------------

    def _saludo(self, conv: Conversation, msg: InboundMessage) -> OutboundMessage:
        nombre = f" {msg.nombre.split()[0]}" if msg.nombre else ""
        return self._resp(conv, (
            f"¡Hola{nombre}! Soy tu asistente de Muévete CB 🚡. Te ayudo a moverte por Ciudad Bolívar "
            "(TransMiCable, SITP, jeeps y colectivos) y a avisar novedades en la vía.\n\n"
            "¿Cómo prefieres que te ayude?\n• Guiada: te pregunto paso a paso\n• Manual: me escribes tu viaje libremente"
        ), OPC_MODO)

    async def _consulta_directa(self, conv: Conversation, msg: InboundMessage, n: str) -> OutboundMessage | None:
        """Si el primer mensaje ya trae origen o destino, se pasa a modo manual sin preguntar."""
        origen, destino, _ = interpretar(n)
        if origen or destino:
            conv.modo, conv.paso = "manual", "manual"
            return await self._manual(conv, msg, n)
        return None

    def _iniciar_guiada(self, conv: Conversation) -> OutboundMessage:
        _reiniciar(conv, modo="guiada", paso="origen")
        return self._preguntar_lugar(conv, PREGUNTA_ORIGEN)

    def _iniciar_manual(self, conv: Conversation) -> OutboundMessage:
        _reiniciar(conv, modo="manual", paso="manual")
        return self._resp(conv, INSTRUCCION_MANUAL)

    def _preguntar_lugar(self, conv: Conversation, pregunta: str, prefijo: str = "") -> OutboundMessage:
        populares = self._places.populares(5)
        conv.candidatos = [p.id for p in populares]
        return self._resp(conv, f"{prefijo}{pregunta}\nEscribe el barrio o paradero, o elige uno:", _opciones_lugares(populares))

    def _pendiente(self, conv: Conversation) -> tuple[str, list[QuickReply]]:
        """La pregunta que el usuario tiene pendiente en el paso actual."""
        lugares = _opciones_lugares([p for p in map(self._places.get, conv.candidatos) if p])
        match conv.paso:
            case "inicio":
                return "¿Prefieres la experiencia guiada o manual?", OPC_MODO
            case "origen":
                return PREGUNTA_ORIGEN, lugares
            case "destino":
                return PREGUNTA_DESTINO, lugares
            case "prioridad":
                return PREGUNTA_PRIORIDAD, OPC_PRIORIDAD
            case "resultado":
                return PREGUNTA_RESULTADO, OPC_RESULTADO
        if conv.pendiente == "origen":
            return "¿Desde dónde sales?", lugares
        if conv.pendiente == "destino":
            return "¿A dónde te diriges?", lugares
        return INSTRUCCION_MANUAL, []

    # --- Modo guiado -----------------------------------------------------------

    def _elegir_lugar(self, conv: Conversation, texto: str) -> Resolution:
        n = normalize(texto)
        if n.isdigit() and conv.candidatos:
            i = int(n) - 1
            if 0 <= i < len(conv.candidatos) and (p := self._places.get(conv.candidatos[i])):
                return Resolution(estado="exacto", lugar=p)
        return self._places.resolve(texto)

    def _no_resuelto(self, conv: Conversation, texto: str, res: Resolution) -> OutboundMessage:
        if res.estado == "ambiguo":
            conv.candidatos = [p.id for p in res.candidatos]
            return self._resp(conv, f"Encontré varios lugares para «{texto}». ¿Cuál es?", _opciones_lugares(res.candidatos))
        populares = self._places.populares(5)
        conv.candidatos = [p.id for p in populares]
        return self._resp(
            conv,
            f"No reconozco «{texto}» 🤔. Prueba con otro nombre de barrio o paradero, por ejemplo:",
            _opciones_lugares(populares),
        )

    async def _paso_lugar(self, conv: Conversation, msg: InboundMessage, n: str) -> OutboundMessage:
        res = self._elegir_lugar(conv, msg.texto)
        if res.estado != "exacto":
            return self._no_resuelto(conv, msg.texto.strip(), res)
        lugar = res.lugar
        conv.candidatos = []
        if conv.paso == "origen":
            conv.origen_id, conv.paso = lugar.id, "destino"
            return self._preguntar_lugar(conv, PREGUNTA_DESTINO, f"✅ Origen: {lugar.nombre}\n\n")
        if lugar.id == conv.origen_id:
            return self._preguntar_lugar(conv, PREGUNTA_DESTINO, "El destino no puede ser igual al origen 🙃\n\n")
        conv.destino_id, conv.paso = lugar.id, "prioridad"
        return self._resp(conv, f"✅ Destino: {lugar.nombre}\n\n{PREGUNTA_PRIORIDAD}", OPC_PRIORIDAD)

    @staticmethod
    def _prioridad_de_opcion(n: str) -> Prioridad:
        return {"1": "rapido", "2": "barato", "3": "transbordos"}.get(n) or detectar_prioridad(n) or "rapido"

    # --- Modo manual -----------------------------------------------------------

    async def _manual(self, conv: Conversation, msg: InboundMessage, n: str) -> OutboundMessage:
        conv.modo = conv.modo or "manual"
        conv.paso = "manual"
        origen_txt, destino_txt, prioridad = interpretar(n)

        # Respuesta directa a lo que se preguntó (un lugar o el número de un candidato)
        if not origen_txt and not destino_txt:
            campo = conv.pendiente or "destino"  # un lugar suelto se asume destino ("¿a dónde vas?")
            if campo == "origen":
                origen_txt = msg.texto
            else:
                destino_txt = msg.texto

        for campo, texto in (("origen", origen_txt), ("destino", destino_txt)):
            if not texto:
                continue
            res = self._elegir_lugar(conv, texto) if campo == conv.pendiente else self._places.resolve(texto)
            if res.estado != "exacto":
                conv.pendiente = campo
                return self._no_resuelto(conv, texto.strip(), res)
            setattr(conv, f"{campo}_id", res.lugar.id)
            conv.candidatos = []
        if prioridad:
            conv.prioridad = prioridad

        if conv.origen_id and conv.destino_id:
            if conv.origen_id == conv.destino_id:
                conv.destino_id, conv.pendiente = None, "destino"
                return self._resp(conv, "El destino no puede ser igual al origen 🙃 ¿A dónde te diriges?")
            conv.pendiente = None
            return await self._resultado(conv, msg)
        if conv.destino_id:
            conv.pendiente = "origen"
            destino = self._places.get(conv.destino_id).nombre
            return self._resp(conv, f"¿Desde dónde sales para llegar a {destino}?")
        conv.pendiente = "destino"
        origen = self._places.get(conv.origen_id).nombre
        return self._resp(conv, f"¿A dónde vas desde {origen}?")

    # --- Resultado -------------------------------------------------------------

    async def _resultado(self, conv: Conversation, msg: InboundMessage) -> OutboundMessage:
        prioridad = conv.prioridad or "rapido"
        plan = self._trip.ejecutar(conv.origen_id, conv.destino_id, prioridad)
        conv.paso, conv.ultimo_plan, conv.candidatos = "resultado", plan, []
        if not plan.opciones:
            return self._resp(conv, (
                f"No encontré ruta entre {plan.origen.nombre} y {plan.destino.nombre} 😕. "
                "Puede que un tramo esté bloqueado por un reporte. Prueba con un lugar cercano.\n\n"
                f"{PREGUNTA_RESULTADO}"
            ), OPC_RESULTADO, plan=plan)
        op = plan.opciones[plan.recomendada]
        base = explicar(op, self._net)
        pulido = await self._pulir(
            f"Quiero ir de {plan.origen.nombre} a {plan.destino.nombre} ({prioridad}). Mensaje original: {msg.texto}",
            base, {"ruta": op.model_dump()}, msg.canal,
        )
        cierre = f"\n\n{PREGUNTA_RESULTADO}"
        return self._resp(conv, base + cierre, OPC_RESULTADO, texto=pulido + cierre, plan=plan)

    async def _tras_resultado(self, conv: Conversation, msg: InboundMessage, n: str) -> OutboundMessage:
        if n in ("1", "otra", "otra ruta", "nueva", "nueva ruta"):
            return self._iniciar_guiada(conv) if conv.modo == "guiada" else self._iniciar_manual(conv)
        if n in ("2",) or "alternativa" in n:
            plan: TripPlan | None = conv.ultimo_plan
            if not plan or not plan.opciones:
                return self._resp(conv, f"No tengo alternativas para mostrar.\n\n{PREGUNTA_RESULTADO}", OPC_RESULTADO)
            base = "\n\n".join(explicar(o, self._net) for o in plan.opciones)
            return self._resp(conv, f"{base}\n\n{PREGUNTA_RESULTADO}", OPC_RESULTADO, plan=plan)
        if n in ("3",):
            return self._resp(conv, INSTRUCCION_REPORTE, OPC_RESULTADO)
        # Una consulta nueva escrita libremente
        origen, destino, _ = interpretar(n)
        if origen or destino or self._places.menciones(n):
            conv.origen_id = conv.destino_id = conv.prioridad = None
            return await self._manual(conv, msg, n)
        return self._resp(conv, PREGUNTA_RESULTADO, OPC_RESULTADO)

    # --- Reportes --------------------------------------------------------------

    async def _reporte(self, conv: Conversation, msg: InboundMessage, n: str) -> OutboundMessage:
        texto_pend, opciones_pend = self._pendiente(conv)
        recordatorio = f"\n\nSigamos: {texto_pend}" if conv.paso not in ("inicio",) else ""
        tipo = next((k for k, palabras in PALABRAS_TIPO.items() if any(w in n for w in palabras)), "novedad")
        lugares = self._places.menciones(n)
        if not lugares:
            return self._resp(conv, INSTRUCCION_REPORTE + recordatorio, opciones_pend)

        tramo = None
        if len(lugares) >= 2:
            tramo = self._net.tramo_entre(lugares[0].id, lugares[1].id)
        if not tramo:
            tramo = next((t for t in self._net.tramos if lugares[0].id in (t.de, t.a)), None)
        if not tramo:
            return self._resp(conv, f"No tengo rutas registradas en {lugares[0].nombre} todavía 🙏" + recordatorio, opciones_pend)

        actor = self._reports.actor_de_canal(msg.canal, msg.user_id)
        try:
            inc = self._reports.reportar(actor, tipo, tramo.de, tramo.a, tramo.modo, nota=msg.texto.strip()[:280])
        except RateLimited:
            return self._resp(conv, "Ya habías reportado eso hace poco 🙏 ¡Gracias por avisar!" + recordatorio, opciones_pend)
        except DomainError as e:
            return self._resp(conv, f"No pude registrar el reporte: {e}" + recordatorio, opciones_pend)

        vista = self._reports.vista(inc)
        t = TIPOS[tipo]
        de, a = self._places.get(inc.de_id).nombre, self._places.get(inc.a_id).nombre
        efecto = (
            "Ya lo tenemos en cuenta para recalcular las rutas de todos 🙌"
            if vista.afecta_rutas else
            "Lo verán otros vecinos; cuando más personas lo confirmen, afectará las rutas 🙌"
        )
        base = f"¡Gracias! {t.icono} Registré «{t.label}» en {de} ↔ {a}. {efecto}"
        pulido = await self._pulir(msg.texto, base, {"reporte": vista.model_dump(mode="json")}, msg.canal)
        return self._resp(conv, base + recordatorio, opciones_pend, texto=pulido + recordatorio, reporte=vista)

    # --- LLM -------------------------------------------------------------------

    async def _pulir(self, mensaje: str, base: str, hechos: dict, canal: str) -> str:
        """Pule con el LLM. Ante cualquier falla, o si cambia alguna cifra, se queda el texto del dominio."""
        try:
            ctx = RefineContext(mensaje_usuario=mensaje, texto_base=base, hechos=hechos, canal=canal)
            out = (await asyncio.wait_for(self._refiner.refine(ctx), self._timeout) or "").strip()
        except Exception:  # noqa: BLE001 — el LLM nunca debe tumbar la respuesta
            log.warning("El refinador de respuestas falló; se usa el texto base", exc_info=True)
            return base
        if not out or not _cifras(base) <= _cifras(out):
            return base
        return out

    # --- Utilidades ------------------------------------------------------------

    @staticmethod
    def _resp(
        conv: Conversation,
        texto_base: str,
        opciones: list[QuickReply] | None = None,
        *,
        texto: str | None = None,
        plan: TripPlan | None = None,
        reporte=None,
    ) -> OutboundMessage:
        return OutboundMessage(
            texto=texto or texto_base,
            texto_base=texto_base,
            opciones_rapidas=opciones or [],
            paso=conv.paso,
            modo=conv.modo,
            plan=plan,
            reporte=reporte,
        )
