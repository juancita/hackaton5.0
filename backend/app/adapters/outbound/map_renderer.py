"""Dibuja el mapa de una ruta sobre teselas de OpenStreetMap con Pillow.

Si las teselas no se pueden descargar, el mapa se dibuja igual sobre un fondo liso: la ruta,
A/B y la ubicación siguen siendo legibles.
"""

import io
import logging
import math
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
from PIL import Image, ImageDraw, ImageFont

from app.domain.mapas import Punto, RouteMap, distancia_m

log = logging.getLogger(__name__)

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
ATRIBUCION = "© colaboradores de OpenStreetMap"
ANCHO, ALTO = 1024, 768
MARGEN = 110
ZOOM_MIN, ZOOM_MAX = 11, 17
UBICACION_MAX_M = 8_000  # más lejos que esto de A o B, la ubicación no se dibuja (alejaría todo el mapa)

FONDO = "#ECE8E1"
COLOR_A, COLOR_B, COLOR_TU = "#1A6B00", "#B00020", "#1A73E8"


def _fuente(tam: int, negrita: bool = False) -> ImageFont.ImageFont:
    nombres = ["DejaVuSans-Bold.ttf", "arialbd.ttf"] if negrita else ["DejaVuSans.ttf", "arial.ttf"]
    for nombre in nombres:
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return ImageFont.load_default(size=tam)


