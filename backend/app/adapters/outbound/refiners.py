"""Adaptadores de LLM: ResponseRefiner (pulir texto) y MessageInterpreter (entender texto libre).

Agregar otro proveedor = otra clase con `refine` / `interpret`.
"""

import asyncio
import json
import logging

from app.domain.models import InterpretContext, Interpretation, RefineContext

log = logging.getLogger(__name__)

INSTRUCCION_SISTEMA = (
    "Eres el asistente de movilidad de Muévete CB en Ciudad Bolívar, Bogotá. "
    "Reescribe el TEXTO BASE para que suene cálido, claro y breve, en español colombiano. "
    "Reglas estrictas: no cambies cifras, tiempos, precios, nombres de rutas, paraderos ni el orden de los pasos; "
    "no inventes información que no esté en el texto base o en los hechos; conserva todos los emojis del texto base; "
    "no saludes (la conversación ya empezó); "
    "máximo 900 caracteres. Responde solo con el texto final."
)


INSTRUCCION_INTERPRETE = (
    "Eres el intérprete del asistente de movilidad Muévete CB (Ciudad Bolívar, Bogotá: TransMiCable, SITP, "
    "jeeps y colectivos). Clasifica el mensaje del usuario y extrae datos. Reglas:\n"
    "- intencion: 'ruta' si quiere ir a algún lado o da un origen/destino; 'reporte' si avisa un problema en la vía "
    "(derrumbe, bloqueo, trancón, bus lleno, sin servicio, novedad); 'saludo'; 'ayuda' si pregunta qué puedes hacer; "
    "'otro' para lo demás.\n"
    "- origen/destino/lugares: escribe el nombre tal como aparece en la lista de LUGARES CONOCIDOS cuando el usuario "
    "se refiera a uno (aunque lo escriba mal o con otro nombre); si no está en la lista, cópialo como lo dijo.\n"
    "- Si el sistema espera un lugar (paso origen/destino o pendiente) y el mensaje es solo un lugar, ponlo en ese campo.\n"
    "- prioridad: 'rapido', 'barato' o 'transbordos' (menos transbordos) solo si el usuario lo expresa.\n"
    "- respuesta: solo para 'saludo', 'ayuda' u 'otro': una frase breve y cálida en español colombiano que responda y "
    "lo invite a decir de dónde sale y a dónde va o a reportar una novedad. Nunca inventes rutas, tiempos ni precios."
)


class _Gemini:
    """Cliente de Gemini (SDK `google-genai`) con modelo de respaldo.

    Sin reintentos del SDK: si el modelo principal está saturado (503) o no responde en `primary_timeout_s`,
    se pregunta una vez al modelo de respaldo. Si también falla, el error sube y el asistente sigue con reglas.
    """

    def __init__(self, api_key: str, model: str, *, fallback_model: str = "", primary_timeout_s: float = 6.0,
                 thinking: str = ""):
        from google import genai  # importación diferida: solo se necesita si el proveedor está activo
        from google.genai import types

        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))
        )
        self._model = model
        self._fallback = fallback_model if fallback_model != model else ""
        self._primary_timeout = primary_timeout_s
        self._thinking = thinking

    async def _generar(self, instruccion: str, prompt: str, **kw):
        from google.genai import types

        extra = {"thinking_config": types.ThinkingConfig(thinking_level=self._thinking)} if self._thinking else {}
        config = types.GenerateContentConfig(
            system_instruction=instruccion,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            **extra, **kw,
        )
        llamar = lambda modelo: self._client.aio.models.generate_content(  # noqa: E731
            model=modelo, contents=prompt, config=config
        )
        if not self._fallback:
            return await llamar(self._model)
        try:
            return await asyncio.wait_for(llamar(self._model), self._primary_timeout)
        except Exception as e:  # noqa: BLE001 — timeout, 503, cuota… → modelo de respaldo
            log.info("%s no respondió (%s); se usa %s", self._model, type(e).__name__, self._fallback)
            return await llamar(self._fallback)


class NoopRefiner:
    """Sin LLM: devuelve el texto del dominio tal cual."""

    async def refine(self, ctx: RefineContext) -> str:
        return ctx.texto_base


class GeminiRefiner(_Gemini):
    """Pule el texto del dominio con Gemini."""

    def __init__(self, api_key: str, model: str, max_chars: int = 900, **kw):
        super().__init__(api_key, model, **kw)
        self._max_chars = max_chars

    async def refine(self, ctx: RefineContext) -> str:
        formato = "texto plano, sin markdown" if ctx.canal in ("whatsapp", "telegram") else "texto plano"
        prompt = (
            f"Canal: {ctx.canal} ({formato}).\n"
            f"Mensaje del usuario: {ctx.mensaje_usuario}\n"
            f"Hechos (JSON): {json.dumps(ctx.hechos, ensure_ascii=False, default=str)[:4000]}\n\n"
            f"TEXTO BASE:\n{ctx.texto_base}"
        )
        resp = await self._generar(INSTRUCCION_SISTEMA, prompt, temperature=0.4)
        return (resp.text or "").strip()[: self._max_chars]


class NoopInterpreter:
    """Sin LLM: el asistente se queda con sus reglas."""

    async def interpret(self, ctx: InterpretContext) -> Interpretation | None:
        return None


class GeminiInterpreter(_Gemini):
    """Gemini con salida JSON estructurada (esquema = `Interpretation`)."""

    async def interpret(self, ctx: InterpretContext) -> Interpretation | None:
        prompt = (
            f"LUGARES CONOCIDOS: {', '.join(ctx.lugares)}\n"
            f"Paso actual del sistema: {ctx.paso}"
            + (f" (espera el {ctx.pendiente})" if ctx.pendiente else "")
            + f"\nCanal: {ctx.canal}\n\nMENSAJE DEL USUARIO:\n{ctx.texto[:1000]}"
        )
        resp = await self._generar(
            INSTRUCCION_INTERPRETE, prompt,
            temperature=0, response_mime_type="application/json", response_schema=Interpretation,
        )
        if isinstance(resp.parsed, Interpretation):
            return resp.parsed
        return Interpretation.model_validate_json(resp.text) if resp.text else None
