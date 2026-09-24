"""Normalización de texto compartida por búsqueda de lugares y el asistente."""

import math
import re
import unicodedata

_NO_ALNUM = re.compile(r"[^a-z0-9ñ ]+")
_SPACES = re.compile(r"\s+")


def normalize(texto: str | None) -> str:
    """Minúsculas, sin tildes, sin puntuación y con espacios colapsados."""
    if not texto:
        return ""
    t = texto.lower().replace("ñ", "\0")
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = t.replace("\0", "ñ")
    t = _NO_ALNUM.sub(" ", t)
    return _SPACES.sub(" ", t).strip()


def formato_cop(valor: float) -> str:
    """4450 -> '4.450' (separador de miles colombiano)."""
    return f"{int(round(valor)):,}".replace(",", ".")


def redondear(x: float) -> int:
    """Redondeo como Math.round de JS (0.5 hacia arriba), no el bancario de Python."""
    return math.floor(x + 0.5)
