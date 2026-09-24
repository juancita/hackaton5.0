"""Adaptadores del puerto ResponseRefiner (LLM). Agregar otro proveedor = otra clase con `refine`."""

import json

from app.domain.models import RefineContext

INSTRUCCION_SISTEMA = (
    "Eres el asistente de movilidad de Muévete CB en Ciudad Bolívar, Bogotá. "
    "Reescribe el TEXTO BASE para que suene cálido, claro y breve, en español colombiano. "
    "Reglas estrictas: no cambies cifras, tiempos, precios, nombres de rutas, paraderos ni el orden de los pasos; "
    "no inventes información que no esté en el texto base o en los hechos; conserva los emojis de cada modo; "
    "máximo 900 caracteres. Responde solo con el texto final."
)


class NoopRefiner:
    """Sin LLM: devuelve el texto del dominio tal cual."""

    async def refine(self, ctx: RefineContext) -> str:
        return ctx.texto_base


class GeminiRefiner:
    """Gemini Flash vía SDK oficial `google-genai`."""

    def __init__(self, api_key: str, model: str, max_chars: int = 900):
        from google import genai  # importación diferida: solo se necesita si el proveedor está activo

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_chars = max_chars

    async def refine(self, ctx: RefineContext) -> str:
        from google.genai import types

        formato = "texto plano, sin markdown" if ctx.canal in ("whatsapp", "telegram") else "texto plano"
        prompt = (
            f"Canal: {ctx.canal} ({formato}).\n"
            f"Mensaje del usuario: {ctx.mensaje_usuario}\n"
            f"Hechos (JSON): {json.dumps(ctx.hechos, ensure_ascii=False, default=str)[:4000]}\n\n"
            f"TEXTO BASE:\n{ctx.texto_base}"
        )
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=INSTRUCCION_SISTEMA, temperature=0.4, max_output_tokens=512
            ),
        )
        return (resp.text or "").strip()[: self._max_chars]
