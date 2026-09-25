"""Analítica: cada consulta de ruta guarda prioridad, medio principal y destino final (tablero para entidades)

Revision ID: 0004_analitica
Revises: 0003_paradas
Create Date: 2026-09-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_analitica"
down_revision = "0003_paradas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("route_events", sa.Column("prioridad", sa.String(16), nullable=True))
    op.add_column("route_events", sa.Column("modo", sa.String(16), nullable=True))
    op.add_column("route_events", sa.Column("destino_final", sa.String(24), nullable=True))


def downgrade() -> None:
    op.drop_column("route_events", "destino_final")
    op.drop_column("route_events", "modo")
    op.drop_column("route_events", "prioridad")
