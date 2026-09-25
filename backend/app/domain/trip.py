"""Puerto de dominio central: punto de entrada + punto de salida -> toda la información del viaje."""

from app.domain.errors import InvalidInput, NotFound
from app.domain.models import PRIORIDADES, Network, PlaceRef, Prioridad, TripPlan
from app.domain.reports import ReportService
from app.domain.routing import RoutingService, clave_tramo


class PlanTripUseCase:
    def __init__(self, network: Network, routing: RoutingService, reports: ReportService):
        self._net = network
        self._routing = routing
        self._reports = reports

    def ejecutar(
        self, origen_id: str, destino_id: str, prioridad: Prioridad | None = None, modos: list[str] | None = None
    ) -> TripPlan:
        origen_id, destino_id = origen_id.strip().lower(), destino_id.strip().lower()
        origen, destino = self._net.lugar(origen_id), self._net.lugar(destino_id)
        if not origen:
            raise NotFound(f"Lugar de origen desconocido: {origen_id}")
        if not destino:
            raise NotFound(f"Lugar de destino desconocido: {destino_id}")
        if origen_id == destino_id:
            raise InvalidInput("El origen y el destino son el mismo lugar")
        if prioridad is not None and prioridad not in PRIORIDADES:
            raise InvalidInput(f"Prioridad inválida: {prioridad}")
        if modos is not None:
            desconocidos = [m for m in modos if m not in self._net.modos]
            if desconocidos:
                raise InvalidInput(f"Medio de transporte desconocido: {', '.join(desconocidos)}")

        pen = self._reports.penalizaciones()
        opciones = self._routing.opciones(
            origen_id, destino_id, pen, preferida=prioridad, modos=None if modos is None else frozenset(modos)
        )
        recomendada = next((i for i, o in enumerate(opciones) if o.prioridad == (prioridad or "rapido")), 0)

        def incidentes_de(ops) -> list[str]:
            ids: list[str] = []
            for op in ops:
                for leg in op.tramos:
                    for de, a in zip(leg.paradas, leg.paradas[1:]):
                        p = pen.get(clave_tramo(de, a, leg.modo)) or pen.get(clave_tramo(a, de, leg.modo))
                        for iid in p.incident_ids if p else []:
                            if iid not in ids:
                                ids.append(iid)
            return ids

        # Incidentes que tocan alguno de los tramos usados por las opciones
        aplicados = incidentes_de(opciones)
        # Cierres sobre la ruta HABITUAL (la que saldría sin alertas) que obligaron a desviarse:
        # sirven para avisar "hay un cierre, te mostramos alternativas" aunque ya no se use ese tramo.
        evitados: list[str] = []
        if pen:
            habituales = self._routing.opciones(
                origen_id, destino_id, {}, preferida=prioridad, modos=None if modos is None else frozenset(modos)
            )
            evitados = [i for i in incidentes_de(habituales) if i not in aplicados]

        return TripPlan(
            origen=PlaceRef(id=origen.id, nombre=origen.nombre),
            destino=PlaceRef(id=destino.id, nombre=destino.nombre),
            opciones=opciones,
            recomendada=recomendada,
            incidentes_aplicados=aplicados,
            incidentes_evitados=evitados,
        )
