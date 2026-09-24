"""Integración con PostgreSQL. Requiere: docker compose up -d db.

Se ejecutan con `pytest -m pg`; si la BD no responde se omiten.
Usan su PROPIA base (`muevete_test`, o TEST_DATABASE_URL): la crean y migran solas y la vacían
entre pruebas. Nunca tocan la base de la app (`muevete`), donde viven los reportes reales.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text

from app.adapters.outbound.pg.db import make_session_factory
from app.adapters.outbound.pg.repos import PgIncidentRepository, PgReporterRepository
from app.adapters.outbound.refiners import NoopRefiner
from app.container import build_container
from app.main import create_app
from tests.conftest import ADMIN_KEY, make_settings

pytestmark = pytest.mark.pg

DB_URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://muevete:muevete@localhost:5432/muevete_test")
BACKEND = Path(__file__).resolve().parents[1]


def _preparar_bd_de_pruebas() -> None:
    """Crea la base de pruebas si no existe y le aplica las migraciones."""
    url = make_url(DB_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        if not c.execute(text("select 1 from pg_database where datname = :n"), {"n": url.database}).scalar():
            c.execute(text(f'create database "{url.database}"'))
    admin.dispose()
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True,
                   env={**os.environ, "DATABASE_URL": DB_URL}, capture_output=True)


@pytest.fixture(scope="module")
def sessions():
    if not (make_url(DB_URL).database or "").endswith("_test"):
        # Estas pruebas hacen TRUNCATE: jamás contra la base de la app
        pytest.exit(f"TEST_DATABASE_URL debe apuntar a una base *_test, no a {make_url(DB_URL).database!r}", returncode=2)
    try:
        _preparar_bd_de_pruebas()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"PostgreSQL no disponible: {e}")
    return make_session_factory(DB_URL)


def _truncar(sessions) -> None:
    with sessions.begin() as s:
        s.execute(text("truncate votes, reports, incidents, reporters cascade"))


@pytest.fixture
def limpio(sessions):
    """Deja las tablas vacías antes y después (solo en la base de pruebas)."""
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
        assert me["aciertos"] == 1 and me["estrellas"] == 5
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


def test_estrellas_por_votos_de_la_comunidad(limpio):
    with nuevo_cliente(limpio) as api:
        inc = api.post("/incidents", json={"tipo": "trancon", "de_id": "tunal", "a_id": "meissen"},
                       headers={"X-Client-Id": "autor"}).json()
        api.post(f"/incidents/{inc['id']}/votos", json={"valor": "confirma"}, headers={"X-Client-Id": "b"})
        api.post(f"/incidents/{inc['id']}/votos", json={"valor": "niega"}, headers={"X-Client-Id": "c"})
        me = api.get("/reporters/me", headers={"X-Client-Id": "autor"}).json()
        assert (me["likes"], me["dislikes"], me["estrellas"]) == (1, 1, 3.3)
        assert api.get("/incidents/recent?horas=1").json()[0]["estrellas_autor"] == 3.3
