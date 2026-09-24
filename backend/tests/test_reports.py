import pytest

from app.domain.errors import Conflict, InvalidInput, RateLimited
from app.domain.models import IncidentState
from app.domain.reports import reporter_id_para
from app.domain.routing import clave_tramo
from tests.conftest import ADMIN_KEY

TRAMO = ("perdomo", "sierramorena", "sitp")


def usuario(c, n: int):
    return c.reports.actor_de_canal("web", f"cliente-{n}")


def test_identidad_anonima_y_estable(container):
    a, b = container.reports.actor_de_canal("whatsapp", "573001112233"), container.reports.actor_de_canal("whatsapp", "573001112233")
    assert a.reporter_id == b.reporter_id == reporter_id_para("whatsapp", "573001112233", "salt-test")
    assert "573001112233" not in a.reporter_id
    assert a.reporter_id != container.reports.actor_de_canal("telegram", "573001112233").reporter_id


def test_usuario_nuevo_pesa_04_y_penaliza_proporcional(container):
    inc = container.reports.reportar(usuario(container, 1), "trancon", *TRAMO)
    assert inc.confianza == pytest.approx(0.4)
    pen = container.reports.penalizaciones()[clave_tramo(*TRAMO)]
    assert pen.factor == pytest.approx(1.32)
    assert not pen.bloqueado


def test_reportes_iguales_se_fusionan(container):
    a = container.reports.reportar(usuario(container, 1), "trancon", *TRAMO)
    b = container.reports.reportar(usuario(container, 2), "trancon", "sierramorena", "perdomo")  # sentido inverso
    assert a.id == b.id
    assert b.confianza == pytest.approx(1 - 0.6 ** 2)
    assert len(container.reports.vigentes()) == 1


def test_antispam_por_reportero(container, reloj):
    container.reports.reportar(usuario(container, 1), "trancon", *TRAMO)
    with pytest.raises(RateLimited):
        container.reports.reportar(usuario(container, 1), "trancon", *TRAMO)
    reloj.avanzar(minutes=11)
    inc = container.reports.reportar(usuario(container, 1), "trancon", *TRAMO)
    assert len(inc.reports) == 1  # no suma dos veces al mismo incidente


def test_admin_verifica_al_reportar_y_bloquea(container):
    inc = container.reports.reportar(container.reports.actor_admin("ana"), "derrumbe", "mirador", "paraiso")
    assert inc.estado == IncidentState.verificado
    assert container.reports.penalizaciones()[clave_tramo("mirador", "paraiso", "jeep")].bloqueado


def test_bloqueo_de_usuario_solo_penaliza_hasta_confianza_alta(container):
    container.reports.reportar(usuario(container, 1), "derrumbe", "mirador", "paraiso")
    pen = container.reports.penalizaciones()[clave_tramo("mirador", "paraiso", "jeep")]
    assert not pen.bloqueado and pen.factor == pytest.approx(1 + 1.5 * 0.4)
    container.reports.reportar(usuario(container, 2), "derrumbe", "mirador", "paraiso")
    container.reports.reportar(usuario(container, 3), "derrumbe", "mirador", "paraiso")  # 1 - 0.6^3 = 0.784
    assert container.reports.penalizaciones()[clave_tramo("mirador", "paraiso", "jeep")].bloqueado


def test_niega_reduce_confianza_bajo_umbral(container):
    inc = container.reports.reportar(usuario(container, 1), "trancon", *TRAMO)
    inc = container.reports.votar(usuario(container, 2), inc.id, "niega")
    assert inc.confianza == pytest.approx(0.4 * 0.6)
    assert clave_tramo(*TRAMO) not in container.reports.penalizaciones()
    # cambiar el voto reemplaza el anterior
    inc = container.reports.votar(usuario(container, 2), inc.id, "confirma")
    assert len(inc.votes) == 1 and inc.confianza == pytest.approx(1 - 0.6 ** 2)


