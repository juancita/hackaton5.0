"""Login por teléfono (nombre/modo) + módulo de conductores: perfiles, viajes, cupos, lugares, tracking

Revision ID: 0002_drivers
Revises: 0001_feedback
Create Date: 2026-09-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_drivers"
down_revision = "0001_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Login por celular: nombre de usuario y modo (pasajero/conductor) en reporters
    op.add_column("reporters", sa.Column("nombre", sa.String(40), nullable=True))
    op.add_column("reporters", sa.Column("modo", sa.String(16), nullable=False, server_default="pasajero"))

    op.create_table(
        "driver_profiles",
        sa.Column("reporter_id", sa.String(64), primary_key=True),
        sa.Column("ruta", sa.String(80), nullable=False, server_default=""),
        sa.Column("barrio_base", sa.String(64), nullable=True),
        sa.Column("placa", sa.String(16), nullable=True),
        sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "trips",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("driver_id", sa.String(64), nullable=False),
        sa.Column("driver_nombre", sa.String(40), nullable=False, server_default=""),
        sa.Column("ruta", sa.String(80), nullable=False, server_default=""),
        sa.Column("origen_id", sa.String(64), nullable=False),
        sa.Column("destino_id", sa.String(64), nullable=False),
        sa.Column("hora", sa.String(5), nullable=False),
        sa.Column("cupos_total", sa.Integer, nullable=False),
        sa.Column("cupos_libres", sa.Integer, nullable=False),
        sa.Column("estado", sa.String(16), nullable=False, server_default="programado"),
        sa.Column("lleno", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("lat", sa.Float, nullable=True),
        sa.Column("lng", sa.Float, nullable=True),
        sa.Column("salio_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("desvio", sa.Text, nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trips_driver_id", "trips", ["driver_id"])
    op.create_index("ix_trips_creado_en", "trips", ["creado_en"])
    op.create_index("ix_trips_estado", "trips", ["estado", "origen_id", "destino_id"])
    op.create_table(
        "seat_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("trip_id", sa.String(36), nullable=False),
        sa.Column("passenger_id", sa.String(64), nullable=False),
        sa.Column("passenger_nombre", sa.String(40), nullable=False, server_default=""),
        sa.Column("estado", sa.String(16), nullable=False, server_default="reservado"),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_seat_requests_trip_id", "seat_requests", ["trip_id"])
    op.create_table(
        "saved_places",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reporter_id", sa.String(64), nullable=False),
        sa.Column("etiqueta", sa.String(24), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lng", sa.Float, nullable=False),
        sa.Column("place_id", sa.String(64), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("reporter_id", "etiqueta", name="uq_saved_reporter_etiqueta"),
    )
    op.create_index("ix_saved_places_reporter_id", "saved_places", ["reporter_id"])
    op.create_table(
        "route_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("reporter_id", sa.String(64), nullable=False),
        sa.Column("origen_id", sa.String(64), nullable=False),
        sa.Column("destino_id", sa.String(64), nullable=False),
        sa.Column("canal", sa.String(16), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_route_events_reporter_id", "route_events", ["reporter_id"])
    op.create_index("ix_route_events_creado_en", "route_events", ["creado_en"])
    op.create_table(
        "identity_links",
        sa.Column("canal_key", sa.String(64), primary_key=True),
        sa.Column("reporter_id", sa.String(64), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_identity_links_reporter_id", "identity_links", ["reporter_id"])


def downgrade() -> None:
    op.drop_table("identity_links")
    op.drop_table("route_events")
    op.drop_table("saved_places")
    op.drop_table("seat_requests")
    op.drop_index("ix_trips_estado", table_name="trips")
    op.drop_index("ix_trips_creado_en", table_name="trips")
    op.drop_index("ix_trips_driver_id", table_name="trips")
    op.drop_table("trips")
    op.drop_table("driver_profiles")
    op.drop_column("reporters", "modo")
    op.drop_column("reporters", "nombre")
