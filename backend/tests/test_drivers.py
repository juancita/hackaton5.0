"""Módulo de conductores informales, login por celular, cámaras y viajes por chat."""

import pytest

from app.domain.errors import InvalidInput
from app.domain.reports import normalizar_telefono


def tg(client, uid, texto="", nombre="X", contact=None, loc=None):
    m = {"message_id": 1, "chat": {"id": uid}, "from": {"id": uid, "first_name": nombre}, "text": texto}
    if contact:
        m.pop("text"); m["contact"] = {"phone_number": contact, "user_id": uid}
    if loc:
        m.pop("text"); m["location"] = {"latitude": loc[0], "longitude": loc[1]}
    r = client.post("/webhooks/telegram", json={"update_id": 1, "message": m})
    assert r.status_code == 200
    return r.json().get("text") or r.json().get("caption") or ""


def test_telefono_normalizado_unifica_canales(container):
    assert normalizar_telefono("+57 300 123 4567") == normalizar_telefono("3001234567") == "3001234567"
    a = container.reports.actor_por_telefono("web", "3001234567")
    b = container.reports.actor_por_telefono("telegram", "573001234567")
    assert a.reporter_id == b.reporter_id


def test_login_y_modo(client):
    r = client.post("/auth/login", json={"telefono": "3001234567", "nombre": "Rosa", "modo": "conductor"})
    assert r.status_code == 200
    body = r.json()
    assert body["client_id"] == "tel:3001234567"
    assert body["perfil"]["nombre"] == "Rosa" and body["perfil"]["es_conductor"]
    p = client.post("/me/perfil", json={"modo": "pasajero"}, headers={"X-Client-Id": body["client_id"]}).json()
    assert p["modo"] == "pasajero"


def test_viaje_cupos_salida_y_lleno(container):
    d = container.drivers
    t = d.anunciar("cond", "Pedro", "mirador", "paraiso", "06:00", 2, "Jeep Paraíso")
    d.reservar(t.id, "p1", "Ana")
    d.reservar(t.id, "p1", "Ana")  # el mismo pasajero no duplica cupo
    t = d.reservar(t.id, "p2", "Luis")
    assert t.cupos_libres == 0 and t.lleno and t.esperando == 2
    with pytest.raises(InvalidInput):
        d.reservar(t.id, "p3", "Eva")
    with pytest.raises(InvalidInput):
        d.salir(t.id, "otro", None, None)  # solo el conductor
    t = d.salir(t.id, "cond", 4.58, -74.16)
    assert t.estado == "en_ruta" and t.lat == 4.58


def test_tendencia_y_horarios_offline(container):
    d = container.drivers
    for h in ("06:00", "06:00", "06:30"):
        d.anunciar("cond", "Pedro", "mirador", "paraiso", h, 5, "Jeep Paraíso")
    tend = d.tendencia("cond")
    assert tend["horas_frecuentes"][0] == "06:00" and tend["total"] == 3
    assert "06:00" in d.horarios_tipicos()["Jeep Paraíso"]


def test_camara_crea_incidente_verificado(client):
    r = client.post("/cameras/cam-villavicencio/lectura", json={"nivel": 0.9, "vehiculos": 50}).json()
    assert r["accion"] == "incidente" and r["confianza"] == 1.0
    assert client.post("/cameras/cam-villavicencio/lectura", json={"nivel": 0.3}).json()["accion"] == "sin_congestion"


def test_chat_telegram_conductor_y_pasajero(client):
    assert "¿Cómo vas a usar" in tg(client, 1, "/start", "Pedro")
    tg(client, 1, "📱 Compartir mi número", "Pedro", contact="+573001112233")
    assert "CONDUCTOR" in tg(client, 1, "🚙 Soy conductor", "Pedro")
    assert "publicado" in tg(client, 1, "salgo 6:30 de Mirador a Paraíso con 8 cupos", "Pedro")
    assert "PASAJERO" in tg(client, 2, "🧍 Soy pasajero", "Ana")
    assert "Próximos viajes" in tg(client, 2, "ver viajes", "Ana")
    assert "Cupo apartado" in tg(client, 2, "Apartar 1", "Ana")
    assert "En ruta" in tg(client, 1, "✅ Ya salí", "Pedro")
    assert "Desvío avisado" in tg(client, 1, "desvío por la 68 porque hay protesta", "Pedro")
    # La misma persona entra por la web con su número y ve su viaje
    cid = client.post("/auth/login", json={"telefono": "3001112233"}).json()["client_id"]
    assert len(client.get("/conductores/mios", headers={"X-Client-Id": cid}).json()) == 1


