"""Viajes con paradas intermedias: recorrido, corte del viaje y parada de bajada del pasajero

Revision ID: 0003_paradas
Revises: 0002_drivers
Create Date: 2026-09-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_paradas"
down_revision = "0002_drivers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("paradas", sa.Text, nullable=True))
    op.add_column("trips", sa.Column("corta_en", sa.String(64), nullable=True))
    op.add_column("seat_requests", sa.Column("baja_en", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("seat_requests", "baja_en")
    op.drop_column("trips", "corta_en")
    op.drop_column("trips", "paradas")
