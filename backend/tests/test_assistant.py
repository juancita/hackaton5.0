import asyncio

import pytest

from app.adapters.inbound.chat_channels import render_telegram, render_whatsapp
from app.adapters.outbound.memory_repos import MemoryIncidentRepository, MemoryReporterRepository
from app.container import build_container
from app.domain.models import InboundMessage
from tests.conftest import FakeRefiner, make_settings


def conversar(container, *textos, canal="web", user="u1"):
    async def run():
        return [await container.assistant.handle(InboundMessage(canal=canal, user_id=user, texto=t)) for t in textos]
    return asyncio.run(run())


def con_refiner(refiner, reloj):
    return build_container(make_settings(), incidents=MemoryIncidentRepository(),
                           reporters=MemoryReporterRepository(), refiner=refiner, clock=reloj)


def test_saludo_ofrece_modos(container):
    (out,) = conversar(container, "hola")
    assert out.paso == "inicio"
    assert [o.label for o in out.opciones_rapidas] == ["Guiada", "Manual"]


def test_flujo_guiado_completo(container):
    outs = conversar(container, "hola", "1", "Mei", "1", "paraiso", "2")
    assert [o.paso for o in outs] == ["inicio", "origen", "origen", "destino", "prioridad", "resultado"]
    assert [o.label for o in outs[2].opciones_rapidas] == ["Meissen", "Hospital Meissen"]
    plan = outs[-1].plan
    assert (plan.origen.id, plan.destino.id) == ("meissen", "paraiso")
    assert plan.opciones[plan.recomendada].prioridad == "barato"


def test_guiado_acepta_nombre_de_la_opcion(container):
    outs = conversar(container, "guiada", "Portal Tunal", "Hospital Meissen", "Menos transbordos")
    assert outs[-1].paso == "resultado"
    assert container.assistant._store.get("web:u1").prioridad == "transbordos"


def test_guiado_lugar_desconocido_ofrece_populares(container):
    out = conversar(container, "guiada", "marte")[-1]
    assert out.paso == "origen" and "No reconozco" in out.texto and out.opciones_rapidas


def test_guiado_destino_igual_al_origen(container):
    out = conversar(container, "guiada", "meissen", "meissen")[-1]
    assert out.paso == "destino" and "igual al origen" in out.texto


def test_manual_recuerda_destino(container):
    outs = conversar(container, "manual", "voy a paraíso", "meissen")
    assert "¿Desde dónde sales" in outs[1].texto
    assert outs[-1].paso == "resultado"
    assert (outs[-1].plan.origen.id, outs[-1].plan.destino.id) == ("meissen", "paraiso")


def test_primer_mensaje_con_ruta_responde_directo(container):
    (out,) = conversar(container, "de sierra morena al hospital meissen lo mas barato")
    assert out.modo == "manual" and out.paso == "resultado"
    assert out.plan.opciones[out.plan.recomendada].prioridad == "barato"


def test_reporte_a_mitad_del_flujo_conserva_el_paso(container):
    outs = conversar(container, "guiada", "meissen", "reporto trancón en perdomo")
    out = outs[-1]
    assert out.reporte is not None and out.reporte.tipo == "trancon"
    assert out.paso == "destino" and "¿A dónde te diriges?" in out.texto
    assert conversar(container, "paraiso")[-1].paso == "prioridad"


def test_reporte_sin_lugar_pide_detalle(container):
    out = conversar(container, "reportar")[-1]
    assert out.reporte is None and "dónde" in out.texto


def test_reporte_repetido_por_chat_no_falla(container):
    out = conversar(container, "hay un derrumbe en paraiso", "hay un derrumbe en paraiso")[-1]
    assert "hace poco" in out.texto


def test_ver_alternativas_y_otra_ruta(container):
    outs = conversar(container, "guiada", "meissen", "paraiso", "1", "2", "1")
    assert outs[4].texto.count("🚀") == len(outs[3].plan.opciones)
    assert outs[5].paso == "origen"


def test_menu_reinicia(container):
    out = conversar(container, "guiada", "meissen", "menu")[-1]
    assert out.paso == "inicio"


def test_conversacion_expira(container, reloj):
    conversar(container, "guiada", "meissen")
    reloj.avanzar(minutes=31)
    assert conversar(container, "paraiso")[-1].paso != "prioridad"


