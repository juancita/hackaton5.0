import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.domain.models import Penalty
from app.domain.routing import clave_tramo

WEB_JS = Path(__file__).resolve().parents[2] / "web" / "js"

NODE_SCRIPT = """
global.window = {};
const fs = require('fs');
for (const f of ['data.js', 'engine.js']) eval(fs.readFileSync(process.argv[1] + '/' + f, 'utf8'));
const { PARADEROS } = window.DB, out = {};
for (const a of PARADEROS) for (const b of PARADEROS) for (const p of ['rapido', 'barato', 'transbordos']) {
  const r = window.Engine.mejorRuta(a.id, b.id, p);
  out[`${a.id}|${b.id}|${p}`] = r && { rutas: r.tramos.map(t => t.ruta), totalMin: r.totalMin, totalCop: r.totalCop };
}
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="se necesita node para comparar con engine.js")
def test_paridad_con_engine_js(container):
    """El port en Python devuelve exactamente las mismas rutas que el motor del front, para todos los pares."""
    res = subprocess.run(["node", "-e", NODE_SCRIPT, str(WEB_JS)], capture_output=True, text=True, encoding="utf-8", check=True)
    esperado = json.loads(res.stdout)
    for clave, js in esperado.items():
        o, d, p = clave.split("|")
        py = container.routing.mejor_ruta(o, d, p)
        if js is None:
            assert py is None, clave
        else:
            assert [t.ruta for t in py.tramos] == js["rutas"], clave
            assert (py.totalMin, py.totalCop) == (js["totalMin"], js["totalCop"]), clave


def test_opciones_sin_duplicados(container):
    ops = container.routing.opciones("meissen", "paraiso")
    firmas = [">".join(t.ruta for t in o.tramos) for o in ops]
    assert len(firmas) == len(set(firmas))
    assert ops[0].etiqueta == "La más rápida"


def test_tramo_bloqueado_se_excluye(container):
    pen = {clave_tramo("mirador", "paraiso", "jeep"): Penalty(bloqueado=True, motivo="derrumbe")}
    r = container.routing.mejor_ruta("meissen", "paraiso", "rapido", pen)
    assert "Jeep Paraíso" not in [t.ruta for t in r.tramos]


def test_penalizacion_en_sentido_inverso(container):
    # Solo formal: desde que existe el colectivo El Ensueño - Sierra Morena - Potosí, con trancón el
    # motor puede esquivar el SITP; aquí se prueba que la penalización aplica en ambos sentidos.
    formal = frozenset({"sitp", "alimentador", "troncal", "cable"})
    base = container.routing.mejor_ruta("perdomo", "sierramorena", modos=formal)
    pen = {clave_tramo("sierramorena", "perdomo", "sitp"): Penalty(factor=3, motivo="trancón")}
    r = container.routing.mejor_ruta("perdomo", "sierramorena", "rapido", pen, modos=formal)
    assert r.totalMin > base.totalMin
    assert r.alertas == ["trancón"]


def test_empate_de_prioridades_conserva_la_pedida(container):
    """Si la más barata es la misma que la más rápida, el usuario que pidió 'barato' la ve así."""
    rapida = container.routing.mejor_ruta("meissen", "paraiso", "rapido")
    barata = container.routing.mejor_ruta("meissen", "paraiso", "barato")
    assert [t.ruta for t in rapida.tramos] == [t.ruta for t in barata.tramos]
    prios = [o.prioridad for o in container.routing.opciones("meissen", "paraiso", preferida="barato")]
    assert "barato" in prios and "rapido" not in prios


def test_endpoint_routes(client):
    r = client.post("/routes", json={"origen_id": "Meissen ", "destino_id": "paraiso", "prioridad": "barato"})
    assert r.status_code == 200
    plan = r.json()
    assert plan["origen"]["nombre"] == "Meissen"
    assert plan["opciones"][plan["recomendada"]]["prioridad"] == "barato"


@pytest.mark.parametrize("body,status", [
    ({"origen_id": "marte", "destino_id": "paraiso"}, 404),
    ({"origen_id": "paraiso", "destino_id": "paraiso"}, 422),
    ({"origen_id": "meissen", "destino_id": "paraiso", "prioridad": "volando"}, 422),
])
def test_endpoint_routes_errores(client, body, status):
    assert client.post("/routes", json=body).status_code == status


def test_network_incluye_camaras(client):
    data = client.get("/network").json()
    assert len(data["camaras"]) == 4
    assert {"modos", "paraderos", "tramos"} <= data.keys()


def test_filtro_de_modos(container):
    """Si la persona no quiere el cable, la ruta sale sin cable (caminar siempre se permite)."""
    con_cable = container.routing.mejor_ruta("tunal", "juanpablo")
    assert [t.modo for t in con_cable.tramos] == ["cable"]
    solo_bus = container.routing.mejor_ruta("tunal", "juanpablo", modos=frozenset({"sitp", "alimentador"}))
    assert solo_bus and {t.modo for t in solo_bus.tramos} <= {"sitp", "alimentador", "caminando"}


def test_opciones_incluyen_alternativa_sin_el_medio_principal(container):
    ops = container.routing.opciones("tunal", "juanpablo")
    sin_cable = next(o for o in ops if o.etiqueta == "Sin TransMiCable")
    assert "cable" not in {t.modo for t in sin_cable.tramos}


def test_endpoint_routes_con_modos(client):
    r = client.post("/routes", json={"origen_id": "tunal", "destino_id": "juanpablo", "modos": ["sitp", "alimentador"]})
    assert r.status_code == 200
    for op in r.json()["opciones"]:
        assert {t["modo"] for t in op["tramos"]} <= {"sitp", "alimentador", "caminando"}
    assert client.post("/routes", json={"origen_id": "tunal", "destino_id": "juanpablo", "modos": ["ovni"]}).status_code == 422


@pytest.mark.parametrize("destino,ruta", [
    ("bellaflor", "Jeep Bella Flor"), ("caracoli", "Colectivo Caracolí"), ("santodomingo", "Colectivo Santo Domingo"),
    ("tesoro", "Colectivo El Tesoro"), ("quibaalta", "Jeep Quiba Alta"), ("mochueloalto", "Veredal Mochuelo Alto"),
])
def test_barrios_altos_y_veredas_llegan_en_informal(container, destino, ruta):
    r = container.routing.mejor_ruta("tunal", destino)
    assert r and ruta in [t.ruta for t in r.tramos]


def test_opcion_con_transporte_informal(container):
    """Si ninguna opción usa informal, igual aparece una alternativa con jeep/colectivo/veredal."""
    ops = container.routing.opciones("tunal", "paraiso")
    assert any(o.usaInformal for o in ops)
    con = [o for o in ops if o.etiqueta == "Con transporte informal"]
    assert all(o.usaInformal for o in con)
