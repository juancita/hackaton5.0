"""Adaptadores de entrada del asistente. Cada canal traduce su payload a InboundMessage
y muestra el OutboundMessage a su manera. El dominio no sabe de qué canal viene."""

import hashlib
import hmac
import html
import logging
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.adapters.inbound.deps import get_container
from app.adapters.inbound.http_api import imagen_mapa, parametros_mapa
from app.container import Container
from app.domain.models import InboundMessage, MapaRuta, OutboundMessage

log = logging.getLogger(__name__)
router = APIRouter(tags=["asistente"])


def _http(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


# --- Mapa de la ruta -------------------------------------------------------------

def url_mapa(request: Request, c: Container, mapa: MapaRuta) -> str:
    base = (c.settings.public_base_url or str(request.base_url)).rstrip("/")
    return f"{base}/mapas/ruta.jpg?{urlencode(parametros_mapa(mapa))}"


async def mapa_listo(c: Container, mapa: MapaRuta | None) -> bool:
    """Genera (y deja en caché) la imagen antes de responder: si falla, se responde sin imagen."""
    if not mapa:
        return False
    q = parametros_mapa(mapa)
    try:
        await run_in_threadpool(imagen_mapa, c, q["r"], q.get("u", ""))
        return True
    except Exception:  # noqa: BLE001 — sin mapa la respuesta igual sale
        log.exception("No se pudo generar el mapa de la ruta")
        return False


# --- Web -----------------------------------------------------------------------

class WebChatRequest(BaseModel):
    texto: str = Field(default="", max_length=1000)
    nombre: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


@router.post("/chat/web", response_model=OutboundMessage)
async def web_chat(
    body: WebChatRequest,
    x_client_id: str | None = Header(default=None),
    c: Container = Depends(get_container),
) -> OutboundMessage:
    if not x_client_id or not x_client_id.strip():
        raise HTTPException(400, "Falta el header X-Client-Id")
    ubicacion = (body.lat, body.lng) if body.lat is not None and body.lng is not None else None
    msg = InboundMessage(canal="web", user_id=x_client_id.strip()[:128], texto=body.texto, nombre=body.nombre,
                         ubicacion=ubicacion)
    return await c.assistant.handle(msg)


# --- Telegram ------------------------------------------------------------------

SALIDAS = {"cancelar", "menu"}  # van solas en la última fila del teclado
LIMITE_CAPTION = 1024  # Telegram: largo máximo del texto que acompaña una foto
ENLACE_GOOGLE = "🗺️ Abrir la ruta en Google Maps"


def _teclado(out: OutboundMessage) -> dict:
    boton = lambda o: {"text": o.label, "request_location": True} if o.id == "ubicacion" else {"text": o.label}  # noqa: E731
    normales = [boton(o) for o in out.opciones_rapidas if o.id not in SALIDAS and o.id != "ubicacion"]
    solas = [[boton(o)] for o in out.opciones_rapidas if o.id == "ubicacion"]
    salidas = [boton(o) for o in out.opciones_rapidas if o.id in SALIDAS]
    filas = [normales[i:i + 2] for i in range(0, len(normales), 2)] + solas + ([salidas] if salidas else [])
    if not filas:
        return {"reply_markup": {"remove_keyboard": True}}
    return {"reply_markup": {
        "keyboard": filas,
        "resize_keyboard": True,
        "one_time_keyboard": True,
        "input_field_placeholder": "Toca una opción 👇",
    }}


def render_telegram(out: OutboundMessage, mapa_url: str | None = None) -> dict:
    """Método de la Bot API a ejecutar (sin chat_id). Con mapa: foto de la ruta + enlace a Google Maps."""
    if not (out.mapa and mapa_url):
        return {"method": "sendMessage", "text": out.texto, **_teclado(out)}
    texto = f'{html.escape(out.texto)}\n\n<a href="{html.escape(out.mapa.google_maps)}">{ENLACE_GOOGLE}</a>'
    visible = len(f"{out.texto}\n\n{ENLACE_GOOGLE}".encode("utf-16-le")) // 2
    if visible <= LIMITE_CAPTION:
        return {"method": "sendPhoto", "photo": mapa_url, "caption": texto, "parse_mode": "HTML", **_teclado(out)}
    # Texto muy largo para ir como pie de foto: mensaje con la imagen como vista previa grande
    return {
        "method": "sendMessage", "text": texto, "parse_mode": "HTML",
        "link_preview_options": {"url": mapa_url, "prefer_large_media": True, "show_above_text": True},
        **_teclado(out),
    }


@router.post("/webhooks/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    c: Container = Depends(get_container),
) -> dict:
    secreto = c.settings.telegram_webhook_secret
    if secreto and not hmac.compare_digest(x_telegram_bot_api_secret_token or "", secreto):
        raise HTTPException(401, "Secreto de webhook inválido")

    update = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not message or "from" not in message:
        return {"ok": True}  # updates sin mensaje (callbacks, joins…) se ignoran

    remitente = message["from"]
    ubicacion = message.get("location")
    msg = InboundMessage(
        canal="telegram",
        user_id=str(remitente["id"]),
        texto=message.get("text", ""),
        nombre=remitente.get("first_name"),
        ubicacion=(ubicacion["latitude"], ubicacion["longitude"]) if ubicacion else None,
    )
    out = await c.assistant.handle(msg)
    mapa_url = url_mapa(request, c, out.mapa) if await mapa_listo(c, out.mapa) else None
    # Se responde en el cuerpo del webhook: Telegram ejecuta el método por nosotros,
    # sin que el backend tenga que abrir una conexión saliente a api.telegram.org.
    return {"chat_id": message["chat"]["id"], **render_telegram(out, mapa_url)}


# --- WhatsApp (Meta Cloud API) -------------------------------------------------

def render_whatsapp(out: OutboundMessage) -> str:
    texto = f"{out.texto}\n\n🗺️ Ruta en Google Maps: {out.mapa.google_maps}" if out.mapa else out.texto
    if not out.opciones_rapidas:
        return texto
    lista = "\n".join(f"{i}. {o.label}" for i, o in enumerate(out.opciones_rapidas, 1))
    return f"{texto}\n\n{lista}\n\nResponde con el número o escribe tu respuesta."


@router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
def whatsapp_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    c: Container = Depends(get_container),
) -> str:
    esperado = c.settings.whatsapp_verify_token
    if hub_mode == "subscribe" and esperado and hmac.compare_digest(hub_verify_token, esperado):
        return hub_challenge
    raise HTTPException(403, "Token de verificación inválido")


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    c: Container = Depends(get_container),
) -> dict:
    cuerpo = await request.body()
    if c.settings.whatsapp_app_secret:
        firma = "sha256=" + hmac.new(c.settings.whatsapp_app_secret.encode(), cuerpo, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(x_hub_signature_256 or "", firma):
            raise HTTPException(401, "Firma inválida")

    data = await request.json()
    respuestas = []
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contactos = {ct.get("wa_id"): ct for ct in value.get("contacts", [])}
            for m in value.get("messages", []):
                wa_id = m.get("from")
                contacto = contactos.get(wa_id) or next(iter(contactos.values()), {})
                lugar = m.get("location") if m.get("type") == "location" else None
                msg = InboundMessage(
                    canal="whatsapp",
                    user_id=contacto.get("wa_id") or wa_id,
                    texto=(m.get("text") or {}).get("body", "") if m.get("type") == "text" else "",
                    nombre=(contacto.get("profile") or {}).get("name"),
                    ubicacion=(lugar["latitude"], lugar["longitude"]) if lugar else None,
                )
                out = await c.assistant.handle(msg)
                respuestas.append(out.model_dump(mode="json"))
                if await mapa_listo(c, out.mapa):
                    await _enviar_whatsapp(request, c, msg.user_id, {"type": "image", "image": {"link": url_mapa(request, c, out.mapa)}})
                await _enviar_whatsapp(request, c, msg.user_id, {"type": "text", "text": {"body": render_whatsapp(out)[:4096]}})
    return {"ok": True, "respuestas": respuestas}


async def _enviar_whatsapp(request: Request, c: Container, para: str, contenido: dict) -> None:
    s = c.settings
    if not (s.whatsapp_token and s.whatsapp_phone_id):
        return
    try:
        r = await _http(request).post(
            f"https://graph.facebook.com/{s.whatsapp_api_version}/{s.whatsapp_phone_id}/messages",
            headers={"Authorization": f"Bearer {s.whatsapp_token}"},
            json={"messaging_product": "whatsapp", "to": para, **contenido},
        )
        r.raise_for_status()
    except httpx.HTTPError:
        log.exception("No se pudo enviar la respuesta a WhatsApp")
