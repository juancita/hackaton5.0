"""Tablas de feedback en PostgreSQL (spec 05 · R7). El esquema lo crean las migraciones de Alembic."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ReporterRow(Base):
    __tablename__ = "reporters"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canal: Mapped[str] = mapped_column(String(16))
    rol: Mapped[str] = mapped_column(String(16), default="usuario")
    aciertos: Mapped[int] = mapped_column(Integer, default=0)
    fallos: Mapped[int] = mapped_column(Integer, default=0)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ultimo_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IncidentRow(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(32))
    de_id: Mapped[str] = mapped_column(String(64))
    a_id: Mapped[str] = mapped_column(String(64))
    modo: Mapped[str] = mapped_column(String(32))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    nota: Mapped[str] = mapped_column(Text, default="")
    estado: Mapped[str] = mapped_column(String(16), default="activo")
    confianza: Mapped[float] = mapped_column(Float, default=0.0)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    verificado_por: Mapped[str | None] = mapped_column(ForeignKey("reporters.id"), nullable=True)
    resuelto: Mapped[bool] = mapped_column(Boolean, default=False)

    reports: Mapped[list["ReportRow"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", order_by="ReportRow.id", lazy="selectin"
    )
    votes: Mapped[list["VoteRow"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", order_by="VoteRow.id", lazy="selectin"
    )

    __table_args__ = (Index("ix_incidents_tramo", "de_id", "a_id", "tipo", "estado"),)


class ReportRow(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"))
    reporter_id: Mapped[str] = mapped_column(ForeignKey("reporters.id"))
    peso: Mapped[float] = mapped_column(Float)
    nota: Mapped[str] = mapped_column(Text, default="")
    canal: Mapped[str] = mapped_column(String(16))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    incident: Mapped[IncidentRow] = relationship(back_populates="reports")

    __table_args__ = (Index("ix_reports_reporter", "reporter_id", "creado_en"),)


class VoteRow(Base):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"))
    reporter_id: Mapped[str] = mapped_column(ForeignKey("reporters.id"))
    valor: Mapped[str] = mapped_column(String(16))
    peso: Mapped[float] = mapped_column(Float)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    incident: Mapped[IncidentRow] = relationship(back_populates="votes")

    __table_args__ = (UniqueConstraint("incident_id", "reporter_id", name="uq_votes_incident_reporter"),)
