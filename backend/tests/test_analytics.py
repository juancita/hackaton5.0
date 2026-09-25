"""Tablero de analítica del administrador: cifras agregadas, anonimato, IA opcional y datos ficticios."""

import json
from datetime import timedelta

from app.domain.analytics import K_ANONIMATO, modo_principal
from app.domain.drivers import RouteEvent, SeatRequest, Trip
from app.domain.models import Leg, PlaceRef, RouteOption, TripPlan
from tests.conftest import ADMIN_KEY

ADMIN = {"X-Admin-Key": ADMIN_KEY}


def _evento(container, reloj, rid, o, d, modo="colectivo", final=None, horas_atras=2, canal="telegram"):
    container.drivers._repo.add_route_event(RouteEvent(
        reporter_id=rid, origen_id=o, destino_id=d, canal=canal, prioridad="barato", modo=modo,
        destino_final=final, creado_en=reloj() - timedelta(hours=horas_atras)))


def _opcion(*modos):
    return RouteOption(origen="a", destino="b", totalMin=30, totalCop=0, transbordos=0, usaInformal=False, alertas=[],
                       tramos=[Leg(modo=m, ruta="r", desde="a", hasta="b", min=10, cop=0, espera=0, paradas=["a", "b"])
                               for m in modos])


def test_modo_principal_prioriza_informal_y_cable():
    plan = lambda *m: TripPlan(origen=PlaceRef(id="a", nombre="A"), destino=PlaceRef(id="b", nombre="B"),  # noqa: E731
                               opciones=[_opcion(*m)])
    assert modo_principal(plan("caminando", "cable", "sitp")) == "cable"
    assert modo_principal(plan("sitp", "jeep")) == "jeep"
    assert modo_principal(plan("caminando")) == "caminando"


def test_tablero_agrega_y_protege_flujos_pequenos(container, reloj):
    for i in range(8):  # flujo con suficientes personas: se muestra
        _evento(container, reloj, f"u{i}", "potosi", "ensueno", final="kennedy")
    for i in range(K_ANONIMATO - 1):  # flujo con pocas personas: se agrupa (no aparece)
        _evento(container, reloj, f"x{i}", "quiba", "tunal", modo="veredal", final="centro")
    d = container.analytics.tablero(30)
    assert d["kpis"]["consultas"] == 8 + K_ANONIMATO - 1
    assert d["kpis"]["usuarios_activos"] == 8 + K_ANONIMATO - 1
    flujos = {(f["origen_id"], f["salida_id"]) for f in d["flujos"]}
    assert ("potosi", "ensueno") in flujos and ("quiba", "tunal") not in flujos
    assert all(p["n"] >= K_ANONIMATO for p in d["pares"])
    assert d["salidas"][0]["id"] == "ensueno"
    assert {m["modo"] for m in d["medios"]} == {"informal"}
    # Ningún dato personal en el tablero
    texto = json.dumps(d, ensure_ascii=False)
    assert "u1" not in texto and "reporter_id" not in texto


def test_rutas_informales_cortes_y_bajadas(container, reloj):
    repo = container.drivers._repo
    for k in range(20):
        t = Trip(id=f"t{k}", driver_id="c1", driver_nombre="W", ruta="Colectivo El Ensueño - Sierra Morena - Potosí",
                 origen_id="ensueno", destino_id="potosi", hora="06:10", cupos_total=10, cupos_libres=0, lleno=True,
                 estado="finalizado", paradas=["ensueno", "sierramorena", "potosi"],
                 corta_en="sierramorena" if k < 5 else None, creado_en=reloj() - timedelta(days=1))
        repo.create_trip(t)
        repo.add_seat(SeatRequest(id=f"s{k}", trip_id=t.id, passenger_id="p", baja_en="sierramorena" if k % 2 else "potosi",
                                  creado_en=t.creado_en))
    d = container.analytics.tablero(30)
    r = d["rutas_informales"][0]
    assert r["cortados_pct"] == 25.0 and r["corte_frecuente"] == "Sierra Morena"
    assert r["bajan_antes_pct"] == 50.0 and r["ocupacion_pct"] == 100.0
    assert any("se corta" in i["texto"] for i in d["insights"])


def test_tablero_solo_admin_y_resumen_sin_ia(client, container, reloj):
    for i in range(6):
        _evento(container, reloj, f"u{i}", "lucero", "tunal", final="centro")
    assert client.get("/admin/tablero").status_code == 401
    assert client.get("/admin/tablero", headers={"X-Admin-Key": "mala"}).status_code == 401
    d = client.get("/admin/tablero?dias=30", headers=ADMIN).json()
    assert d["kpis"]["consultas"] == 6
    r = client.get("/admin/tablero/resumen", headers=ADMIN).json()
    assert r["fuente"] == "reglas" and r["texto"]
    csv = client.get("/admin/tablero.csv", headers=ADMIN)
    assert csv.status_code == 200 and "salida_de_la_localidad" in csv.text and "Portal Tunal" in csv.text


def test_consulta_de_ruta_guarda_prioridad_y_medio(client, container):
    client.post("/routes", json={"origen_id": "paraiso", "destino_id": "tunal", "prioridad": "rapido"},
                headers={"X-Client-Id": "vecino-1"})
    ev = container.drivers._repo._events[-1]
    assert ev.prioridad == "rapido" and ev.modo in ("cable", "jeep", "colectivo", "sitp")


def test_generador_de_datos_ficticios(container):
    from scripts.seed_analitica import Generador

    ahora = container.drivers._now()
    f = Generador(container, ahora, dias=14).generar()
    assert len(f["events"]) > 1000 and len(f["trips"]) > 300 and f["incidents"]
    assert all(r["id"].startswith("demo:") for r in f["reporters"])
    assert all(i["id"].startswith("demo-") for i in f["incidents"])
    assert all(e["creado_en"] <= ahora for e in f["events"])
    assert all(i["creado_en"] <= ahora - timedelta(hours=3) for i in f["incidents"])  # nunca son alertas vigentes
    assert all(t["estado"] == "finalizado" for t in f["trips"])  # no aparecen como viajes próximos


def test_clave_admin_con_tildes_y_espacios(reloj):
    from urllib.parse import quote

    from fastapi.testclient import TestClient

    from app.adapters.outbound.memory_repos import MemoryIncidentRepository, MemoryReporterRepository
    from app.adapters.outbound.refiners import NoopRefiner
    from app.container import build_container
    from app.main import create_app
    from tests.conftest import make_settings

    clave = "la loma de Ciudad Bolívar sí se mueve ñ"
    c = build_container(make_settings().model_copy(update={"admin_api_key": clave}), incidents=MemoryIncidentRepository(),
                        reporters=MemoryReporterRepository(), refiner=NoopRefiner(), clock=reloj)
    with TestClient(create_app(c)) as api:
        assert api.get("/admin/tablero", headers={"X-Admin-Key": quote(clave)}).status_code == 200  # así la envía la web
        assert api.get("/admin/tablero", headers={"X-Admin-Key": clave.encode()}).status_code == 200  # UTF-8 crudo
        assert api.get("/admin/tablero", headers={"X-Admin-Key": quote("otra clave")}).status_code == 401
