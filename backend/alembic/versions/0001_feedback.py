"""Tablas de feedback: reporteros, incidentes, reportes y votos

Revision ID: 0001_feedback
Revises:
Create Date: 2026-09-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_feedback"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reporters",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("canal", sa.String(16), nullable=False),
        sa.Column("rol", sa.String(16), nullable=False, server_default="usuario"),
        sa.Column("aciertos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fallos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ultimo_en", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tipo", sa.String(32), nullable=False),
        sa.Column("de_id", sa.String(64), nullable=False),
        sa.Column("a_id", sa.String(64), nullable=False),
        sa.Column("modo", sa.String(32), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lng", sa.Float, nullable=False),
        sa.Column("nota", sa.Text, nullable=False, server_default=""),
        sa.Column("estado", sa.String(16), nullable=False, server_default="activo"),
        sa.Column("confianza", sa.Float, nullable=False, server_default="0"),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verificado_por", sa.String(64), sa.ForeignKey("reporters.id"), nullable=True),
        sa.Column("resuelto", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_incidents_tramo", "incidents", ["de_id", "a_id", "tipo", "estado"])
    op.create_index("ix_incidents_expira_en", "incidents", ["expira_en"])
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", sa.String(64), sa.ForeignKey("reporters.id"), nullable=False),
        sa.Column("peso", sa.Float, nullable=False),
        sa.Column("nota", sa.Text, nullable=False, server_default=""),
        sa.Column("canal", sa.String(16), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reports_reporter", "reports", ["reporter_id", "creado_en"])
    op.create_table(
        "votes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", sa.String(64), sa.ForeignKey("reporters.id"), nullable=False),
        sa.Column("valor", sa.String(16), nullable=False),
        sa.Column("peso", sa.Float, nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("incident_id", "reporter_id", name="uq_votes_incident_reporter"),
    )


def downgrade() -> None:
    op.drop_table("votes")
    op.drop_index("ix_reports_reporter", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_incidents_expira_en", table_name="incidents")
    op.drop_index("ix_incidents_tramo", table_name="incidents")
    op.drop_table("incidents")
    op.drop_table("reporters")