def test_verificar_y_rechazar_actualizan_reputacion(container):
    admin = container.reports.actor_admin()
    u1, u2 = usuario(container, 1), usuario(container, 2)
    inc = container.reports.reportar(u1, "trancon", *TRAMO)
    container.reports.votar(u2, inc.id, "niega")
    container.reports.verificar(admin, inc.id)
    assert container.reports.perfil(u1).aciertos == 1
    assert container.reports.perfil(u2).fallos == 1

    inc2 = container.reports.reportar(u2, "lleno", "tunal", "meissen")
    container.reports.rechazar(admin, inc2.id)
    p2 = container.reports.perfil(u2)
    assert p2.fallos == 2
    assert container.reports.perfil(u1).estrellas == 2.5  # u2 le dio 👎: (5 + 0) / 2
    with pytest.raises(Conflict):
        container.reports.votar(u1, inc2.id, "confirma")


def test_vencido_con_confianza_alta_premia_reporteros(container, reloj):
    for n in (1, 2, 3):
        container.reports.reportar(usuario(container, n), "lleno", "tunal", "meissen")  # conf 0.784
    reloj.avanzar(minutes=46)
    assert container.reports.vigentes() == []
    assert container.reports.perfil(usuario(container, 1)).aciertos == 1


def test_tramo_inexistente(container):
    with pytest.raises(InvalidInput):
        container.reports.reportar(usuario(container, 1), "trancon", "paraiso", "pasquilla")


# --- API ---------------------------------------------------------------------

def test_api_reporte_requiere_identidad(client):
    body = {"tipo": "trancon", "de_id": "perdomo", "a_id": "sierramorena"}
    assert client.post("/incidents", json=body).status_code == 400
    r = client.post("/incidents", json=body, headers={"X-Client-Id": "abc"})
    assert r.status_code == 201
    assert r.json()["confianza"] == pytest.approx(0.4) and r.json()["afecta_rutas"]
    assert client.post("/incidents", json=body, headers={"X-Client-Id": "abc"}).status_code == 429


def test_api_admin_requiere_clave(client):
    inc = client.post("/incidents", json={"tipo": "trancon", "de_id": "perdomo", "a_id": "sierramorena"},
                      headers={"X-Client-Id": "abc"}).json()
    assert client.post(f"/admin/incidents/{inc['id']}/verificar").status_code == 401
    assert client.post(f"/admin/incidents/{inc['id']}/verificar", headers={"X-Admin-Key": "mala"}).status_code == 401
    r = client.post(f"/admin/incidents/{inc['id']}/verificar", headers={"X-Admin-Key": ADMIN_KEY})
    assert r.status_code == 200 and r.json()["estado"] == "verificado"
    assert client.get("/reporters/me", headers={"X-Client-Id": "abc"}).json()["aciertos"] == 1
    assert client.delete("/admin/incidents").status_code == 401
    assert client.delete("/admin/incidents", headers={"X-Admin-Key": ADMIN_KEY}).json() == {"eliminados": 1}


def test_api_incidente_afecta_ruta(client):
    antes = client.post("/routes", json={"origen_id": "meissen", "destino_id": "paraiso"}).json()
    client.post("/incidents", json={"tipo": "derrumbe", "de_id": "lucero", "a_id": "paraiso"},
                headers={"X-Admin-Key": ADMIN_KEY})
    despues = client.post("/routes", json={"origen_id": "meissen", "destino_id": "paraiso"}).json()
    rutas = [t["ruta"] for o in despues["opciones"] for t in o["tramos"]]
    assert "Jeep Alto" not in rutas
    assert despues["opciones"][0]["totalMin"] > antes["opciones"][0]["totalMin"]
    assert len(despues["incidentes_aplicados"]) == 0  # el tramo bloqueado ya no está en ninguna opción


# --- Reporte por ubicación (tipo Waze) ------------------------------------------