class TileMapRenderer:
    def __init__(self, tile_url: str = TILE_URL, tile_size: int = 256, timeout_s: float = 4.0):
        self._url = tile_url
        self._tam = tile_size
        self._http = httpx.Client(timeout=timeout_s, follow_redirects=True, headers={"User-Agent": "MueveteCB/1.0 (asistente de movilidad, Ciudad Bolivar)"})
        self._cache: dict[tuple[int, int, int], Image.Image] = {}
        self._lock = threading.Lock()
        self._fuentes = {k: _fuente(t, n) for k, (t, n) in
                         {"pin": (26, True), "leyenda": (19, False), "titulo": (19, True), "nota": (14, False)}.items()}

    # --- Teselas -----------------------------------------------------------------

    def _tesela(self, z: int, x: int, y: int) -> Image.Image | None:
        clave = (z, x, y)
        with self._lock:
            if clave in self._cache:
                return self._cache[clave]
        try:
            r = self._http.get(self._url.format(z=z, x=x, y=y))
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception as e:  # noqa: BLE001 — sin tesela se dibuja sobre fondo liso
            log.warning("No se pudo descargar la tesela %s: %s", clave, type(e).__name__)
            return None
        if img.size != (self._tam, self._tam):
            img = img.resize((self._tam, self._tam))
        with self._lock:
            if len(self._cache) > 400:
                self._cache.clear()
            self._cache[clave] = img
        return img

    def _mundo(self, p: Punto, z: int) -> tuple[float, float]:
        """Web Mercator: (lat, lng) → píxel en el mundo a zoom z."""
        n = self._tam * 2 ** z
        s = math.sin(math.radians(max(min(p[0], 85.0), -85.0)))
        return (p[1] + 180) / 360 * n, (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n

    def _zoom(self, puntos: list[Punto]) -> int:
        for z in range(ZOOM_MAX, ZOOM_MIN - 1, -1):
            xs, ys = zip(*(self._mundo(p, z) for p in puntos))
            if max(xs) - min(xs) <= ANCHO - 2 * MARGEN and max(ys) - min(ys) <= ALTO - 2 * MARGEN:
                return z
        return ZOOM_MIN

    # --- Dibujo ------------------------------------------------------------------

    def render(self, mapa: RouteMap) -> bytes:
        ubicacion = mapa.ubicacion
        if ubicacion and min(distancia_m(ubicacion, mapa.origen.punto), distancia_m(ubicacion, mapa.destino.punto)) > UBICACION_MAX_M:
            ubicacion = None
        puntos = [p for linea in mapa.lineas for p in linea.puntos] + [mapa.origen.punto, mapa.destino.punto]
        if ubicacion:
            puntos.append(ubicacion)

        z = self._zoom(puntos)
        xs, ys = zip(*(self._mundo(p, z) for p in puntos))
        izq = (min(xs) + max(xs)) / 2 - ANCHO / 2
        arr = (min(ys) + max(ys)) / 2 - ALTO / 2

        img = Image.new("RGB", (ANCHO, ALTO), FONDO)
        self._pegar_teselas(img, z, izq, arr)
        d = ImageDraw.Draw(img, "RGBA")
        px = lambda p: (lambda x, y: (x - izq, y - arr))(*self._mundo(p, z))  # noqa: E731

        for linea in mapa.lineas:
            pts = [px(p) for p in linea.puntos]
            d.line(pts, fill="white", width=16, joint="curve")
            if linea.formal:
                d.line(pts, fill=linea.color, width=10, joint="curve")
            else:
                _linea_punteada(d, pts, linea.color, 10)
        for p in mapa.transbordos:
            x, y = px(p)
            d.ellipse((x - 11, y - 11, x + 11, y + 11), fill="#111111", outline="white", width=4)
        if ubicacion:
            x, y = px(ubicacion)
            d.ellipse((x - 34, y - 34, x + 34, y + 34), fill=(26, 115, 232, 55))
            d.ellipse((x - 14, y - 14, x + 14, y + 14), fill=COLOR_TU, outline="white", width=5)
        self._pin(d, px(mapa.origen.punto), "A", COLOR_A)
        self._pin(d, px(mapa.destino.punto), "B", COLOR_B)
        if ubicacion:  # etiqueta encima de todo: se ve aunque el punto quede bajo A o B
            self._etiqueta(d, px(ubicacion), "Estás aquí")

        self._leyenda(d, mapa, ubicacion is not None, mapa.ubicacion is not None and ubicacion is None)
        nota = self._fuentes["nota"]
        ancho = d.textlength(ATRIBUCION, font=nota)
        d.rectangle((ANCHO - ancho - 16, ALTO - 26, ANCHO, ALTO), fill=(255, 255, 255, 200))
        d.text((ANCHO - ancho - 8, ALTO - 22), ATRIBUCION, fill="#333333", font=nota)

        out = io.BytesIO()
        img.save(out, "JPEG", quality=88, optimize=True)
        return out.getvalue()

    def _pegar_teselas(self, img: Image.Image, z: int, izq: float, arr: float) -> None:
        if not self._url:
            return
        n = 2 ** z
        coords = [
            (tx, ty)
            for tx in range(math.floor(izq / self._tam), math.floor((izq + ANCHO) / self._tam) + 1)
            for ty in range(math.floor(arr / self._tam), math.floor((arr + ALTO) / self._tam) + 1)
            if 0 <= ty < n
        ]
        with ThreadPoolExecutor(max_workers=8) as pool:
            teselas = list(pool.map(lambda c: self._tesela(z, c[0] % n, c[1]), coords))
        for (tx, ty), tesela in zip(coords, teselas):
            if tesela:
                img.paste(tesela, (round(tx * self._tam - izq), round(ty * self._tam - arr)))

    def _pin(self, d: ImageDraw.ImageDraw, p: tuple[float, float], letra: str, color: str) -> None:
        x, y = p
        d.ellipse((x - 24, y - 24, x + 24, y + 24), fill=color, outline="white", width=5)
        d.text((x, y), letra, fill="white", font=self._fuentes["pin"], anchor="mm")

    def _etiqueta(self, d: ImageDraw.ImageDraw, p: tuple[float, float], texto: str) -> None:
        x, y = p
        f = self._fuentes["titulo"]
        ancho = d.textlength(texto, font=f) + 24
        # A la izquierda del punto si a la derecha no cabe
        izq = x + 34 if x + 34 + ancho < ANCHO - 8 else x - 34 - ancho
        arriba = max(8, y - 62)
        caja = (izq, arriba, izq + ancho, arriba + 34)
        d.line((x, y, izq + (0 if izq > x else ancho), arriba + 17), fill=COLOR_TU, width=4)
        d.rounded_rectangle(caja, radius=17, fill=COLOR_TU, outline="white", width=3)
        d.text((izq + ancho / 2, arriba + 17), texto, fill="white", font=f, anchor="mm")

    def _leyenda(self, d: ImageDraw.ImageDraw, mapa: RouteMap, con_ubicacion: bool, ubicacion_lejos: bool) -> None:
        f, ft = self._fuentes["leyenda"], self._fuentes["titulo"]
        filas: list[tuple[str, str, str]] = [  # (tipo de símbolo, color, texto)
            ("pin", COLOR_A, f"A · {mapa.origen.nombre}"),
            ("pin", COLOR_B, f"B · {mapa.destino.nombre}"),
            *(("linea", color, nombre) for nombre, color in mapa.modos),
        ]
        if mapa.transbordos:
            filas.append(("transbordo", "#111111", "Transbordo"))
        if con_ubicacion:
            filas.append(("punto", COLOR_TU, "Tu ubicación"))
        elif ubicacion_lejos:
            filas.append(("punto", COLOR_TU, "Tu ubicación (fuera del mapa)"))

        alto_fila, x0 = 30, 16
        ancho = max(d.textlength(t, font=ft if s == "pin" else f) for s, _, t in filas) + 70
        alto = alto_fila * len(filas) + 16
        y0 = ALTO - alto - 36
        d.rounded_rectangle((x0, y0, x0 + ancho, y0 + alto), radius=12, fill=(255, 255, 255, 225), outline=(0, 0, 0, 40))
        for i, (simbolo, color, texto) in enumerate(filas):
            cy = y0 + 8 + alto_fila * i + alto_fila / 2
            cx = x0 + 28
            if simbolo == "pin":
                d.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=color, outline="white", width=2)
            elif simbolo == "linea":
                d.line((cx - 16, cy, cx + 16, cy), fill=color, width=8)
            elif simbolo == "transbordo":
                d.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=color, outline="white", width=3)
            else:
                d.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=color, outline="white", width=3)
            d.text((cx + 26, cy), texto, fill="#1F1F1F", font=ft if simbolo == "pin" else f, anchor="lm")


def _linea_punteada(d: ImageDraw.ImageDraw, pts: list[tuple[float, float]], color: str, ancho: int,
                    trazo: float = 22, hueco: float = 12) -> None:
    """Línea discontinua (transporte informal), igual que en el mapa web."""
    dibujando, restante = True, trazo
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        largo = math.hypot(x2 - x1, y2 - y1)
        hecho = 0.0
        while hecho < largo:
            paso = min(restante, largo - hecho)
            if dibujando:
                a, b = hecho / largo, (hecho + paso) / largo
                d.line((x1 + (x2 - x1) * a, y1 + (y2 - y1) * a, x1 + (x2 - x1) * b, y1 + (y2 - y1) * b),
                       fill=color, width=ancho)
            hecho += paso
            restante -= paso
            if restante <= 0:
                dibujando = not dibujando
                restante = trazo if dibujando else hueco
