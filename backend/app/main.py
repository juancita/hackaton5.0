"""App FastAPI de Muévete CB. Ejecutar: uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters.inbound import chat_channels, http_api
from app.config import get_settings
from app.container import Container, build_container
from app.domain.errors import Conflict, DomainError, InvalidInput, NotFound, RateLimited

STATUS = {NotFound: 404, InvalidInput: 422, Conflict: 409, RateLimited: 429}


def create_app(container: Container | None = None, http_client: httpx.AsyncClient | None = None) -> FastAPI:
    container = container or build_container(get_settings())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.http = http_client or httpx.AsyncClient(timeout=10)
        yield
        await app.state.http.aclose()

    app = FastAPI(title="Muévete CB API", version="0.1.0", lifespan=lifespan)
    app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in container.settings.cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=STATUS.get(type(exc), 400))

    app.include_router(http_api.router)
    app.include_router(chat_channels.router)
    return app


app = create_app()
