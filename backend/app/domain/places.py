"""Sugerencias y resolución de lugares (spec 01)."""

from app.domain.models import Network, Place, Resolution, Suggestion
from app.domain.text import normalize

TIPOS_POPULARES = ("portal", "salud", "cable")
MAX_LIMIT = 20
MAX_CANDIDATOS = 5


class PlaceService:
    def __init__(self, network: Network):
        self._lugares = network.paraderos
        self._por_id = {p.id: p for p in network.paraderos}
        self._nombres = {p.id: normalize(p.nombre) for p in network.paraderos}
        # alias normalizado -> id (se ignoran alias que apuntan a ids inexistentes)
        self._alias = {normalize(k): v for k, v in network.alias.items() if v in self._por_id}

    def populares(self, limit: int = 8) -> list[Suggestion]:
        lugares = [p for p in self._lugares if p.tipo in TIPOS_POPULARES]
        return [Suggestion(**p.model_dump(), via="nombre") for p in lugares[:limit]]

    def suggest(self, q: str | None, limit: int = 8) -> list[Suggestion]:
        limit = max(1, min(limit, MAX_LIMIT))
        n = normalize(q)
        if len(n) < 2:
            return self.populares(limit)

        # id -> (rango, via). Menor rango = más relevante.
        mejores: dict[str, tuple[int, str]] = {}

        def considerar(pid: str, rango: int, via: str) -> None:
            if pid not in mejores or rango < mejores[pid][0]:
                mejores[pid] = (rango, via)

        for pid, nombre in self._nombres.items():
            if nombre.startswith(n):
                considerar(pid, 1, "nombre")
            elif any(w.startswith(n) for w in nombre.split()):
                considerar(pid, 2, "nombre")
            elif n in nombre:
                considerar(pid, 4, "nombre")
        for alias, pid in self._alias.items():
            if alias.startswith(n):
                considerar(pid, 3, "alias")
            elif n in alias:
                considerar(pid, 4, "alias")

        orden = sorted(mejores.items(), key=lambda kv: (kv[1][0], self._nombres[kv[0]]))
        return [Suggestion(**self._por_id[pid].model_dump(), via=via) for pid, (_, via) in orden[:limit]]

    def resolve(self, texto: str | None) -> Resolution:
        n = normalize(texto)
        if not n:
            return Resolution(estado="ninguno")

        # 1) Coincidencia exacta por nombre o alias
        for pid, nombre in self._nombres.items():
            if nombre == n:
                return Resolution(estado="exacto", lugar=self._por_id[pid])
        if n in self._alias:
            return Resolution(estado="exacto", lugar=self._por_id[self._alias[n]])

        # 2) Un alias o nombre completo mencionado dentro del texto ("salgo del hospital meissen")
        encontrados = self._spans(n)
        if encontrados:
            _, _, pid = max(encontrados, key=lambda s: s[1] - s[0])
            return Resolution(estado="exacto", lugar=self._por_id[pid])

        # 3) Sugerencias
        sugerencias = self.suggest(n, MAX_CANDIDATOS)
        if not sugerencias:
            return Resolution(estado="ninguno")
        lugares = [self._por_id[s.id] for s in sugerencias]
        if len(lugares) == 1:
            return Resolution(estado="exacto", lugar=lugares[0])
        return Resolution(estado="ambiguo", candidatos=lugares)

    def _spans(self, n: str) -> list[tuple[int, int, str]]:
        """Menciones de nombres o alias como palabras completas. Si dos se solapan gana la más larga."""
        texto = f" {n} "
        crudos: list[tuple[int, int, str]] = []
        for termino, pid in [*self._alias.items(), *((nom, pid) for pid, nom in self._nombres.items())]:
            inicio = texto.find(f" {termino} ")
            while inicio != -1:
                crudos.append((inicio, inicio + len(termino) + 1, pid))
                inicio = texto.find(f" {termino} ", inicio + 1)
        aceptados: list[tuple[int, int, str]] = []
        for s in sorted(crudos, key=lambda s: s[0] - s[1]):
            if all(s[1] <= a[0] or s[0] >= a[1] for a in aceptados):
                aceptados.append(s)
        return sorted(aceptados)

    def menciones(self, texto: str | None) -> list[Place]:
        """Lugares mencionados en un texto libre, en orden de aparición y sin repetir."""
        vistos: list[str] = []
        for _, _, pid in self._spans(normalize(texto)):
            if pid not in vistos:
                vistos.append(pid)
        return [self._por_id[pid] for pid in vistos]

    def get(self, place_id: str) -> Place | None:
        return self._por_id.get(place_id)
