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

from app.domain import mapas
from app.domain.errors import DomainError, RateLimited
from app.domain.models import (
    Conversation,
    InboundMessage,
    IncidentState,
    InterpretContext,
    Interpretation,
    MapaRuta,
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
from app.ports.outbound import ConversationStore, MessageInterpreter, ResponseRefiner

log = logging.getLogger(__name__)

# --- Vocabulario ---------------------------------------------------------------

SALUDO = re.compile(r"^(hola|ola|buenas|buenos dias|buenas tardes|buenas noches|hey|hi)\b")
REINICIO = {"menu", "menu principal", "reiniciar", "inicio", "empezar", "volver a empezar"}
CANCELAR = {"cancelar", "cancela", "cancelar busqueda", "salir"}
AYUDA = {"ayuda", "help", "que puedes hacer"}

INCIDENTES = {"incidentes", "ultimos incidentes", "ver incidentes", "novedades", "reportes"}

OPC_CANCELAR = QuickReply(id="cancelar", label="✖️ Cancelar")
OPC_UBICACION = QuickReply(id="ubicacion", label="📍 Usar mi ubicación")
OPC_MENU = [
    QuickReply(id="guiada", label="🧭 Ruta guiada"),
    QuickReply(id="manual", label="✍️ Escribir mi viaje"),
    QuickReply(id="reportar", label="⚠️ Reportar novedad"),
    QuickReply(id="incidentes", label="📋 Últimos incidentes"),
    # Módulo de viajes (lo atiende RideChat antes que el asistente)
    QuickReply(id="ver_viajes", label="🕒 Viajes de jeeps"),
    QuickReply(id="soy_conductor", label="🚙 Soy conductor"),
    QuickReply(id="mi_casa", label="🏡 Mi casa"),
]
OPC_PRIORIDAD = [
    QuickReply(id="rapido", label="⚡ Llegar rápido"),
    QuickReply(id="barato", label="💰 Lo más barato"),
    QuickReply(id="transbordos", label="🔄 Menos transbordos"),
    OPC_CANCELAR,
]

PREGUNTA_MENU = (
    "¿Qué quieres hacer? Elige una opción 👇\n"
    "• 🧭 Ruta guiada: te pregunto paso a paso de dónde sales y a dónde vas\n"
    "• ✍️ Escribir mi viaje: me lo cuentas con tus palabras\n"
    "• ⚠️ Reportar novedad: avisa un trancón, derrumbe o bloqueo\n"
    "• 📋 Últimos incidentes: mira lo que han reportado los vecinos\n"
    "• 🕒 Viajes de jeeps: mira a qué hora salen y aparta tu cupo\n"
    "• 🚙 Soy conductor: publica tus salidas y mira cuántos te esperan\n"
    "• 🏡 Mi casa: guárdala y pide rutas con «a mi casa»"
)
PREGUNTA_ORIGEN = "Paso 1 de 3 · ¿Desde dónde sales? 📍"
PREGUNTA_DESTINO = "Paso 2 de 3 · ¿A dónde te diriges? 🏁"
PREGUNTA_PRIORIDAD = "Paso 3 de 3 · ¿Qué es lo más importante en este viaje? Elige una opción 👇"
PREGUNTA_RESULTADO = "¿Qué quieres hacer ahora? Elige una opción 👇"
PREGUNTA_TRAS_REPORTE = "¿Qué más quieres hacer? Elige una opción 👇"
INSTRUCCION_MANUAL = (
    "Modo manual ✍️ Escríbeme tu viaje como quieras, por ejemplo:\n"
    "• «de Sierra Morena al Hospital Meissen»\n"
    "• «voy a Paraíso, estoy en Lucero, lo más barato»"
)
INSTRUCCION_REPORTE = (
    "Cuéntame qué pasa y dónde, por ejemplo: «reporto un trancón en Perdomo» "
    "o «no está pasando el jeep en Paraíso»."
)
ELIGE_OPCION = "No entendí esa respuesta 🙈 Por favor toca una de las opciones de abajo 👇"
COMO_UBICACION = (
    "Para usar tu ubicación toca el botón «📍 Usar mi ubicación» (en WhatsApp: 📎 › Ubicación). "
    "También puedes escribir el barrio o paradero."
)
CERCANIA_MAX_M = 2_500  # más lejos que esto del paradero más cercano, no se toma como origen
N_INCIDENTES = 10

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
    """Deja la conversación como nueva (conservando la clave y la ubicación) y aplica `valores`."""
    for nombre, campo in Conversation.model_fields.items():
        if nombre not in ("key", "ubicacion"):
            setattr(conv, nombre, valores.get(nombre, copy.deepcopy(campo.get_default(call_default_factory=True))))


def _opciones_lugares(lugares: list[Place], conv: Conversation | None = None) -> list[QuickReply]:
    """Lugares como botones. Si se está pidiendo el origen, se ofrece también usar la ubicación."""
    pide_origen = conv is not None and (conv.paso == "origen" or (conv.paso == "manual" and conv.pendiente == "origen"))
    return [QuickReply(id=p.id, label=p.nombre) for p in lugares] + ([OPC_UBICACION] if pide_origen else []) + [OPC_CANCELAR]


def _hace(delta: timedelta) -> str:
    minutos = int(delta.total_seconds() // 60)
    if minutos < 1:
        return "hace un momento"
    if minutos < 60:
        return f"hace {minutos} min"
    if minutos < 24 * 60:
        return f"hace {minutos // 60} h"
    dias = minutos // (24 * 60)
    return f"hace {dias} día{'s' if dias > 1 else ''}"


def _opcion_elegida(conv: Conversation, n: str) -> str | None:
    """El id de la opción mostrada que el usuario eligió: por botón (su texto), por id o por número."""
    if n.isdigit():
        i = int(n) - 1
        return conv.opciones[i].id if 0 <= i < len(conv.opciones) else None
    return next((o.id for o in conv.opciones if n in (o.id, normalize(o.label))), None)


class AssistantService:
    def __init__(
        self,
        network: Network,
        places: PlaceService,
        trip: PlanTripUseCase,
        reports: ReportService,
        store: ConversationStore,
        refiner: ResponseRefiner,
        interpreter: MessageInterpreter | None = None,
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
        self._interpreter = interpreter
        self._lecturas: dict[int, Interpretation | None] = {}  # lectura del LLM por mensaje en curso
        self._ttl = ttl
        self._timeout = refine_timeout_s
        self._now = clock

    # --- Punto de entrada (ChatPort) -------------------------------------------

    async def handle(self, msg: InboundMessage) -> OutboundMessage:
        key = f"{msg.canal}:{msg.user_id}"
        conv = self._store.get(key)
        if conv is None or (conv.updated_at and self._now() - conv.updated_at > self._ttl):
            conv = Conversation(key=key)
        try:
            out = await self._procesar(conv, msg)
        finally:
            self._lecturas.pop(id(msg), None)
        conv.updated_at = self._now()
        self._store.save(conv)
        return out

    async def _procesar(self, conv: Conversation, msg: InboundMessage) -> OutboundMessage:
        if msg.ubicacion:
            return await self._con_ubicacion(conv, msg)
        n = normalize(msg.texto)
        if not n:
            texto, opciones = self._pendiente(conv)
            return self._resp(conv, f"Por ahora solo entiendo mensajes de texto ✍️\n\n{texto}", opciones)

        elegida = _opcion_elegida(conv, n)

        # Comandos globales
        if n in CANCELAR or elegida == "cancelar":
            _reiniciar(conv)
            return self._menu(conv, "Listo, cancelé la búsqueda ✋\n\n")
        if n in REINICIO or elegida == "menu":
            _reiniciar(conv)
            return self._menu(conv)
        if SALUDO.match(n):
            _reiniciar(conv)
            if directo := await self._consulta_directa(conv, msg, n):
                return directo
            return self._saludo(conv, msg)
        if n in AYUDA:
            texto, opciones = self._pendiente(conv)
            return self._resp(conv, (
                "Esto es lo que puedo hacer:\n"
                "• Buscar rutas formales e informales en Ciudad Bolívar\n"
                "• Recibir reportes: «reporto un derrumbe en Paraíso»\n"
                "Toca «Cancelar» o escribe «menu» cuando quieras volver al inicio."
                f"\n\n{texto}"
            ), opciones)
        if elegida == "guiada" or n in ("guiada", "guiado", "paso a paso"):
            return self._iniciar_guiada(conv)
        if elegida == "manual" or n in ("manual", "libre"):
            return self._iniciar_manual(conv)
        if elegida == "reportar" or (n in ("reportar", "reporte") and conv.paso in ("inicio", "resultado")):
            return self._pedir_reporte(conv)
        if elegida == "incidentes" or n in INCIDENTES:
            return self._ultimos_incidentes(conv)
        if elegida == "ubicacion" or n in ("ubicacion", "mi ubicacion", "usar mi ubicacion"):
            texto, opciones = self._pendiente(conv)
            return self._resp(conv, f"{COMO_UBICACION}\n\n{texto}", opciones)

        # Reporte ciudadano: se atiende en cualquier paso sin perder el hilo
        if conv.paso == "reporte" or DISPARADOR_REPORTE.search(n):
            return await self._reporte(conv, msg, n)

        match conv.paso:
            case "inicio":
                if directo := await self._consulta_directa(conv, msg, n):
                    return directo
                if accion := await self._accion_llm(conv, msg, n):
                    return accion
                if not conv.opciones:  # aún no ha visto el menú: se le presenta
                    return self._saludo(conv, msg)
                return self._elige_opcion(conv)
            case "origen" | "destino":
                return await self._paso_lugar(conv, msg, n)
            case "prioridad":
                conv.prioridad = elegida if elegida in ("rapido", "barato", "transbordos") else detectar_prioridad(n)
                if not conv.prioridad:
                    return self._elige_opcion(conv)
                return await self._resultado(conv, msg)
            case "resultado":
                return await self._tras_resultado(conv, msg, n, elegida)
            case _:
                return await self._manual(conv, msg, n)

    # --- Inicio y modos --------------------------------------------------------

    def _saludo(self, conv: Conversation, msg: InboundMessage) -> OutboundMessage:
        nombre = f" {msg.nombre.split()[0]}" if msg.nombre else ""
        return self._menu(conv, (
            f"¡Hola{nombre}! Soy tu asistente de Muévete CB 🚡. Te ayudo a moverte por Ciudad Bolívar "
            "(TransMiCable, SITP, jeeps y colectivos) y a avisar novedades en la vía.\n\n"
        ))

    def _menu(self, conv: Conversation, prefijo: str = "") -> OutboundMessage:
        return self._resp(conv, prefijo + PREGUNTA_MENU, OPC_MENU)

    def _elige_opcion(self, conv: Conversation) -> OutboundMessage:
        """Respuesta a algo que no es ninguna de las opciones de una pregunta cerrada."""
        pregunta, opciones = self._pendiente(conv)
        salida = " Si quieres dejar la búsqueda, toca «Cancelar»." if OPC_CANCELAR in opciones else ""
        return self._resp(conv, f"{ELIGE_OPCION}{salida}\n\n{pregunta}", opciones)

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
        return self._resp(conv, INSTRUCCION_MANUAL, [OPC_CANCELAR])

    def _pedir_reporte(self, conv: Conversation) -> OutboundMessage:
        _reiniciar(conv, paso="reporte")
        return self._resp(conv, INSTRUCCION_REPORTE, [OPC_CANCELAR])

    def _preguntar_lugar(self, conv: Conversation, pregunta: str, prefijo: str = "") -> OutboundMessage:
        populares = self._places.populares(5)
        conv.candidatos = [p.id for p in populares]
        return self._resp(conv, f"{prefijo}{pregunta}\nEscribe el barrio o paradero, o elige uno:", _opciones_lugares(populares, conv))

    def _pendiente(self, conv: Conversation) -> tuple[str, list[QuickReply]]:
        """La pregunta que el usuario tiene pendiente en el paso actual."""
        lugares = _opciones_lugares([p for p in map(self._places.get, conv.candidatos) if p], conv)
        match conv.paso:
            case "inicio":
                return PREGUNTA_MENU, OPC_MENU
            case "origen":
                return PREGUNTA_ORIGEN, lugares
            case "destino":
                return PREGUNTA_DESTINO, lugares
            case "prioridad":
                return PREGUNTA_PRIORIDAD, OPC_PRIORIDAD
            case "resultado":
                return PREGUNTA_RESULTADO, self._opc_resultado(conv)
            case "reporte":
                return INSTRUCCION_REPORTE, [OPC_CANCELAR]
        if conv.pendiente == "origen":
            return "¿Desde dónde sales?", lugares
        if conv.pendiente == "destino":
            return "¿A dónde te diriges?", lugares
        return INSTRUCCION_MANUAL, [OPC_CANCELAR]

    @staticmethod
    def _opc_resultado(conv: Conversation) -> list[QuickReply]:
        plan: TripPlan | None = conv.ultimo_plan
        alternativas = [QuickReply(id="alternativas", label="🔀 Ver alternativas")] if plan and len(plan.opciones) > 1 else []
        return [
            QuickReply(id="nueva", label="🔁 Buscar otra ruta"),
            *alternativas,
            *([] if conv.ubicacion else [QuickReply(id="ubicacion", label="📍 Marcar mi ubicación")]),
            QuickReply(id="reportar", label="⚠️ Reportar novedad"),
            QuickReply(id="menu", label="🏠 Menú principal"),
        ]

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
            return self._resp(conv, f"Encontré varios lugares para «{texto}». ¿Cuál es?", _opciones_lugares(res.candidatos, conv))
        populares = self._places.populares(5)
        conv.candidatos = [p.id for p in populares]
        return self._resp(
            conv,
            f"No reconozco «{texto}» 🤔. Prueba con otro nombre de barrio o paradero, por ejemplo:",
            _opciones_lugares(populares, conv),
        )

    async def _paso_lugar(self, conv: Conversation, msg: InboundMessage, n: str) -> OutboundMessage:
        res = self._elegir_lugar(conv, msg.texto)
        if (res.estado == "ninguno" or self._es_frase(n)) and (it := await self._entender(conv, msg)):
            if it.intencion == "reporte":
                return await self._reporte(conv, msg, n, it)
            if texto := getattr(it, conv.paso) or next(iter(it.lugares), None):
                if (leido := self._places.resolve(texto)).estado != "ninguno":
                    res = leido
            elif res.estado == "ninguno" and it.respuesta:
                pregunta, opciones = self._pendiente(conv)
                return self._resp(conv, f"{it.respuesta.strip()}\n\n{pregunta}", opciones)
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

    # --- Modo manual -----------------------------------------------------------

    async def _manual(
        self, conv: Conversation, msg: InboundMessage, n: str, it: Interpretation | None = None
    ) -> OutboundMessage:
        """Modo libre. `it` es la lectura del LLM; sin ella se interpreta con reglas."""
        conv.modo = conv.modo or "manual"
        conv.paso = "manual"
        origen_txt, destino_txt, prioridad = (it.origen, it.destino, it.prioridad) if it else interpretar(n)

        # Una frase sin «de X a Y» puede ser un reporte o una charla, no un lugar: que la lea el LLM
        if not (it or origen_txt or destino_txt) and self._es_frase(n) and (llm := await self._con_llm(conv, msg, n)):
            return llm

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
            # Las reglas no reconocen el lugar: que el LLM lea el mensaje completo
            if res.estado == "ninguno" and it is None and (llm := await self._con_llm(conv, msg, n)):
                return llm
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
                return self._resp(conv, "El destino no puede ser igual al origen 🙃 ¿A dónde te diriges?", [OPC_CANCELAR])
            conv.pendiente = None
            return await self._resultado(conv, msg)
        if conv.destino_id:
            conv.pendiente = "origen"
            destino = self._places.get(conv.destino_id).nombre
            return self._resp(conv, f"¿Desde dónde sales para llegar a {destino}?", [OPC_UBICACION, OPC_CANCELAR])
        conv.pendiente = "destino"
        origen = self._places.get(conv.origen_id).nombre
        return self._resp(conv, f"¿A dónde vas desde {origen}?", [OPC_CANCELAR])

    # --- Resultado -------------------------------------------------------------

    async def _resultado(self, conv: Conversation, msg: InboundMessage, prefijo: str = "") -> OutboundMessage:
        prioridad = conv.prioridad or "rapido"
        plan = self._trip.ejecutar(conv.origen_id, conv.destino_id, prioridad)
        conv.paso, conv.ultimo_plan, conv.candidatos = "resultado", plan, []
        if not plan.opciones:
            return self._resp(conv, (
                f"No encontré ruta entre {plan.origen.nombre} y {plan.destino.nombre} 😕. "
                "Puede que un tramo esté bloqueado por un reporte. Prueba con un lugar cercano.\n\n"
                f"{PREGUNTA_RESULTADO}"
            ), self._opc_resultado(conv), plan=plan)
        op = plan.opciones[plan.recomendada]
        base = explicar(op, self._net)
        pulido = await self._pulir(
            f"Quiero ir de {plan.origen.nombre} a {plan.destino.nombre} ({prioridad}). Mensaje original: {msg.texto}",
            base, {"ruta": op.model_dump()}, msg.canal,
        )
        cierre = f"\n\n{PREGUNTA_RESULTADO}"
        return self._resp(conv, prefijo + base + cierre, self._opc_resultado(conv), texto=prefijo + pulido + cierre,
                          plan=plan, mapa=self._mapa(op, conv))

    def _mapa(self, op: RouteOption, conv: Conversation) -> MapaRuta | None:
        try:
            return mapas.mapa_de(op, self._net, conv.ubicacion)
        except DomainError:  # una ruta sin tramos reconocibles no tiene mapa, pero sí respuesta
            log.warning("No se pudo armar el mapa de la ruta %s → %s", op.origen, op.destino)
            return None

    # --- Ubicación -------------------------------------------------------------

    def _paradero_cercano(self, punto: tuple[float, float]) -> tuple[Place, float]:
        return min(((p, mapas.distancia_m(punto, (p.lat, p.lng))) for p in self._net.paraderos), key=lambda x: x[1])

    async def _con_ubicacion(self, conv: Conversation, msg: InboundMessage) -> OutboundMessage:
        """El usuario compartió su ubicación: sirve de origen si se está pidiendo, y siempre sale en el mapa."""
        conv.ubicacion = msg.ubicacion
        cerca, dist = self._paradero_cercano(msg.ubicacion)
        distancia = f"{round(dist)} m" if dist < 1000 else f"{dist / 1000:.1f} km"
        if conv.paso == "resultado" and conv.ultimo_plan and conv.ultimo_plan.opciones:
            return await self._resultado(conv, msg, "📍 ¡Listo! Marqué tu ubicación en el mapa.\n\n")

        pide_origen = conv.paso in ("inicio", "origen") or (conv.paso == "manual" and not conv.origen_id)
        if pide_origen and dist <= CERCANIA_MAX_M:
            aviso = f"📍 Estás a {distancia} de {cerca.nombre}: saldrás desde ahí.\n\n"
            conv.candidatos = []
            if conv.paso == "manual":
                conv.origen_id, conv.pendiente = cerca.id, None
                if conv.destino_id and conv.destino_id != cerca.id:
                    return await self._resultado(conv, msg, aviso)
                conv.pendiente = "destino"
                return self._resp(conv, f"{aviso}¿A dónde vas?", [OPC_CANCELAR])
            _reiniciar(conv, modo="guiada", paso="destino", origen_id=cerca.id)
            return self._preguntar_lugar(conv, PREGUNTA_DESTINO, aviso)

        texto, opciones = self._pendiente(conv)
        if pide_origen:
            return self._resp(conv, (
                f"📍 Recibí tu ubicación, pero el paradero más cercano ({cerca.nombre}) está a {distancia}. "
                f"Elige o escribe desde dónde sales.\n\n{texto}"
            ), opciones)
        return self._resp(conv, f"📍 Guardé tu ubicación: la marcaré en el mapa de tu ruta.\n\n{texto}", opciones)

    # --- Incidentes ------------------------------------------------------------

    def _ultimos_incidentes(self, conv: Conversation) -> OutboundMessage:
        _reiniciar(conv)
        recientes = [i for i in self._reports.recientes(horas=None, limite=N_INCIDENTES * 2)
                     if i.estado != IncidentState.rechazado][:N_INCIDENTES]
        if not recientes:
            return self._resp(conv, f"No hay incidentes reportados por ahora 🙌\n\n{PREGUNTA_TRAS_REPORTE}", OPC_MENU)
        ahora = self._now()
        lineas = []
        for k, v in enumerate(self._reports.vistas(recientes), 1):
            de, a = self._places.get(v.de_id), self._places.get(v.a_id)
            tramo = f"{de.nombre if de else v.de_id} ↔ {a.nombre if a else v.a_id}"
            if v.estado == IncidentState.verificado and v.vigente:
                estado = "✅ verificado"
            elif v.vigente and v.estado == IncidentState.activo:
                estado = f"🟠 activo · {round(v.confianza * 100)}% de confianza"
            else:
                estado = "⚪ ya pasó"
            lineas.append(f"{k}. {v.icono} {v.label} · {tramo}\n    {_hace(ahora - v.creado_en)} · {estado}")
        titulo = f"📋 Últimos {len(lineas)} incidentes reportados:" if len(lineas) > 1 else "📋 Último incidente reportado:"
        return self._resp(conv, titulo + "\n\n" + "\n".join(lineas) + f"\n\n{PREGUNTA_TRAS_REPORTE}", OPC_MENU)

    async def _tras_resultado(
        self, conv: Conversation, msg: InboundMessage, n: str, elegida: str | None
    ) -> OutboundMessage:
        if elegida == "nueva" or n in ("otra", "otra ruta", "nueva", "nueva ruta"):
            return self._iniciar_guiada(conv) if conv.modo == "guiada" else self._iniciar_manual(conv)
        if elegida == "alternativas" or "alternativa" in n:
            plan: TripPlan | None = conv.ultimo_plan
            if not plan or not plan.opciones:
                return self._resp(conv, f"No tengo alternativas para mostrar.\n\n{PREGUNTA_RESULTADO}", self._opc_resultado(conv))
            base = "\n\n".join(explicar(o, self._net) for o in plan.opciones)
            return self._resp(conv, f"{base}\n\n{PREGUNTA_RESULTADO}", self._opc_resultado(conv), plan=plan)
        # Una consulta nueva escrita libremente ("de Lucero a Paraíso")
        origen, destino, _ = interpretar(n)
        if origen or destino or (self._places.menciones(n) and not self._es_frase(n)):
            conv.origen_id = conv.destino_id = conv.prioridad = None
            return await self._manual(conv, msg, n)
        if accion := await self._accion_llm(conv, msg, n):
            return accion
        return self._elige_opcion(conv)

    # --- Reportes --------------------------------------------------------------

    async def _reporte(
        self, conv: Conversation, msg: InboundMessage, n: str, it: Interpretation | None = None
    ) -> OutboundMessage:
        tipo = next((k for k, palabras in PALABRAS_TIPO.items() if any(w in n for w in palabras)), None)
        lugares = self._places.menciones(n)
        if not lugares or not tipo:
            it = it or await self._entender(conv, msg)
        if it:
            tipo = tipo or it.tipo_reporte
            if not lugares:
                textos = [*it.lugares, it.origen, it.destino]
                lugares = [r.lugar for t in textos if t and (r := self._places.resolve(t)).estado == "exacto"]
                lugares = list({p.id: p for p in lugares}.values())
        tipo = tipo or "novedad"
        if not lugares:
            if conv.paso in ("inicio", "resultado", "reporte"):  # no hay un viaje en curso: se espera el reporte
                conv.paso = "reporte"
                return self._resp(conv, f"Me falta saber dónde 📍 {INSTRUCCION_REPORTE}", [OPC_CANCELAR])
            texto_pend, opciones_pend = self._pendiente(conv)
            return self._resp(conv, f"{INSTRUCCION_REPORTE}\n\nSigamos: {texto_pend}", opciones_pend)
        recordatorio, opciones_pend = self._tras_reporte(conv)

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

    def _tras_reporte(self, conv: Conversation) -> tuple[str, list[QuickReply]]:
        """Lo que se le ofrece después de reportar: retomar su viaje o, si no había uno, el menú."""
        if conv.paso == "reporte":
            conv.paso = "inicio"
        if conv.paso == "inicio":
            return f"\n\n{PREGUNTA_TRAS_REPORTE}", OPC_MENU
        texto, opciones = self._pendiente(conv)
        return (f"\n\n{texto}" if conv.paso == "resultado" else f"\n\nSigamos: {texto}"), opciones

    # --- LLM -------------------------------------------------------------------

    async def _entender(self, conv: Conversation, msg: InboundMessage) -> Interpretation | None:
        """Lee el mensaje con el LLM. Sin LLM, ante fallas o demoras: None (el flujo sigue con reglas)."""
        if self._interpreter is None:
            return None
        if id(msg) in self._lecturas:  # una sola llamada por mensaje
            return self._lecturas[id(msg)]
        ctx = InterpretContext(
            texto=msg.texto, canal=msg.canal, paso=conv.paso, pendiente=conv.pendiente,
            lugares=[p.nombre for p in self._net.paraderos],
        )
        try:
            it = await asyncio.wait_for(self._interpreter.interpret(ctx), self._timeout)
        except Exception as e:  # noqa: BLE001 — el LLM nunca debe tumbar la respuesta
            log.warning("El intérprete LLM falló (%s); se sigue con las reglas", type(e).__name__,
                        exc_info=log.isEnabledFor(logging.DEBUG))
            it = None
        self._lecturas[id(msg)] = it
        return it

    async def _accion_llm(self, conv: Conversation, msg: InboundMessage, n: str) -> OutboundMessage | None:
        """En una pregunta cerrada solo se atiende texto libre si el LLM lee un viaje o un reporte."""
        it = await self._entender(conv, msg)
        if it and (it.intencion == "reporte" or it.origen or it.destino):
            return await self._con_llm(conv, msg, n)
        return None

    def _es_frase(self, n: str) -> bool:
        """Más que un nombre de lugar: vale la pena que el LLM lea la intención."""
        return self._interpreter is not None and len(n.split()) >= 4

    async def _con_llm(self, conv: Conversation, msg: InboundMessage, n: str) -> OutboundMessage | None:
        """Último recurso cuando las reglas no entienden: actuar según la intención que lea el LLM."""
        it = await self._entender(conv, msg)
        if it is None:
            return None
        if it.intencion == "reporte":
            return await self._reporte(conv, msg, n, it)
        if it.origen or it.destino:
            if conv.paso in ("inicio", "resultado"):  # consulta nueva
                conv.origen_id = conv.destino_id = conv.prioridad = conv.pendiente = None
            return await self._manual(conv, msg, n, it)
        if it.respuesta:
            pregunta, opciones = self._pendiente(conv)
            return self._resp(conv, f"{it.respuesta.strip()}\n\n{pregunta}", opciones)
        return None

    async def _pulir(self, mensaje: str, base: str, hechos: dict, canal: str) -> str:
        """Pule con el LLM. Ante cualquier falla, o si cambia alguna cifra, se queda el texto del dominio."""
        try:
            ctx = RefineContext(mensaje_usuario=mensaje, texto_base=base, hechos=hechos, canal=canal)
            out = (await asyncio.wait_for(self._refiner.refine(ctx), self._timeout) or "").strip()
        except Exception as e:  # noqa: BLE001 — el LLM nunca debe tumbar la respuesta
            log.warning("El refinador de respuestas falló (%s); se usa el texto base", type(e).__name__,
                        exc_info=log.isEnabledFor(logging.DEBUG))
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
        mapa: MapaRuta | None = None,
    ) -> OutboundMessage:
        conv.opciones = list(opciones or [])
        return OutboundMessage(
            texto=texto or texto_base,
            texto_base=texto_base,
            opciones_rapidas=opciones or [],
            paso=conv.paso,
            modo=conv.modo,
            plan=plan,
            reporte=reporte,
            mapa=mapa,
        )
