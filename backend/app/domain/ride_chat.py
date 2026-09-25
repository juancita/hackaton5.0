"""Viajes por chat (Telegram hoy; WhatsApp mañana, mismo código).

Pensado para conductores informales y personas mayores: botones grandes, frases cortas y
comandos en lenguaje natural. Corre ANTES del asistente de rutas: si el mensaje no es de
viajes, devuelve None y el asistente responde como siempre.

Ejemplos:
  Conductor: "soy conductor" · "salgo 6:30 de El Ensueño a Potosí con 10 cupos" · "ya salí"
             (y comparte ubicación) · "lleno" · "llego hasta Sierra Morena" · "desvío por la 68" · "terminé"
  Pasajero:  "soy pasajero" · "ver viajes" · "colectivo a Potosí" · "apartar 1" · "apartar 1 bajo en Sierra Morena"
  Casa:      "🏡 Mi casa" → comparte ubicación → luego "de Meissen a mi casa"
  Identidad: botón "📱 Compartir mi número" → la misma persona en Telegram y en la app.

Avisos push: cuando alguien aparta cupo se avisa al conductor; cuando el conductor sale, corta,
se desvía o termina, se avisa a sus pasajeros (en Telegram). Los chat_id viven solo en memoria.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable

from app.domain.drivers import DriverService, Trip
from app.domain.errors import DomainError
from app.domain.models import Actor, OutboundMessage, Place, QuickReply
from app.domain.places import PlaceService
from app.domain.reports import ReportService, reporter_id_para, reporter_id_por_telefono
from app.domain.text import normalize

HORA = re.compile(
    r"(?:a las |a la |sobre las |tipo )?\b(\d{1,2})(?:[:.h](\d{2}))?\s*"
    r"(am|pm|a\.m\.|p\.m\.|de la manana|de la mañana|de la tarde|de la noche)?"
)
CUPOS = re.compile(r"(\d{1,2})\s*(?:cupos?|puestos?|pasajeros?|personas?)")
APARTAR = re.compile(r"\b(?:apartar|aparta|apartame|reservar|reserva|cupo)\s*(?:en\s*(?:el\s*)?)?(\d{1,2})\b")
BAJA = re.compile(r"\b(?:bajo en|me bajo en|me quedo en|hasta)\b(.+)$")
CORTE = re.compile(r"\b(?:corto en|corto el viaje en|llego hasta|llego solo hasta|voy solo hasta|voy hasta)\b(.+)$")
VIAJES = re.compile(r"\b(jeeps?|colectivos?|veredal(?:es)?|a que hora sale)\b")
CASA = re.compile(r"\b(?:mi casa|la casa|mi hogar)\b")
PARADERO = re.compile(r"\bmi paradero\b")

BTN_CONDUCTOR = QuickReply(id="soy_conductor", label="🚙 Soy conductor")
BTN_PASAJERO = QuickReply(id="soy_pasajero", label="🧍 Soy pasajero")
BTN_TEL = QuickReply(id="telefono", label="📱 Compartir mi número")
BTN_VER = QuickReply(id="ver_viajes", label="🕒 Ver viajes")
BTN_PUBLICAR = QuickReply(id="publicar", label="📣 Publicar viaje")
BTN_SALI = QuickReply(id="ya_sali", label="✅ Ya salí")
BTN_LLENO = QuickReply(id="lleno", label="🚫 Lleno")
BTN_CORTAR = QuickReply(id="cortar", label="✂️ Cortar viaje")
BTN_DESVIO = QuickReply(id="desvio", label="↪️ Desvío")
BTN_FIN = QuickReply(id="termine", label="🏁 Terminé")
BTN_UBIC = QuickReply(id="ubicacion", label="📍 Enviar mi ubicación")
BTN_MENU = QuickReply(id="menu", label="🏠 Menú principal")
BTN_CASA = QuickReply(id="mi_casa", label="🏡 Mi casa")
BTN_IR_CASA = QuickReply(id="ir_casa", label="🏡 Ir a mi casa")
BTN_CAMBIAR_CASA = QuickReply(id="cambiar_casa", label="📍 Cambiar mi casa")
# Cambio de rol (botones grandes y explícitos: pensado para personas mayores)
BTN_A_PASAJERO = QuickReply(id="soy_pasajero", label="🔄 Cambiar a pasajero")
BTN_A_CONDUCTOR = QuickReply(id="soy_conductor", label="🔄 Cambiar a conductor")
BTN_FIN_Y_PASAJERO = QuickReply(id="terminar_y_pasajero", label="🏁 Terminar viaje y ser pasajero")
BTN_SEGUIR_CONDUCTOR = QuickReply(id="seguir_conductor", label="🚙 Seguir como conductor")

A_CONDUCTOR = {"soy conductor", "conductor", "modo conductor", "cambiar a conductor", "ser conductor",
               "pasarme a conductor", "volver a conductor"}
A_PASAJERO = {"soy pasajero", "pasajero", "modo pasajero", "cambiar a pasajero", "ser pasajero", "pasarme a pasajero",
              "volver a pasajero", "salir de conductor", "salir del modo conductor", "ya no soy conductor",
              "dejar de ser conductor", "no soy conductor"}
MI_ROL = {"mi rol", "que soy", "quien soy", "cambiar rol", "cambiar de rol", "cambiar modo", "cambiar de modo",
          "mi perfil", "perfil", "mi modo"}


def _pasajeros(n: int) -> str:
    return f"{n} pasajero" if n == 1 else f"{n} pasajeros"


def _hora(texto: str) -> tuple[str | None, str]:
    """Extrae la hora ("6:30", "6 pm", "18h") → ("HH:MM", texto_sin_la_hora)."""
    t = texto.lower()
    for m in HORA.finditer(t):
        h, mm, sufijo = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "")
        resto = t[m.end():m.end() + 10]
        if re.match(r"\s*(cupos?|puestos?|pasajeros?|personas?)", resto):
            continue  # es el número de cupos, no la hora
        if not m.group(2) and not sufijo and "salgo" not in t[:m.start()] and "sale" not in t[:m.start()]:
            continue
        if sufijo in ("pm", "p.m.", "de la tarde", "de la noche") and h < 12:
            h += 12
        if sufijo in ("am", "a.m.") and h == 12:
            h = 0
        if 0 <= h <= 23 and 0 <= mm <= 59:
            return f"{h:02d}:{mm:02d}", (t[:m.start()] + " " + t[m.end():])
    return None, t


def _dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    k = 111_320.0
    return math.hypot((a[0] - b[0]) * k, (a[1] - b[1]) * k * math.cos(math.radians(a[0])))


class RideChat:
    def __init__(self, drivers: DriverService, reports: ReportService, places: PlaceService, salt: str,
                 nombre_lugar: Callable[[str], str]):
        self._d = drivers
        self._r = reports
        self._p = places
        self._net = drivers.network
        self._salt = salt
        self._nom = nombre_lugar
        self._ultimos: dict[str, list[str]] = {}         # últimos viajes mostrados a cada usuario ("apartar 2")
        self._chats: dict[str, str] = {}                 # reporter_id -> chat de Telegram (solo en memoria)
        self._esperando_ubicacion: dict[str, str] = {}   # reporter_id -> "casa" | "paradero"
        self._avisos: list[tuple[str, str]] = []

    # --- Identidad ---
    def identidad(self, canal: str, user_id: str) -> tuple[str, str]:
        """(canal_key, reporter_id). En la web 'tel:<num>' ya es identidad por teléfono; en Telegram
        se usa el número vinculado si la persona lo compartió."""
        if canal == "web" and user_id.startswith("tel:"):
            rid = reporter_id_por_telefono(user_id[4:], self._salt)
            return rid, rid
        canal_key = reporter_id_para(canal, user_id, self._salt)
        return canal_key, (self._d.vinculo(canal_key) or canal_key)

    @staticmethod
    def _actor(canal: str, reporter_id: str) -> Actor:
        return Actor(reporter_id=reporter_id, canal=canal)

    @staticmethod
    def _msg(texto: str, opciones: list[QuickReply] | None = None) -> OutboundMessage:
        return OutboundMessage(texto=texto, texto_base=texto, paso="viajes", modo="viajes",
                               opciones_rapidas=opciones or [])

    @staticmethod
    def _botones_conductor() -> list[QuickReply]:
        return [BTN_PUBLICAR, BTN_SALI, BTN_LLENO, BTN_CORTAR, BTN_DESVIO, BTN_FIN, BTN_UBIC, BTN_A_PASAJERO, BTN_MENU]

    @staticmethod
    def _botones_pasajero(canal: str) -> list[QuickReply]:
        return [BTN_VER, BTN_CASA, BTN_A_CONDUCTOR, BTN_MENU] + ([BTN_TEL] if canal == "telegram" else [])

    def ajustar_menu(self, canal: str, user_id: str, out: OutboundMessage) -> OutboundMessage:
        """El menú principal del asistente ofrece el cambio al rol CONTRARIO al que la persona tiene."""
        if not any(o.id == "soy_conductor" for o in out.opciones_rapidas):
            return out
        try:
            conductor = self._r.perfil(self._actor(canal, self.identidad(canal, user_id)[1])).modo == "conductor"
        except Exception:  # noqa: BLE001 — el menú nunca se rompe por esto
            return out
        cambio = BTN_A_PASAJERO if conductor else BTN_A_CONDUCTOR
        opciones = [cambio if o.id == "soy_conductor" else o for o in out.opciones_rapidas]
        return out.model_copy(update={"opciones_rapidas": opciones})

    # --- Textos compartidos con la API web ---
    def _recorrido(self, t: Trip) -> str:
        return " → ".join(self._nom(p) for p in (t.paradas or [t.origen_id, t.destino_id]))

    def texto_salida(self, t: Trip) -> str:
        lleno = " (va lleno)" if t.lleno else ""
        return f"🚙 {t.driver_nombre or 'Tu conductor'} ya salió{lleno}: {t.ruta}, {self._recorrido(t)}."

    def texto_corte(self, t: Trip) -> str:
        return (f"✂️ Aviso: el viaje de las {t.hora} ({t.ruta}) llega solo hasta {self._nom(t.corta_en)}. "
                "Si ibas más allá, busca otra opción en «Ver viajes».")

    def texto_reserva(self, t: Trip, nombre: str, baja_en: str | None) -> str:
        donde = f" (se baja en {self._nom(baja_en)})" if baja_en and baja_en != t.destino_id else ""
        return f"🧍 {nombre} apartó cupo en tu viaje de las {t.hora}{donde}. Ya son {_pasajeros(t.esperando)} esperando."

    # --- Avisos push ---
    def avisos_pasajeros(self, t: Trip, texto: str) -> list[tuple[str, str]]:
        ids = {s.passenger_id for s in self._d.pasajeros(t.id)}
        return [(self._chats[i], texto) for i in ids if i in self._chats]

    def aviso_conductor(self, t: Trip, texto: str) -> list[tuple[str, str]]:
        return [(self._chats[t.driver_id], texto)] if t.driver_id in self._chats else []

    def tomar_avisos(self) -> list[tuple[str, str]]:
        avisos, self._avisos = self._avisos, []
        return avisos

    # --- Lugares guardados ---
    def _paradero_cercano(self, lat: float, lng: float) -> Place:
        return min(self._net.paraderos, key=lambda p: _dist_m((lat, lng), (p.lat, p.lng)))

    def _lugar_guardado(self, rid: str, etiqueta: str):
        return next((l for l in self._d.lugares(rid) if l.etiqueta == etiqueta), None)

    def reescribir(self, canal: str, user_id: str, texto: str) -> str:
        """Cambia "mi casa" / "mi paradero" por el paradero guardado para que el asistente arme la ruta."""
        if not texto:
            return texto
        _, rid = self.identidad(canal, user_id)
        n = normalize(texto)
        out = texto
        if CASA.search(n) and (l := self._lugar_guardado(rid, "casa")) and l.place_id:
            out = re.sub(r"(?i)\b(mi casa|la casa|mi hogar)\b", self._nom(l.place_id), out)
        if PARADERO.search(n) and (l := self._lugar_guardado(rid, "paradero")) and l.place_id:
            out = re.sub(r"(?i)\bmi paradero\b", self._nom(l.place_id), out)
        return out

    def _linea_viaje(self, i: int, t: Trip) -> str:
        estado = "🚙 en ruta" if t.estado == "en_ruta" else ("🚫 lleno" if t.lleno or t.cupos_libres <= 0 else f"🟢 {t.cupos_libres} cupos")
        extra = f"\n   ✂️ Llega solo hasta {self._nom(t.corta_en)}" if t.corta_en else ""
        extra += f"\n   ↪️ {t.desvio}" if t.desvio else ""
        return f"{i}. {t.hora} · {t.ruta}\n   {self._recorrido(t)} · {estado} · {t.esperando} esperando{extra}"

    # --- Punto de entrada ---
    def handle(self, canal: str, user_id: str, texto: str, nombre: str | None = None,
               ubicacion: tuple[float, float] | None = None, telefono: str | None = None) -> OutboundMessage | None:
        canal_key, rid = self.identidad(canal, user_id)
        if canal == "telegram":
            self._chats[rid] = user_id
        actor = self._actor(canal, rid)
        n = normalize(texto)

        try:
            # 1) Compartió su número (Telegram): vincula la identidad con el teléfono
            if telefono:
                rid_tel = reporter_id_por_telefono(telefono, self._salt)
                self._d.vincular(canal_key, rid_tel)
                self._chats[rid_tel] = user_id
                self._r.registrar_perfil(self._actor(canal, rid_tel), nombre, None)
                return self._msg(
                    "📱 ¡Listo! Tu número quedó vinculado. Ahora eres la misma persona aquí y en la app "
                    "(tus viajes, cupos, tu casa y tus reportes te siguen).\n\n¿Cómo vas a usar Muévete CB?",
                    [BTN_PASAJERO, BTN_CONDUCTOR])

            perfil = self._r.perfil(actor)
            conductor = perfil.modo == "conductor"

            # 2) Guardar casa/paradero con la ubicación que acaba de compartir
            if ubicacion and rid in self._esperando_ubicacion:
                etiqueta = self._esperando_ubicacion.pop(rid)
                p = self._paradero_cercano(*ubicacion)
                nombre_lugar = "Mi casa" if etiqueta == "casa" else "Mi paradero"
                self._d.guardar_lugar(rid, etiqueta, f"{nombre_lugar} (cerca de {p.nombre})", ubicacion[0], ubicacion[1], p.id)
                return self._msg(
                    f"🏡 ¡Guardado! {nombre_lugar} queda cerca de {p.nombre}.\n\n"
                    "Ahora puedes escribir, por ejemplo: «de Meissen a mi casa» o «de mi casa a Portal Tunal».",
                    [BTN_MENU])

            # 3) Bienvenida con elección clara de rol (Telegram envía /start la primera vez)
            if canal == "telegram" and n in ("start", "iniciar", "empezar viajes"):
                if nombre and not perfil.nombre:
                    self._r.registrar_perfil(actor, nombre, None)
                return self._msg(
                    f"¡Hola{', ' + nombre if nombre else ''}! 👋 Soy Muévete CB.\n\n"
                    "¿Cómo vas a usar el servicio? Toca una opción 👇\n"
                    "• 🧍 Pasajero: ves a qué hora salen los jeeps y colectivos y apartas tu cupo.\n"
                    "• 🚙 Conductor: avisas a qué hora sales y sabes cuántos pasajeros te esperan.\n"
                    "• 🏡 Mi casa: la guardas una vez y pides rutas con «a mi casa».",
                    [BTN_PASAJERO, BTN_CONDUCTOR, BTN_CASA, BTN_TEL])

            # 4) Mi casa / mi paradero
            if n in ("mi casa", "casa", "guardar mi casa", "cambiar mi casa", "mi paradero", "guardar mi paradero",
                     "ir a mi casa", "ir a casa"):
                etiqueta = "paradero" if "paradero" in n else "casa"
                guardado = self._lugar_guardado(rid, etiqueta)
                if guardado and not n.startswith("cambiar"):
                    return self._msg(f"🏡 {guardado.nombre}.\n¿Desde dónde sales? Escríbeme, por ejemplo: "
                                     "«de Meissen a mi casa».", [BTN_CAMBIAR_CASA, BTN_MENU])
                self._esperando_ubicacion[rid] = etiqueta
                cual = "tu casa" if etiqueta == "casa" else "tu paradero de siempre"
                return self._msg(f"📍 Cuando estés en {cual}, toca «Enviar mi ubicación» y la guardo.",
                                 [BTN_UBIC, BTN_MENU])

            # 5) Elegir / cambiar de rol (conductor ⇄ pasajero)
            if n in MI_ROL:
                if conductor:
                    return self._msg("🚙 Ahora estás como CONDUCTOR.\n¿Quieres pasarte a pasajero? Toca el botón 👇",
                                     [BTN_A_PASAJERO, BTN_SEGUIR_CONDUCTOR, BTN_MENU])
                return self._msg("🧍 Ahora estás como PASAJERO.\n¿Quieres pasarte a conductor? Toca el botón 👇",
                                 [BTN_A_CONDUCTOR, BTN_VER, BTN_MENU])
            if n in A_CONDUCTOR:
                ya = conductor
                self._r.registrar_perfil(actor, nombre if not perfil.nombre else None, "conductor")
                return self._msg(
                    ("🚙 Ya estás como CONDUCTOR." if ya else "🚙 Listo, ahora estás como CONDUCTOR.")
                    + "\n\nPara publicar un viaje escríbeme así:\n"
                    "👉 salgo 6:30 de El Ensueño a Potosí con 10 cupos\n\n"
                    "Luego usa los botones: ✅ Ya salí (comparte ubicación), 🚫 Lleno, ✂️ Cortar viaje, ↪️ Desvío, 🏁 Terminé.\n"
                    "Para volver a pasajero toca 🔄 Cambiar a pasajero.",
                    self._botones_conductor())
            if n == "seguir como conductor":
                return self._msg("🚙 Sigues como CONDUCTOR. Tu viaje sigue publicado.", self._botones_conductor())
            if n in A_PASAJERO or n == "terminar viaje y ser pasajero":
                activo = self._d.viaje_activo(rid) if conductor else None
                if activo and n != "terminar viaje y ser pasajero":
                    # No se deja un viaje colgado: los pasajeros que apartaron cupo lo están esperando
                    esperan = (f" y {_pasajeros(activo.esperando)} te "
                               f"{'espera' if activo.esperando == 1 else 'esperan'}") if activo.esperando else ""
                    return self._msg(
                        f"⚠️ Tienes un viaje publicado: {activo.ruta} a las {activo.hora}{esperan}.\n\n"
                        "¿Lo terminas y te pasas a pasajero? Si tocas 🏁, les aviso a tus pasajeros.",
                        [BTN_FIN_Y_PASAJERO, BTN_SEGUIR_CONDUCTOR])
                aviso = ""
                if activo:
                    t = self._d.finalizar(activo.id, rid)
                    self._avisos += self.avisos_pasajeros(
                        t, f"🏁 El viaje de las {t.hora} ({t.ruta}) terminó. Busca otro en 🕒 Ver viajes.")
                    aviso = f"🏁 Terminé tu viaje de las {t.hora} y avisé a tus pasajeros.\n"
                self._r.registrar_perfil(actor, nombre if not perfil.nombre else None, "pasajero")
                return self._msg(
                    aviso + ("🧍 Ya estás como PASAJERO." if not conductor else "🧍 Listo, ahora estás como PASAJERO.")
                    + "\n\nToca 🕒 Ver viajes para ver los jeeps y colectivos que salen, "
                    "o escríbeme por ejemplo: colectivo a Potosí.\nPara volver a conductor toca 🔄 Cambiar a conductor.",
                    self._botones_pasajero(canal))

            # 6) Pasajero: ver próximos viajes (opcionalmente hacia/desde un barrio)
            if (n in ("ver viajes", "viajes", "que viajes hay", "horarios", "viajes de jeeps")
                    or (VIAJES.search(n) and not conductor and not APARTAR.search(n))):
                lugares = self._p.menciones(texto)
                barrio = lugares[-1].id if lugares else None
                viajes = [t for t in self._d.proximos(None, 30)
                          if barrio is None or barrio in (t.paradas or [t.origen_id, t.destino_id])][:8]
                if not viajes and barrio:
                    viajes = self._d.proximos(None, 8)
                if not viajes:
                    tend = self._d.horarios_tipicos()
                    extra = ("\n\nHorarios típicos:\n" + "\n".join(f"• {r}: {', '.join(h)}" for r, h in list(tend.items())[:5])) if tend else ""
                    return self._msg("Ahora no hay viajes publicados. 🙏" + extra, self._botones_pasajero(canal))
                self._ultimos[rid] = [t.id for t in viajes]
                lineas = "\n".join(self._linea_viaje(i, t) for i, t in enumerate(viajes, 1))
                apartar = [QuickReply(id=f"apartar_{i}", label=f"Apartar {i}")
                           for i, t in enumerate(viajes[:4], 1) if not (t.lleno or t.cupos_libres <= 0)]
                return self._msg(f"🕒 Próximos viajes:\n\n{lineas}\n\nToca «Apartar» con el número del viaje. "
                                 "Si te bajas antes, escribe por ejemplo: apartar 1 bajo en Sierra Morena.",
                                 apartar + [BTN_MENU])

            # 7) Pasajero: apartar cupo (opcional: dónde se baja)
            m = APARTAR.search(n)
            if m:
                idx = int(m.group(1)) - 1
                ids = self._ultimos.get(rid) or [t.id for t in self._d.proximos(None, 8)]
                if not (0 <= idx < len(ids)):
                    return self._msg("No encontré ese número de viaje. Toca 🕒 Ver viajes.", [BTN_VER])
                baja = BAJA.search(n)
                lugares_baja = self._p.menciones(baja.group(1)) if baja else []
                baja_en = lugares_baja[0].id if lugares_baja else None
                nombre_p = perfil.nombre or nombre or "Pasajero"
                t = self._d.reservar(ids[idx], rid, nombre_p, baja_en)
                self._avisos += self.aviso_conductor(t, self.texto_reserva(t, nombre_p, baja_en))
                donde = f", te bajas en {self._nom(baja_en)}" if baja_en and baja_en != t.destino_id else ""
                return self._msg(
                    f"✅ ¡Cupo apartado{donde}! {t.ruta} sale a las {t.hora} de {self._nom(t.origen_id)}.\n"
                    f"Recorrido: {self._recorrido(t)}\n"
                    f"El conductor ya sabe que vas ({t.esperando} esperando, quedan {t.cupos_libres} cupos). "
                    "Te aviso aquí cuando salga.",
                    [BTN_VER, BTN_MENU])

            # 8) Conductor: publicar viaje en lenguaje natural
            if n in ("publicar viaje", "publicar"):
                return self._msg("Escríbeme así 👇\nsalgo 6:30 de El Ensueño a Potosí con 10 cupos",
                                 self._botones_conductor())
            if (conductor or "cupo" in n) and re.search(r"\b(salgo|sale|saldre|voy a salir)\b", n):
                hora, sin_hora = _hora(texto)
                cupos_m = CUPOS.search(sin_hora)
                cupos = int(cupos_m.group(1)) if cupos_m else 4
                sin_cupos = CUPOS.sub(" ", sin_hora)
                partes = re.split(r"\b(?:pasando por|por)\b", sin_cupos, maxsplit=1)
                lugares = self._p.menciones(partes[0])
                vias = [p.id for p in self._p.menciones(partes[1])] if len(partes) > 1 else []
                if not hora or len(lugares) < 2:
                    return self._msg("No te entendí del todo 🙏 Escríbeme así:\nsalgo 6:30 de El Ensueño a Potosí con 10 cupos",
                                     self._botones_conductor())
                if not conductor:
                    self._r.registrar_perfil(actor, None, "conductor")
                prof = self._d.perfil(rid)
                ruta = prof.ruta if prof and prof.ruta else None
                if not ruta:  # nombre de la ruta informal de la red si arranca en uno de sus paraderos
                    tramo = next((t for t in self._net.tramos
                                  if not self._net.modos[t.modo].formal and lugares[0].id in (t.de, t.a)), None)
                    ruta = tramo.ruta if tramo else f"Ruta {lugares[0].nombre} – {lugares[-1].nombre}"
                    self._d.registrar_conductor(rid, ruta, lugares[0].id)
                t = self._d.anunciar(rid, perfil.nombre or nombre or "Conductor", lugares[0].id, lugares[-1].id,
                                     hora, cupos, ruta, vias or None)
                return self._msg(
                    f"📣 ¡Viaje publicado!\n{t.ruta}\n{self._recorrido(t)}\n🕒 {t.hora} · {t.cupos_total} cupos\n\n"
                    "Te aviso aquí cada vez que alguien aparte cupo. Cuando arranques, toca ✅ Ya salí.",
                    self._botones_conductor())

            # 9) Conductor: acciones sobre su viaje activo
            if conductor:
                activo = self._d.viaje_activo(rid)
                sin_viaje = self._msg("No tienes un viaje publicado. Escríbeme: salgo 6:30 de El Ensueño a Potosí con 10 cupos",
                                      self._botones_conductor())
                if n in ("ya sali", "sali", "arranque", "ya arranque", "en camino"):
                    if not activo:
                        return sin_viaje
                    lat, lng = ubicacion if ubicacion else (None, None)
                    t = self._d.salir(activo.id, rid, lat, lng)
                    self._avisos += self.avisos_pasajeros(t, self.texto_salida(t))
                    extra = "" if ubicacion else "\n📍 Toca «Enviar mi ubicación» para que te vean en el mapa."
                    lleno = " ¡Y sales LLENO! 🚫" if t.lleno else ""
                    return self._msg(f"🚙 ¡En ruta!{lleno} Avisé a {_pasajeros(t.esperando)} que te esperan.{extra}",
                                     self._botones_conductor())
                if ubicacion and activo and not texto.strip():
                    self._d.salir(activo.id, rid, ubicacion[0], ubicacion[1])
                    return self._msg("📍 Ubicación actualizada: tus pasajeros ven que ya te moviste.",
                                     self._botones_conductor())
                if n in ("lleno", "voy lleno", "sali lleno") and activo:
                    self._d.marcar_lleno(activo.id, rid)
                    return self._msg("🚫 Marcado como LLENO. Ya no se aparta más cupo.", self._botones_conductor())
                if n in ("cortar viaje", "cortar", "hasta aqui llego") or CORTE.search(n):
                    if not activo:
                        return sin_viaje
                    intermedias = (activo.paradas or [])[1:-1]
                    mc = CORTE.search(n)
                    lugares_corte = self._p.menciones(mc.group(1)) if mc else []
                    parada = lugares_corte[0].id if lugares_corte else None
                    if not parada:
                        if not intermedias:
                            return self._msg("Este viaje no tiene paradas intermedias para cortar.", self._botones_conductor())
                        return self._msg("✂️ ¿Hasta dónde llegas? Toca la parada:",
                                         [QuickReply(id=f"corte_{p}", label=f"✂️ Llego hasta {self._nom(p)}")
                                          for p in intermedias] + [BTN_MENU])
                    t, afectados = self._d.cortar(activo.id, rid, parada)
                    self._avisos += self.avisos_pasajeros(t, self.texto_corte(t))
                    return self._msg(f"✂️ Listo: tu viaje llega hasta {self._nom(parada)}. "
                                     f"Avisé a {_pasajeros(afectados)} que {'iba' if afectados == 1 else 'iban'} más allá.", self._botones_conductor())
                if n.startswith("desvio") and activo:
                    nota = texto.split(" ", 1)[1] if " " in texto.strip() else ""
                    if not nota or normalize(nota) == "desvio":
                        return self._msg("↪️ Cuéntame el desvío, por ejemplo:\ndesvío por la 68 porque hay protesta en la Distrital",
                                         self._botones_conductor())
                    t = self._d.desvio(activo.id, rid, nota)
                    self._avisos += self.avisos_pasajeros(t, f"↪️ Tu viaje de las {t.hora} ({t.ruta}) va por desvío: {t.desvio}")
                    try:
                        if self._net.tramo_entre(t.origen_id, t.destino_id):
                            self._r.reportar(actor, "novedad", t.origen_id, t.destino_id, None, f"Desvío de {t.ruta}: {t.desvio}")
                    except DomainError:
                        pass
                    return self._msg(f"↪️ Desvío avisado a tus pasajeros: {t.desvio}", self._botones_conductor())
                if n in ("termine", "terminado", "finalizar", "fin") and activo:
                    t = self._d.finalizar(activo.id, rid)
                    self._avisos += self.avisos_pasajeros(t, f"🏁 El viaje de las {t.hora} ({t.ruta}) terminó. ¡Gracias por viajar!")
                    return self._msg("🏁 Viaje terminado. ¡Gracias por mover a Ciudad Bolívar! 🙌",
                                     self._botones_conductor())
                if n in ("cuantos esperan", "pasajeros", "quien va") and activo:
                    t = next((x for x in self._d.mis_viajes(rid, 20) if x.id == activo.id), activo)
                    bajan = [s for s in self._d.pasajeros(t.id) if s.baja_en]
                    extra = ("\n" + "\n".join(f"• {s.passenger_nombre} se baja en {self._nom(s.baja_en)}" for s in bajan)) if bajan else ""
                    return self._msg(f"🧍 {_pasajeros(t.esperando)} esperando tu viaje de las {t.hora}.{extra}",
                                     self._botones_conductor())
        except DomainError as e:
            return self._msg(f"🙏 {e}")

        return None  # no es de viajes: responde el asistente de rutas
