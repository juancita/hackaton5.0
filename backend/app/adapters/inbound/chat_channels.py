"""Adaptadores de entrada del asistente. Cada canal traduce su payload a InboundMessage
y muestra el OutboundMessage a su manera. El dominio no sabe de qué canal viene."""

import hashlib
import hmac
import logging

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.adapters.inbound.deps import get_container
from app.container import Container
from app.domain.models import InboundMessage, OutboundMessage

log = logging.getLogger(__name__)
router = APIRouter(tags=["asistente"])


def _http(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


# --- Web -----------------------------------------------------------------------

class WebChatRequest(BaseModel):
    texto: str = Field(default="", max_length=1000)
    nombre: str | None = None


@router.post("/chat/web", response_model=OutboundMessage)
async def web_chat(
    body: WebChatRequest,
    x_client_id: str | None = Header(default=None),
    c: Container = Depends(get_container),
) -> OutboundMessage:
    if not x_client_id or not x_client_id.strip():
        raise HTTPException(400, "Falta el header X-Client-Id")
    msg = InboundMessage(canal="web", user_id=x_client_id.strip()[:128], texto=body.texto, nombre=body.nombre)
    return await c.assistant.handle(msg)


# --- Telegram ------------------------------------------------------------------

def render_telegram(out: OutboundMessage) -> dict:
    labels = [o.label for o in out.opciones_rapidas]
    if not labels:
        return {"text": out.texto, "reply_markup": {"remove_keyboard": True}}
    filas = [labels[i:i + 2] for i in range(0, len(labels), 2)]
    return {
        "text": out.texto,
        "reply_markup": {
            "keyboard": [[{"text": t} for t in fila] for fila in filas],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        },
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
    msg = InboundMessage(
        canal="telegram",
        user_id=str(remitente["id"]),
        texto=message.get("text", ""),
        nombre=remitente.get("first_name"),
    )
    out = await c.assistant.handle(msg)
    payload = {"chat_id": message["chat"]["id"], **render_telegram(out)}

    if c.settings.telegram_token:
        try:
            r = await _http(request).post(
                f"https://api.telegram.org/bot{c.settings.telegram_token}/sendMessage", json=payload
            )
            r.raise_for_status()
        except httpx.HTTPError:
            log.exception("No se pudo enviar la respuesta a Telegram")
    return {"ok": True, "respuesta": out.model_dump(mode="json")}


# --- WhatsApp (Meta Cloud API) -------------------------------------------------

def render_whatsapp(out: OutboundMessage) -> str:
    if not out.opciones_rapidas:
        return out.texto
    lista = "\n".join(f"{i}. {o.label}" for i, o in enumerate(out.opciones_rapidas, 1))
    return f"{out.texto}\n\n{lista}\n\nResponde con el número o escribe tu respuesta."


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
                msg = InboundMessage(
                    canal="whatsapp",
                    user_id=contacto.get("wa_id") or wa_id,
                    texto=(m.get("text") or {}).get("body", "") if m.get("type") == "text" else "",
                    nombre=(contacto.get("profile") or {}).get("name"),
                )
                out = await c.assistant.handle(msg)
                respuestas.append(out.model_dump(mode="json"))
                await _enviar_whatsapp(request, c, msg.user_id, render_whatsapp(out))
    return {"ok": True, "respuestas": respuestas}


async def _enviar_whatsapp(request: Request, c: Container, para: str, texto: str) -> None:
    s = c.settings
    if not (s.whatsapp_token and s.whatsapp_phone_id):
        return
    try:
        r = await _http(request).post(
            f"https://graph.facebook.com/{s.whatsapp_api_version}/{s.whatsapp_phone_id}/messages",
            headers={"Authorization": f"Bearer {s.whatsapp_token}"},
            json={"messaging_product": "whatsapp", "to": para, "type": "text", "text": {"body": texto[:4096]}},
        )
        r.raise_for_status()
    except httpx.HTTPError:
        log.exception("No se pudo enviar la respuesta a WhatsApp")