def test_chat_de_rutas_no_se_afecta(client):
    # Una consulta de ruta normal sigue yendo al asistente
    assert "La más rápida" in tg(client, 3, "de meissen a paraiso", "Luz")


def test_camara_bloquea_y_ruta_alternativa_avisa(client):
    # Guion del demo: la cámara de la subida a Paraíso detecta tráfico detenido
    assert client.post("/cameras/cam-paraiso/lectura", json={"nivel": 0.97}).json()["tipo"] == "bloqueo"
    plan = client.post("/routes", json={"origen_id": "paraiso", "destino_id": "tunal"}).json()
    rutas = [t["ruta"] for o in plan["opciones"] for t in o["tramos"]]
    assert "Jeep Paraíso" not in rutas                      # esquiva el tramo bloqueado
    assert plan["incidentes_evitados"]                      # y avisa que hubo un cierre en la ruta habitual


def test_ensueno_potosi_bajar_a_mitad_y_cortar(client, container):
    # El conductor publica; el recorrido se deduce de la ruta informal (pasa por Sierra Morena)
    assert "CONDUCTOR" in tg(client, 11, "🚙 Soy conductor", "Álvaro")
    texto = tg(client, 11, "salgo 6:30 de El Ensueño a Potosí con 10 cupos", "Álvaro")
    assert "Sierra Morena" in texto and "Potosí" in texto
    # Dos pasajeras: una se baja a mitad del trayecto
    tg(client, 12, "🧍 Soy pasajero", "Rosa")
    assert "Próximos viajes" in tg(client, 12, "colectivo a Potosí", "Rosa")
    assert "te bajas en Sierra Morena" in tg(client, 12, "apartar 1 bajo en Sierra Morena", "Rosa")
    tg(client, 13, "🧍 Soy pasajero", "Luz")
    tg(client, 13, "colectivo a Potosí", "Luz")
    tg(client, 13, "Apartar 1", "Luz")
    # El conductor corta en Sierra Morena: solo Luz (iba a Potosí) queda afectada
    assert "¿Hasta dónde llegas?" in tg(client, 11, "✂️ Cortar viaje", "Álvaro")
    assert "Avisé a 1 pasajero" in tg(client, 11, "✂️ Llego hasta Sierra Morena", "Álvaro")
    assert "Llega solo hasta Sierra Morena" in tg(client, 13, "ver viajes", "Luz")


def test_avisos_push_a_conductor_y_pasajeros(container):
    r = container.rides
    r.handle("telegram", "21", "🚙 Soy conductor", "Pedro")
    r.handle("telegram", "21", "salgo 6:00 de Mirador a Paraíso con 5 cupos", "Pedro")
    r.handle("telegram", "22", "ver viajes", "Ana")
    r.tomar_avisos()
    r.handle("telegram", "22", "Apartar 1", "Ana")
    assert [chat for chat, _ in r.tomar_avisos()] == ["21"]          # al conductor le llega la reserva
    r.handle("telegram", "21", "✅ Ya salí", "Pedro")
    avisos = r.tomar_avisos()
    assert [chat for chat, _ in avisos] == ["22"] and "ya salió" in avisos[0][1]  # a la pasajera, la salida


def test_mi_casa_por_ubicacion_y_ruta(client):
    assert "Enviar mi ubicación" in tg(client, 31, "🏡 Mi casa", "Rosa")
    assert "Guardado" in tg(client, 31, loc=(4.5689, -74.1703), nombre="Rosa")   # junto a Potosí
    texto = tg(client, 31, "de Meissen a mi casa", "Rosa")
    assert "Potosí" in texto or "La más rápida" in texto
