"""Dependencias HTTP compartidas: contenedor e identidad (usuario anónimo o admin)."""

import secrets

from fastapi import Depends, Header, HTTPException, Request

from app.container import Container
from app.domain.models import Actor


def get_container(request: Request) -> Container:
    return request.app.state.container


def _es_admin(c: Container, key: str | None) -> bool:
    esperado = c.settings.admin_api_key
    return bool(esperado and key and secrets.compare_digest(key, esperado))


def get_actor(
    c: Container = Depends(get_container),
    x_client_id: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
    x_admin_name: str | None = Header(default=None),
) -> Actor:
    """Admin si trae una X-Admin-Key válida; si no, usuario identificado por X-Client-Id (sin cuenta)."""
    if _es_admin(c, x_admin_key):
        return c.reports.actor_admin(x_admin_name)
    if x_client_id and x_client_id.strip():
        cid = x_client_id.strip()[:128]
        # Login por celular: "tel:<numero>" da identidad UNIFICADA (misma persona en app y Telegram)
        if cid.startswith("tel:"):
            return c.reports.actor_por_telefono("web", cid[4:])
        return c.reports.actor_de_canal("web", cid)
    if x_admin_key:
        raise HTTPException(401, "X-Admin-Key inválida")
    raise HTTPException(400, "Falta el header X-Client-Id")


def get_viewer_id(
    c: Container = Depends(get_container),
    x_client_id: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
    x_admin_name: str | None = Header(default=None),
) -> str | None:
    """Identidad opcional para lecturas: marca en las vistas los reportes y votos de quien consulta."""
    try:
        return get_actor(c, x_client_id, x_admin_key, x_admin_name).reporter_id
    except HTTPException:
        return None


def require_admin(
    c: Container = Depends(get_container),
    x_admin_key: str | None = Header(default=None),
    x_admin_name: str | None = Header(default=None),
) -> Actor:
    if not _es_admin(c, x_admin_key):
        raise HTTPException(401, "Se requiere X-Admin-Key válida")
    return c.reports.actor_admin(x_admin_name)