def test_reporte_por_ubicacion_se_asigna_al_tramo_cercano(container):
    net = container.network
    t = net.tramos[0]
    de, a = net.lugar(t.de), net.lugar(t.a)
    punto = t.geom[len(t.geom) // 2] if t.geom else ((de.lat + a.lat) / 2, (de.lng + a.lng) / 2)
    inc = container.reports.reportar_aqui(usuario(container, 1), "trancon", punto[0], punto[1])
    cercano, dist = net.tramo_cercano(*punto)
    assert dist < 1 and {inc.de_id, inc.a_id} == {cercano.de, cercano.a}
    assert (inc.lat, inc.lng) == pytest.approx(punto)  # el pin queda donde se reportó


def test_reporte_lejos_de_la_red_se_rechaza(container):
    with pytest.raises(InvalidInput):
        container.reports.reportar_aqui(usuario(container, 1), "trancon", 4.711, -74.0721)  # centro de Bogotá


def test_api_reporte_por_ubicacion(client, container):
    p = container.network.lugar("perdomo")
    r = client.post("/incidents", json={"tipo": "trancon", "lat": p.lat, "lng": p.lng}, headers={"X-Client-Id": "abc"})
    assert r.status_code == 201 and (r.json()["lat"], r.json()["lng"]) == pytest.approx((p.lat, p.lng))
    assert client.post("/incidents", json={"tipo": "trancon"}, headers={"X-Client-Id": "abc"}).status_code == 422


def test_recientes_incluye_vencidos_y_excluye_rechazados(container, reloj):
    viejo = container.reports.reportar(usuario(container, 1), "lleno", *TRAMO)  # vive 45 min
    reloj.avanzar(minutes=60)
    nuevo = container.reports.reportar(usuario(container, 2), "trancon", *TRAMO)
    rechazado = container.reports.reportar(usuario(container, 3), "bloqueo", *TRAMO)
    container.reports.rechazar(container.reports.actor_admin(), rechazado.id)
    ids = [i.id for i in container.reports.recientes()]
    assert ids == [nuevo.id, viejo.id]  # más nuevo primero, sin el rechazado
    assert [i.id for i in container.reports.vigentes()] == [nuevo.id]
    assert not container.reports.vista(container.reports.recientes()[1]).vigente


def test_api_recientes(client, container):
    p = container.network.lugar("perdomo")
    client.post("/incidents", json={"tipo": "trancon", "lat": p.lat, "lng": p.lng}, headers={"X-Client-Id": "abc"})
    r = client.get("/incidents/recent?limit=5")
    assert r.status_code == 200 and len(r.json()) == 1 and r.json()[0]["vigente"]



def test_estrellas_las_da_la_comunidad(container):
    autor = usuario(container, 1)
    assert container.reports.perfil(autor).estrellas == 5  # todos empiezan con 5
    inc = container.reports.reportar(autor, "trancon", *TRAMO)
    container.reports.votar(usuario(container, 2), inc.id, "confirma")
    container.reports.votar(usuario(container, 3), inc.id, "niega")
    p = container.reports.perfil(autor)
    assert (p.likes, p.dislikes, p.estrellas) == (1, 1, pytest.approx(3.3))  # (5 + 5 + 0) / 3
    container.reports.votar(usuario(container, 3), inc.id, "confirma")  # cambiar el voto recalcula
    assert container.reports.perfil(autor).estrellas == 5
    with pytest.raises(Conflict):
        container.reports.votar(autor, inc.id, "confirma")  # no te calificas a ti mismo


def test_menos_estrellas_pesan_menos(container):
    autor = usuario(container, 1)
    inc = container.reports.reportar(autor, "trancon", *TRAMO)
    for n in (2, 3, 4):
        container.reports.votar(usuario(container, n), inc.id, "niega")
    assert container.reports.perfil(autor).estrellas == pytest.approx(1.2)  # 5 / 4
    otro = container.reports.reportar(autor, "lleno", "tunal", "meissen")
    assert otro.confianza == pytest.approx(0.1 + 0.3 * 1.2 / 5)


def test_recientes_pagina_hacia_atras(container, reloj):
    ids = []
    for n, tipo in enumerate(("trancon", "lleno", "novedad")):
        ids.append(container.reports.reportar(usuario(container, n), tipo, *TRAMO).id)
        reloj.avanzar(minutes=25)
    primera = container.reports.recientes(horas=1)
    assert [i.id for i in primera] == [ids[2], ids[1]]
    mas = container.reports.recientes(horas=None, antes=primera[-1].creado_en)
    assert [i.id for i in mas] == [ids[0]]