def test_estado_separado_por_canal_y_usuario(container):
    conversar(container, "guiada", "meissen", user="a")
    assert conversar(container, "paraiso", user="b")[-1].paso != "prioridad"
    assert conversar(container, "paraiso", canal="telegram", user="a")[-1].paso != "prioridad"


def test_mensaje_vacio(container):
    out = conversar(container, "guiada", "")[-1]
    assert "solo entiendo" in out.texto and out.paso == "origen"


# --- LLM -----------------------------------------------------------------------

def test_refiner_pule_solo_el_resultado(reloj):
    ref = FakeRefiner()
    c = con_refiner(ref, reloj)
    outs = conversar(c, "guiada", "meissen", "paraiso", "1")
    assert len(ref.llamadas) == 1  # las preguntas de los pasos no se pulen
    assert outs[-1].texto.startswith("PULIDO:")
    assert not outs[-1].texto_base.startswith("PULIDO:")


def test_refiner_falla_usa_texto_base(reloj):
    c = con_refiner(FakeRefiner(error=RuntimeError("sin red")), reloj)
    out = conversar(c, "de meissen a paraiso")[-1]
    assert out.texto == out.texto_base


def test_refiner_que_cambia_cifras_se_descarta(reloj):
    c = con_refiner(FakeRefiner(respuesta="Tardas 5 minutos, ¡suerte!"), reloj)
    out = conversar(c, "de meissen a paraiso")[-1]
    assert out.texto == out.texto_base


def test_refiner_lento_usa_texto_base(reloj):
    class Lento:
        async def refine(self, ctx):
            await asyncio.sleep(1)
            return "tarde"
    c = con_refiner(Lento(), reloj)
    c.assistant._timeout = 0.05
    out = conversar(c, "de meissen a paraiso")[-1]
    assert out.texto == out.texto_base


# --- Canales -------------------------------------------------------------------

def test_mismo_texto_base_en_todos_los_canales(container):
    web = conversar(container, "de meissen a paraiso", canal="web")[-1]
    tg = conversar(container, "de meissen a paraiso", canal="telegram")[-1]
    wa = conversar(container, "de meissen a paraiso", canal="whatsapp")[-1]
    assert web.texto_base == tg.texto_base == wa.texto_base


def test_render_por_canal(container):
    (out,) = conversar(container, "hola")
    assert render_telegram(out)["reply_markup"]["keyboard"] == [[{"text": "Guiada"}, {"text": "Manual"}]]
    assert "1. Guiada\n2. Manual" in render_whatsapp(out)


def test_web_chat_endpoint(client):
    assert client.post("/chat/web", json={"texto": "hola"}).status_code == 400
    h = {"X-Client-Id": "web-1"}
    assert client.post("/chat/web", json={"texto": "hola"}, headers=h).json()["paso"] == "inicio"
    assert client.post("/chat/web", json={"texto": "1"}, headers=h).json()["paso"] == "origen"


def test_telegram_webhook(client):
    update = {"update_id": 1, "message": {"message_id": 1, "from": {"id": 42, "first_name": "Ana"},
                                          "chat": {"id": 42}, "text": "hola"}}
    r = client.post("/webhooks/telegram", json=update)
    assert r.status_code == 200
    assert r.json()["respuesta"]["texto"].startswith("¡Hola Ana!")
    assert client.post("/webhooks/telegram", json={"update_id": 2}).json() == {"ok": True}


def test_whatsapp_webhook_y_verificacion(client, container):
    container.settings.whatsapp_verify_token = "tok"
    ok = client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "tok", "hub.challenge": "123"})
    assert ok.status_code == 200 and ok.text == "123"
    assert client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "x"}).status_code == 403

    payload = {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": "573001112233", "profile": {"name": "Luis"}}],
        "messages": [{"from": "573001112233", "type": "text", "text": {"body": "hay un derrumbe en paraiso"}}],
    }}]}]}
    r = client.post("/webhooks/whatsapp", json=payload)
    assert r.json()["respuestas"][0]["reporte"]["tipo"] == "derrumbe"


@pytest.mark.parametrize("texto", ["menu", "reiniciar", "inicio"])
def test_comandos_globales(container, texto):
    assert conversar(container, "manual", texto)[-1].paso == "inicio"
