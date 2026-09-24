def test_mei_sugiere_meissen_primero(container):
    ids = [s.id for s in container.places.suggest("Mei")]
    assert ids[0] == "meissen"
    assert "hospital" in ids


def test_ignora_tildes_y_mayusculas(container):
    assert "paraiso" in [s.id for s in container.places.suggest("PARAI")]
    assert "paraiso" in [s.id for s in container.places.suggest("paraí")]


def test_sugiere_por_alias(container):
    res = container.places.suggest("mercado")
    plaza = next(s for s in res if s.id == "plaza")
    assert plaza.via == "nombre"  # "Plaza de mercado Perdomo" contiene una palabra que empieza por "mercado"
    assert next(s for s in container.places.suggest("univer") if s.id == "udtecno").via == "alias"


def test_texto_corto_devuelve_populares(container):
    tipos = {s.tipo for s in container.places.suggest("m")}
    assert tipos <= {"portal", "salud", "cable"}


def test_limite_y_sin_repetidos(container):
    res = container.places.suggest("a", 3)
    assert len(res) <= 3
    todos = container.places.suggest("er", 20)
    assert len({s.id for s in todos}) == len(todos)


def test_resolve_exacto_ambiguo_ninguno(container):
    assert container.places.resolve("meissen").lugar.id == "meissen"
    assert container.places.resolve("hospital meissen").lugar.id == "hospital"
    assert container.places.resolve("juan").lugar.id == "juanpablo"
    assert container.places.resolve("me").estado == "ambiguo"
    assert container.places.resolve("marte").estado == "ninguno"


def test_menciones_en_texto_libre(container):
    ids = [p.id for p in container.places.menciones("hay trancón entre perdomo y sierra morena")]
    assert ids == ["perdomo", "sierramorena"]


def test_endpoint_suggest(client):
    r = client.get("/places/suggest", params={"q": "Mei"})
    assert r.status_code == 200
    assert r.json()[0]["nombre"] == "Meissen"
