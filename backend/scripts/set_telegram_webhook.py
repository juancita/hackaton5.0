"""Registra el webhook del bot de Telegram apuntando a /webhooks/telegram.

Uso (desde backend/):
    python -m scripts.set_telegram_webhook                  # toma la URL pública de ngrok (localhost:4040)
    python -m scripts.set_telegram_webhook https://xxxx.ngrok-free.app
    python -m scripts.set_telegram_webhook --info           # muestra el webhook actual
    python -m scripts.set_telegram_webhook --delete         # lo elimina

Lee TELEGRAM_TOKEN y TELEGRAM_WEBHOOK_SECRET del .env. El secreto viaja como `secret_token`
y Telegram lo reenvía en el header X-Telegram-Bot-Api-Secret-Token, que el backend valida.
"""

import sys

import httpx

from app.config import get_settings

RUTA = "/webhooks/telegram"


def url_ngrok() -> str:
    try:
        tuneles = httpx.get("http://127.0.0.1:4040/api/tunnels", timeout=3).json()["tunnels"]
    except (httpx.HTTPError, KeyError):
        sys.exit("ngrok no está corriendo. Arráncalo con `ngrok http 8000` o pasa la URL pública como argumento.")
    https = [t["public_url"] for t in tuneles if t["public_url"].startswith("https://")]
    if not https:
        sys.exit("ngrok no expone ningún túnel https.")
    return https[0]


def main() -> None:
    s = get_settings()
    if not s.telegram_token:
        sys.exit("Falta TELEGRAM_TOKEN en backend/.env")
    api = f"https://api.telegram.org/bot{s.telegram_token}"
    args = sys.argv[1:]

    if args[:1] == ["--info"]:
        print(httpx.get(f"{api}/getWebhookInfo").json())
        return
    if args[:1] == ["--delete"]:
        print(httpx.post(f"{api}/deleteWebhook").json())
        return

    base = (args[0] if args else url_ngrok()).rstrip("/")
    datos = {"url": base + RUTA, "allowed_updates": '["message"]', "drop_pending_updates": "true"}
    if s.telegram_webhook_secret:
        datos["secret_token"] = s.telegram_webhook_secret
    r = httpx.post(f"{api}/setWebhook", data=datos).json()
    print(f"{datos['url']} -> {r}")
    if not r.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
