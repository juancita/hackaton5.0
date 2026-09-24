from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.adapters.outbound.memory_repos import MemoryIncidentRepository, MemoryReporterRepository
from app.adapters.outbound.refiners import NoopRefiner
from app.config import Settings
from app.container import build_container
from app.domain.models import RefineContext
from app.main import create_app

ADMIN_KEY = "clave-admin-test"


class Reloj:
    """Reloj controlable para probar vencimientos y ventanas de tiempo."""

    def __init__(self):
        self.ahora = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.ahora

    def avanzar(self, **kw) -> None:
        self.ahora += timedelta(**kw)


class FakeRefiner:
    def __init__(self, respuesta: str | None = None, error: Exception | None = None):
        self.respuesta, self.error, self.llamadas = respuesta, error, []

    async def refine(self, ctx: RefineContext) -> str:
        self.llamadas.append(ctx)
        if self.error:
            raise self.error
        return self.respuesta if self.respuesta is not None else f"PULIDO: {ctx.texto_base}"


def make_settings(**kw) -> Settings:
    return Settings(_env_file=None, storage="memory", admin_api_key=ADMIN_KEY, id_salt="salt-test", **kw)


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def container(reloj):
    return build_container(
        make_settings(),
        incidents=MemoryIncidentRepository(),
        reporters=MemoryReporterRepository(),
        refiner=NoopRefiner(),
        clock=reloj,
    )


@pytest.fixture
def client(container):
    with TestClient(create_app(container)) as c:
        yield c
