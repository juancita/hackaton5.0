import asyncio
from urllib.parse import parse_qs, urlparse

import pytest

from app.domain import mapas
from app.domain.errors import InvalidInput
from app.domain.models import InboundMessage

MEISSEN = (4.5597, -74.1378)  # a ~20 m del paradero de Meissen


def conversar(container, *mensajes, canal="web", user="u1"):
    """Cada mensaje es texto o una tupla (lat, lng) de ubicación compartida."""
    async def run():
        return [
            await container.assistant.handle(InboundMessage(
                canal=canal, user_id=user,
                texto=m if isinstance(m, str) else "",
                ubicacion=None if isinstance(m, str) else m,
            ))
            for m in mensajes
        ]
    return asyncio.run(run())


@pytest.fixture
def ruta(container):
    plan = container.trip.ejecutar("meissen", "paraiso", "barato")
    return plan.opciones[plan.recomendada]


def test_codificar_y_decodificar_recorren_la_misma_ruta(container, ruta):
    codigo = mapas.codificar(ruta, container.network)
    pasos = mapas.decodificar(codigo, container.network)
    assert pasos[0][1] == ruta.origen and pasos[-1][2] == ruta.destino
    mapa = mapas.construir(codigo, container.network, MEISSEN)
    assert mapa.origen.nombre == "Meissen" and mapa.ubicacion == MEISSEN
    assert len(mapa.lineas) == len(pasos) and {n for n, _ in mapa.modos}


@pytest.mark.parametrize("codigo", ["", "marte:1", "meissen:", "meissen:9999", "meissen:a.b", "meissen:0"])
def test_codigo_invalido(container, codigo):
    with pytest.raises(InvalidInput):
        mapas.decodificar(codigo, container.network)


def test_google_maps_pasa_por_los_transbordos_y_sale_de_la_ubicacion(container, ruta):
    codigo = mapas.codificar(ruta, container.network)
    q = parse_qs(urlparse(mapas.google_maps(codigo, container.network)).query)
    b = container.network.lugar("paraiso")
    assert q["destination"] == [f"{b.lat:.6f},{b.lng:.6f}"]
    cerca = (MEISSEN[0] + 0.004, MEISSEN[1])  # ~450 m del paradero de salida
    q = parse_qs(urlparse(mapas.google_maps(codigo, container.network, cerca)).query)
    assert q["origin"] == [f"{cerca[0]:.6f},{cerca[1]:.6f}"]


def test_endpoint_devuelve_la_imagen(client, container, ruta):
    codigo = mapas.codificar(ruta, container.network)
    r = client.get("/mapas/ruta.jpg", params={"r": codigo, "u": "4.5585,-74.1385"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.content[:3] == b"\xff\xd8\xff"
    assert client.get("/mapas/ruta.jpg", params={"r": "meissen:9999"}).status_code == 422


# --- Asistente -------------------------------------------------------------------

def test_resultado_trae_mapa_y_google_maps(container):
    out = conversar(container, "guiada", "meissen", "paraiso", "barato")[-1]
    assert out.mapa and out.mapa.google_maps.startswith("https://www.google.com/maps/dir/")
    assert out.mapa.ubicacion is None


def test_ubicacion_como_origen(container):
    outs = conversar(container, "guiada", MEISSEN, "paraiso", "barato")
    assert outs[1].paso == "destino" and "Meissen" in outs[1].texto
    assert outs[-1].plan.origen.id == "meissen" and outs[-1].mapa.ubicacion == MEISSEN
    assert "ubicacion" not in [o.id for o in outs[-1].opciones_rapidas]


def test_ubicacion_lejana_no_se_toma_como_origen(container):
    out = conversar(container, "guiada", (6.2442, -75.5812))[-1]  # Medellín
    assert out.paso == "origen" and "está a" in out.texto


def test_marcar_ubicacion_en_el_resultado(container):
    outs = conversar(container, "guiada", "meissen", "paraiso", "barato", MEISSEN)
    assert outs[-1].paso == "resultado" and outs[-1].texto.startswith("📍 ¡Listo!")
    assert outs[-1].mapa.ubicacion == MEISSEN


def test_boton_de_ubicacion_sin_coordenadas_explica_como_compartirla(container):
    out = conversar(container, "guiada", "📍 Usar mi ubicación")[-1]
    assert out.paso == "origen" and "📎" in out.texto


def test_ultimos_incidentes(container):
    vacio = conversar(container, "hola", "📋 Últimos incidentes")[-1]
    assert "No hay incidentes" in vacio.texto
    conversar(container, "hay un derrumbe en paraiso", user="vecino")
    out = conversar(container, "incidentes")[-1]
    assert out.paso == "inicio" and "Derrumbe" in out.texto and "1." in out.texto
    assert [o.id for o in out.opciones_rapidas] == ["guiada", "manual", "reportar", "incidentes", "ver_viajes", "soy_conductor", "mi_casa"]


# --- Telegram ----------------------------------------------------------------------

def _update(texto="", ubicacion=None):
    msg = {"message_id": 1, "from": {"id": 7, "first_name": "Ana"}, "chat": {"id": 7}, "text": texto}
    if ubicacion:
        msg["location"] = {"latitude": ubicacion[0], "longitude": ubicacion[1]}
    return {"update_id": 1, "message": msg}


def test_telegram_envia_foto_con_enlace_a_google_maps(client):
    for t in ("guiada", "meissen", "paraiso"):
        client.post("/webhooks/telegram", json=_update(t))
    r = client.post("/webhooks/telegram", json=_update("barato")).json()
    assert r["method"] == "sendPhoto" and r["parse_mode"] == "HTML"
    assert "/mapas/ruta.jpg?r=meissen" in r["photo"]
    assert 'href="https://www.google.com/maps/dir/' in r["caption"]
    assert client.get(r["photo"].replace("http://testserver", "")).status_code == 200


def test_telegram_boton_de_ubicacion_y_mensaje_de_ubicacion(client):
    r = client.post("/webhooks/telegram", json=_update("guiada")).json()
    botones = [b for fila in r["reply_markup"]["keyboard"] for b in fila]
    assert {"text": "📍 Usar mi ubicación", "request_location": True} in botones
    r = client.post("/webhooks/telegram", json=_update(ubicacion=MEISSEN)).json()
    assert "Meissen" in r["text"] and "Paso 2 de 3" in r["text"]
