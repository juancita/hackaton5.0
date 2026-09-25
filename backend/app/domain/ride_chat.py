"""Viajes por chat (Telegram hoy; WhatsApp mañana, mismo código).

Pensado para conductores informales y personas mayores: botones grandes, frases cortas y
comandos en lenguaje natural. Corre ANTES del asistente de rutas: si el mensaje no es de
viajes, devuelve None y el asistente responde como siempre.

Ejemplos:
  Conductor: "soy conductor" · "salgo 6:30 de Mirador a Paraíso con 8 cupos" · "ya salí"
             (y comparte ubicación) · "lleno" · "desvío por la 68 porque hay protesta" · "terminé"
  Pasajero:  "soy pasajero" · "ver viajes" · "jeep a Paraíso" · "apartar 1"
  Identidad: botón "📱 Compartir mi número" → la misma persona en Telegram y en la app.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from app.domain.drivers import DriverService, Trip
from app.domain.errors import DomainError
from app.domain.models import OutboundMessage, QuickReply
from app.domain.places import PlaceService
from app.domain.reports import ReportService, reporter_id_para, reporter_id_por_telefono
from app.domain.text import normalize

HORA = re.compile(
    r"(?:a las |a la |sobre las |tipo )?\b(\d{1,2})(?:[:.h](\d{2}))?\s*"
    r"(am|pm|a\.m\.|p\.m\.|de la manana|de la mañana|de la tarde|de la noche)?"
)
CUPOS = re.compile(r"(\d{1,2})\s*(?:cupos?|puestos?|pasajeros?|personas?)")
APARTAR = re.compile(r"\b(?:apartar|aparta|apartame|reservar|reserva|cupo)\s*(?:en\s*(?:el\s*)?)?(\d{1,2})\b")

BTN_CONDUCTOR = QuickReply(id="soy_conductor", label="🚙 Soy conductor")
BTN_PASAJERO = QuickReply(id="soy_pasajero", label="🧍 Soy pasajero")
BTN_TEL = QuickReply(id="telefono", label="📱 Compartir mi número")
BTN_VER = QuickReply(id="ver_viajes", label="🕒 Ver viajes")
BTN_PUBLICAR = QuickReply(id="publicar", label="📣 Publicar viaje")
BTN_SALI = QuickReply(id="ya_sali", label="✅ Ya salí")
BTN_LLENO = QuickReply(id="lleno", label="🚫 Lleno")
BTN_DESVIO = QuickReply(id="desvio", label="↪️ Desvío")
BTN_FIN = QuickReply(id="termine", label="🏁 Terminé")
BTN_UBIC = QuickReply(id="ubicacion", label="📍 Enviar mi ubicación")
BTN_MENU = QuickReply(id="menu", label="🏠 Menú principal")


def _pasajeros(n: int) -> str:
    return f"{n} pasajero" if n == 1 else f"{n} pasajeros"


def _hora(texto: str) -> tuple[str | None, str]:
    """Extrae la hora ("6:30", "6 pm", "18h") → ("HH:MM", texto_sin_la_hora)."""
    t = texto.lower()
    for m in HORA.finditer(t):
        h, mm, sufijo = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "")
        # descarta números que son cupos ("8 cupos")
        resto = t[m.end():m.end() + 10]
        if re.match(r"\s*(cupos?|puestos?|pasajeros?|personas?)", resto):
            continue
        if not m.group(2) and not sufijo and "salgo" not in t[:m.start()] and "sale" not in t[:m.start()]:
            continue
        if sufijo in ("pm", "p.m.", "de la tarde", "de la noche") and h < 12:
            h += 12
        if sufijo in ("am", "a.m.") and h == 12:
            h = 0
        if 0 <= h <= 23 and 0 <= mm <= 59:
            return f"{h:02d}:{mm:02d}", (t[:m.start()] + " " + t[m.end():])
    return None, t


class RideChat:
    def __init__(self, drivers: DriverService, reports: ReportService, places: PlaceService, salt: str,
                 nombre_lugar: Callable[[str], str]):
        self._d = drivers
        self._r = reports
        self._p = places
        self._salt = salt
        self._nom = nombre_lugar
        self._ultimos: dict[str, list[str]] = {}  # últimos viajes mostrados a cada usuario (para "apartar 2")

    # --- Identidad ---
    def identidad(self, canal: str, user_id: str) -> tuple[str, str]:
        """(canal_key, reporter_id). En la web 'tel:<num>' ya es identidad por teléfono; en Telegram
        se usa el número vinculado si la persona lo compartió."""
        if canal == "web" and user_id.startswith("tel:"):
            rid = reporter_id_por_telefono(user_id[4:], self._salt)
            return rid, rid
        canal_key = reporter_id_para(canal, user_id, self._salt)
        return canal_key, (self._d.vinculo(canal_key) or canal_key)

    def _actor(self, canal: str, reporter_id: str):
        from app.domain.models import Actor
        return Actor(reporter_id=reporter_id, canal=canal)

    def _msg(self, texto: str, opciones: list[QuickReply] | None = None) -> OutboundMessage:
        return OutboundMessage(texto=texto, texto_base=texto, paso="viajes", modo="viajes",
                               opciones_rapidas=opciones or [])

    def _botones_conductor(self, canal: str) -> list[QuickReply]:
        return [BTN_PUBLICAR, BTN_SALI, BTN_LLENO, BTN_DESVIO, BTN_FIN, BTN_UBIC, BTN_PASAJERO]

    def _botones_pasajero(self, canal: str) -> list[QuickReply]:
        return [BTN_VER, BTN_MENU, BTN_CONDUCTOR] + ([BTN_TEL] if canal == "telegram" else [])

    def _linea_viaje(self, i: int, t: Trip) -> str:
        estado = "🚙 en ruta" if t.estado == "en_ruta" else ("🚫 lleno" if t.lleno or t.cupos_libres <= 0 else f"🟢 {t.cupos_libres} cupos")
        desvio = f"\n   ↪️ {t.desvio}" if t.desvio else ""
        return (f"{i}. {t.hora} · {t.ruta}\n   {self._nom(t.origen_id)} → {self._nom(t.destino_id)} · {estado}"
                f" · {t.esperando} esperando{desvio}")

    # --- Punto de entrada ---
    def handle(self, canal: str, user_id: str, texto: str, nombre: str | None = None,
               ubicacion: tuple[float, float] | None = None, telefono: str | None = None) -> OutboundMessage | None:
        canal_key, rid = self.identidad(canal, user_id)
        actor = self._actor(canal, rid)
        n = normalize(texto)

        try:
            # 1) Compartió su número (Telegram): vincula la identidad con el teléfono
            if telefono:
                rid_tel = reporter_id_por_telefono(telefono, self._salt)
                self._d.vincular(canal_key, rid_tel)
                self._r.registrar_perfil(self._actor(canal, rid_tel), nombre, None)
                return self._msg(
                    "📱 ¡Listo! Tu número quedó vinculado. Ahora eres la misma persona aquí y en la app "
                    "(tus viajes, cupos y reportes te siguen).\n\n¿Cómo vas a usar Muévete CB?",
                    [BTN_PASAJERO, BTN_CONDUCTOR])

            perfil = self._r.perfil(actor)
            conductor = perfil.modo == "conductor"

            # 2) Bienvenida con elección clara de rol (primera vez o /start)
            # (Telegram envía /start la primera vez que alguien abre el bot; "hola" sigue al asistente)
            if canal == "telegram" and n in ("start", "iniciar", "empezar viajes"):
                if nombre and not perfil.nombre:
                    self._r.registrar_perfil(actor, nombre, None)
                return self._msg(
                    f"¡Hola{', ' + nombre if nombre else ''}! 👋 Soy Muévete CB.\n\n"
                    "¿Cómo vas a usar el servicio? Toca una opción 👇\n"
                    "• 🧍 Pasajero: ves a qué hora salen los jeeps y colectivos y apartas tu cupo.\n"
                    "• 🚙 Conductor: avisas a qué hora sales y sabes cuántos pasajeros te esperan.",
                    [BTN_PASAJERO, BTN_CONDUCTOR] + ([BTN_TEL] if canal == "telegram" else []))

            # 3) Elegir / cambiar de rol
            if n in ("soy conductor", "conductor", "modo conductor"):
                self._r.registrar_perfil(actor, nombre if not perfil.nombre else None, "conductor")
                return self._msg(
                    "🚙 Listo, estás como CONDUCTOR.\n\nPara publicar un viaje escríbeme así:\n"
                    "👉 salgo 6:30 de Mirador a Paraíso con 8 cupos\n\n"
                    "Luego usa los botones: ✅ Ya salí (comparte ubicación), 🚫 Lleno, ↪️ Desvío, 🏁 Terminé.",
                    self._botones_conductor(canal))
            if n in ("soy pasajero", "pasajero", "modo pasajero"):
                self._r.registrar_perfil(actor, nombre if not perfil.nombre else None, "pasajero")
                return self._msg(
                    "🧍 Listo, estás como PASAJERO.\n\nToca 🕒 Ver viajes para ver los jeeps y colectivos que salen, "
                    "o escríbeme por ejemplo: jeep a Paraíso.",
                    self._botones_pasajero(canal))

            # 4) Pasajero: ver próximos viajes (opcionalmente hacia/desde un barrio)
            if n in ("ver viajes", "viajes", "que viajes hay", "horarios") or re.search(r"\b(jeep|colectivo|veredal|a que hora sale)\b", n):
                lugares = self._p.menciones(texto)
                barrio = lugares[-1].id if lugares else None
                viajes = self._d.proximos(barrio, 8)
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
                return self._msg(f"🕒 Próximos viajes:\n\n{lineas}\n\nToca «Apartar» con el número del viaje.",
                                 apartar + [BTN_MENU])

            # 5) Pasajero: apartar cupo
            m = APARTAR.search(n)
            if m:
                idx = int(m.group(1)) - 1
                ids = self._ultimos.get(rid) or [t.id for t in self._d.proximos(None, 8)]
                if not (0 <= idx < len(ids)):
                    return self._msg("No encontré ese número de viaje. Toca 🕒 Ver viajes.", [BTN_VER])
                t = self._d.reservar(ids[idx], rid, perfil.nombre or nombre or "Pasajero")
                return self._msg(
                    f"✅ ¡Cupo apartado! {t.ruta} sale a las {t.hora} de {self._nom(t.origen_id)}.\n"
                    f"El conductor ya sabe que vas ({t.esperando} esperando, quedan {t.cupos_libres} cupos).",
                    [BTN_VER, BTN_MENU])

            # 6) Conductor: publicar viaje en lenguaje natural
            if n in ("publicar viaje", "publicar"):
                return self._msg("Escríbeme así 👇\nsalgo 6:30 de Mirador a Paraíso con 8 cupos",
                                 self._botones_conductor(canal))
            if (conductor or "cupo" in n) and re.search(r"\b(salgo|sale|saldre|voy a salir)\b", n):
                hora, sin_hora = _hora(texto)
                cupos_m = CUPOS.search(sin_hora)
                cupos = int(cupos_m.group(1)) if cupos_m else 4
                sin_cupos = CUPOS.sub(" ", sin_hora)
                lugares = self._p.menciones(sin_cupos)
                if not hora or len(lugares) < 2:
                    return self._msg("No te entendí del todo 🙏 Escríbeme así:\nsalgo 6:30 de Mirador a Paraíso con 8 cupos",
                                     self._botones_conductor(canal))
                if not conductor:
                    self._r.registrar_perfil(actor, None, "conductor")
                prof = self._d.perfil(rid)
                ruta = (prof.ruta if prof and prof.ruta else f"Ruta {lugares[0].nombre} – {lugares[1].nombre}")
                if not prof:
                    self._d.registrar_conductor(rid, ruta, lugares[0].id)
                t = self._d.anunciar(rid, perfil.nombre or nombre or "Conductor", lugares[0].id, lugares[1].id, hora, cupos, ruta)
                return self._msg(
                    f"📣 ¡Viaje publicado!\n{t.ruta}: {self._nom(t.origen_id)} → {self._nom(t.destino_id)}\n"
                    f"🕒 {t.hora} · {t.cupos_total} cupos\n\nTe aviso cuántos pasajeros apartan. Cuando arranques, toca ✅ Ya salí.",
                    self._botones_conductor(canal))

            # 7) Conductor: acciones sobre su viaje activo
            if conductor:
                activo = self._d.viaje_activo(rid)
                if n in ("ya sali", "sali", "arranque", "ya arranque", "en camino"):
                    if not activo:
                        return self._msg("No tienes un viaje publicado. Escríbeme: salgo 6:30 de Mirador a Paraíso con 8 cupos",
                                         self._botones_conductor(canal))
                    lat, lng = ubicacion if ubicacion else (None, None)
                    t = self._d.salir(activo.id, rid, lat, lng)
                    extra = "" if ubicacion else "\n📍 Toca «Enviar mi ubicación» para que te vean en el mapa."
                    lleno = " ¡Y sales LLENO! 🚫" if t.lleno else ""
                    return self._msg(f"🚙 ¡En ruta!{lleno} Avisé a {_pasajeros(t.esperando)} que te esperan.{extra}",
                                     self._botones_conductor(canal))
                if ubicacion and activo and not texto.strip():
                    t = self._d.salir(activo.id, rid, ubicacion[0], ubicacion[1])
                    return self._msg("📍 Ubicación actualizada: tus pasajeros ven que ya te moviste.",
                                     self._botones_conductor(canal))
                if n in ("lleno", "voy lleno", "sali lleno") and activo:
                    self._d.marcar_lleno(activo.id, rid)
                    return self._msg("🚫 Marcado como LLENO. Ya no se aparta más cupo.", self._botones_conductor(canal))
                if n.startswith("desvio") and activo:
                    nota = texto.split(" ", 1)[1] if " " in texto.strip() else ""
                    if not nota:
                        return self._msg("↪️ Cuéntame el desvío, por ejemplo:\ndesvío por la 68 porque hay protesta en la Distrital",
                                         self._botones_conductor(canal))
                    t = self._d.desvio(activo.id, rid, nota)
                    try:
                        if t.origen_id and t.destino_id:
                            self._r.reportar(actor, "novedad", t.origen_id, t.destino_id, None, f"Desvío de {t.ruta}: {t.desvio}")
                    except DomainError:
                        pass
                    return self._msg(f"↪️ Desvío avisado a tus pasajeros: {t.desvio}", self._botones_conductor(canal))
                if n in ("termine", "terminado", "finalizar", "fin") and activo:
                    self._d.finalizar(activo.id, rid)
                    return self._msg("🏁 Viaje terminado. ¡Gracias por mover a Ciudad Bolívar! 🙌",
                                     self._botones_conductor(canal))
                if n in ("cuantos esperan", "pasajeros", "quien va") and activo:
                    t = next((x for x in self._d.proximos(None, 50) if x.id == activo.id), activo)
                    return self._msg(f"🧍 {_pasajeros(t.esperando)} esperando tu viaje de las {t.hora}.",
                                     self._botones_conductor(canal))
        except DomainError as e:
            return self._msg(f"🙏 {e}")

        return None  # no es de viajes: responde el asistente de rutas
