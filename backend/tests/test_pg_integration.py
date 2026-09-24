"""Integración con PostgreSQL. Requiere: docker compose up -d db && alembic upgrade head.

Se ejecutan con `pytest -m pg`; si la BD no responde se omiten.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.adapters.outbound.pg.db import make_session_factory
from app.adapters.outbound.pg.repos import PgIncidentRepository, PgReporterRepository
from app.adapters.outbound.refiners import NoopRefiner
from app.container import build_container
from app.main import create_app
from tests.conftest import ADMIN_KEY, make_settings

pytestmark = pytest.mark.pg

DB_URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://muevete:muevete@localhost:5432/muevete")


@pytest.fixture(scope="module")
def sessions():
    factory = make_session_factory(DB_URL)
    try:
        with factory() as s:
            s.execute(text("select 1 from reporters limit 1"))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"PostgreSQL no disponible o sin migrar: {e}")
    return factory


def _truncar(sessions) -> None:
    with sessions.begin() as s:
        s.execute(text("truncate votes, reports, incidents, reporters cascade"))


@pytest.fixture
def limpio(sessions):
    """Deja las tablas vacías antes y después (usa TEST_DATABASE_URL para no tocar la BD de desarrollo)."""
    _truncar(sessions)
    yield sessions
    _truncar(sessions)


def nuevo_cliente(sessions) -> TestClient:
    """Una 'instancia' nueva de la API sobre la misma BD (simula un reinicio)."""
    c = build_container(make_settings(), incidents=PgIncidentRepository(sessions),
                        reporters=PgReporterRepository(sessions), refiner=NoopRefiner())
    return TestClient(create_app(c))


def test_reportero_se_crea_solo_y_se_reutiliza(limpio):
    cid = str(uuid.uuid4())
    with nuevo_cliente(limpio) as api:
        body = {"tipo": "trancon", "de_id": "perdomo", "a_id": "sierramorena"}
        r1 = api.post("/incidents", json=body, headers={"X-Client-Id": cid})
        assert r1.status_code == 201
        r2 = api.post("/incidents", json={**body, "tipo": "lleno"}, headers={"X-Client-Id": cid})
        assert r2.status_code == 201
    with limpio() as s:
        assert s.execute(text("select count(*) from reporters where rol = 'usuario'")).scalar() == 1
        assert s.execute(text("select count(*) from reports")).scalar() == 2


def test_reputacion_persiste_tras_reinicio(limpio):
    with nuevo_cliente(limpio) as api:
        inc = api.post("/incidents", json={"tipo": "trancon", "de_id": "tunal", "a_id": "meissen"},
                       headers={"X-Client-Id": "vecino"}).json()
        api.post(f"/admin/incidents/{inc['id']}/verificar", headers={"X-Admin-Key": ADMIN_KEY})
    with nuevo_cliente(limpio) as api:
        me = api.get("/reporters/me", headers={"X-Client-Id": "vecino"}).json()
        assert me["aciertos"] == 1 and me["peso"] > 0.4
        assert api.get("/incidents").json()[0]["estado"] == "verificado"


def test_voto_repetido_no_duplica_filas(limpio):
    with nuevo_cliente(limpio) as api:
        inc = api.post("/incidents", json={"tipo": "trancon", "de_id": "tunal", "a_id": "meissen"},
                       headers={"X-Client-Id": "a"}).json()
        api.post(f"/incidents/{inc['id']}/votos", json={"valor": "confirma"}, headers={"X-Client-Id": "b"})
        r = api.post(f"/incidents/{inc['id']}/votos", json={"valor": "niega"}, headers={"X-Client-Id": "b"})
        assert r.json()["n_niega"] == 1 and r.json()["n_confirma"] == 0
    with limpio() as s:
        assert s.execute(text("select count(*) from votes")).scalar() == 1


def test_unique_de_votos_en_bd(limpio):
    import sqlalchemy.exc

    with nuevo_cliente(limpio) as api:
        inc = api.post("/incidents", json={"tipo": "trancon", "de_id": "tunal", "a_id": "meissen"},
                       headers={"X-Client-Id": "a"}).json()
    rid = PgIncidentRepository(limpio).get(inc["id"]).reports[0].reporter_id
    insert = text("insert into votes (incident_id, reporter_id, valor, peso, creado_en) values (:i, :r, 'confirma', 0.4, now())")
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        with limpio.begin() as s:
            s.execute(insert, {"i": inc["id"], "r": rid})
            s.execute(insert, {"i": inc["id"], "r": rid})
