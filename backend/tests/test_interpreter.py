"""El intérprete LLM entra solo cuando las reglas no entienden el mensaje."""

import asyncio

from app.adapters.outbound.memory_repos import MemoryIncidentRepository, MemoryReporterRepository
from app.adapters.outbound.refiners import NoopRefiner
from app.container import build_container
from app.domain.models import InboundMessage, InterpretContext, Interpretation
from tests.conftest import make_settings


class FakeInterpreter:
    def __init__(self, respuesta: Interpretation | None = None, error: Exception | None = None):
        self.respuesta, self.error, self.llamadas = respuesta, error, []

    async def interpret(self, ctx: InterpretContext) -> Interpretation | None:
        self.llamadas.append(ctx)
        if self.error:
            raise self.error
        return self.respuesta


def con_interprete(interp, reloj):
    return build_container(make_settings(), incidents=MemoryIncidentRepository(),
                           reporters=MemoryReporterRepository(), refiner=NoopRefiner(),
                           interpreter=interp, clock=reloj)


def conversar(container, *textos):
    async def run():
        return [await container.assistant.handle(InboundMessage(canal="web", user_id="u1", texto=t)) for t in textos]
    return asyncio.run(run())


def test_reglas_primero_no_llaman_al_llm(reloj):
    interp = FakeInterpreter(Interpretation(intencion="otro", respuesta="no debería usarse"))
    c = con_interprete(interp, reloj)
    outs = conversar(c, "hola", "guiada", "meissen", "paraiso", "1", "de meissen a paraiso")
    assert interp.llamadas == []
    assert outs[-1].paso == "resultado"


def test_texto_libre_se_convierte_en_ruta(reloj):
    interp = FakeInterpreter(Interpretation(intencion="ruta", origen="Meissen", destino="Mirador (El Paraíso)",
                                            prioridad="barato"))
    c = con_interprete(interp, reloj)
    out = conversar(c, "necesito llegar donde mi tía que vive arriba en el mirador, ando por el hospital")[-1]
    assert out.paso == "resultado" and out.modo == "manual"
    assert (out.plan.origen.id, out.plan.destino.id) == ("meissen", "mirador")
    assert out.plan.opciones[out.plan.recomendada].prioridad == "barato"
    ctx = interp.llamadas[0]
    assert ctx.paso == "inicio" and "Meissen" in ctx.lugares


def test_paso_guiado_usa_el_lugar_que_lee_el_llm(reloj):
    c = con_interprete(FakeInterpreter(Interpretation(intencion="ruta", origen="Meissen")), reloj)
    out = conversar(c, "guiada", "ando donde la señora de las empanadas")[-1]
    assert out.paso == "destino" and "Origen: Meissen" in out.texto


def test_reporte_sin_palabras_clave(reloj):
    interp = FakeInterpreter(Interpretation(intencion="reporte", tipo_reporte="sinservicio",
                                            lugares=["Mirador (El Paraíso)"]))
    c = con_interprete(interp, reloj)
    out = conversar(c, "llevo una hora esperando y nada que baja el carro de arriba del mirador")[-1]
    assert out.reporte and out.reporte.tipo == "sinservicio"


def test_charla_responde_y_retoma_la_pregunta(reloj):
    c = con_interprete(FakeInterpreter(Interpretation(intencion="otro", respuesta="¡Con gusto, vecino!")), reloj)
    out = conversar(c, "guiada", "gracias parce")[-1]
    assert out.texto.startswith("¡Con gusto, vecino!") and "Paso 1 de 3" in out.texto and out.paso == "origen"


def test_llm_caido_sigue_con_reglas(reloj):
    c = con_interprete(FakeInterpreter(error=RuntimeError("sin red")), reloj)
    assert "No reconozco" in conversar(c, "guiada", "marte")[-1].texto
    assert conversar(c, "menu", "blablabla")[-1].paso == "inicio"


def test_frase_con_un_lugar_la_lee_el_llm(reloj):
    interp = FakeInterpreter(Interpretation(intencion="reporte", tipo_reporte="sinservicio", lugares=["Paraíso Alto"]))
    c = con_interprete(interp, reloj)
    out = conversar(c, "de meissen a paraiso", "nada que baja el carro en paraíso")[-1]
    assert out.reporte and out.reporte.tipo == "sinservicio"
    assert len(interp.llamadas) == 1  # una sola llamada por mensaje


def test_nombre_de_lugar_suelto_no_llama_al_llm(reloj):
    interp = FakeInterpreter(Interpretation(intencion="otro", respuesta="x"))
    c = con_interprete(interp, reloj)
    assert conversar(c, "manual", "voy a paraiso", "meissen")[-1].paso == "resultado"
    assert interp.llamadas == []
