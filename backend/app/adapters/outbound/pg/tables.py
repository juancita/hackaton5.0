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
    nombre: Mapped[str | None] = mapped_column(String(40), nullable=True)
    modo: Mapped[str] = mapped_column(String(16), default="pasajero")
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


# --- Módulo de conductores informales ---------------------------------------

class DriverProfileRow(Base):
    __tablename__ = "driver_profiles"

    reporter_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ruta: Mapped[str] = mapped_column(String(80), default="")
    barrio_base: Mapped[str | None] = mapped_column(String(64), nullable=True)
    placa: Mapped[str | None] = mapped_column(String(16), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TripRow(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    driver_id: Mapped[str] = mapped_column(String(64), index=True)
    driver_nombre: Mapped[str] = mapped_column(String(40), default="")
    ruta: Mapped[str] = mapped_column(String(80), default="")
    origen_id: Mapped[str] = mapped_column(String(64))
    destino_id: Mapped[str] = mapped_column(String(64))
    hora: Mapped[str] = mapped_column(String(5))
    cupos_total: Mapped[int] = mapped_column(Integer)
    cupos_libres: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(16), default="programado")
    lleno: Mapped[bool] = mapped_column(Boolean, default=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    salio_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    desvio: Mapped[str | None] = mapped_column(Text, nullable=True)
    paradas: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON: ["ensueno","sierramorena","potosi"]
    corta_en: Mapped[str | None] = mapped_column(String(64), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (Index("ix_trips_estado", "estado", "origen_id", "destino_id"),)


class SeatRequestRow(Base):
    __tablename__ = "seat_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(36), index=True)
    passenger_id: Mapped[str] = mapped_column(String(64))
    passenger_nombre: Mapped[str] = mapped_column(String(40), default="")
    baja_en: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estado: Mapped[str] = mapped_column(String(16), default="reservado")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SavedPlaceRow(Base):
    __tablename__ = "saved_places"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reporter_id: Mapped[str] = mapped_column(String(64), index=True)
    etiqueta: Mapped[str] = mapped_column(String(24))
    nombre: Mapped[str] = mapped_column(String(80))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    place_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("reporter_id", "etiqueta", name="uq_saved_reporter_etiqueta"),)


class RouteEventRow(Base):
    __tablename__ = "route_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_id: Mapped[str] = mapped_column(String(64), index=True)
    origen_id: Mapped[str] = mapped_column(String(64))
    destino_id: Mapped[str] = mapped_column(String(64))
    canal: Mapped[str] = mapped_column(String(16))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IdentityLinkRow(Base):
    """Vincula una identidad de canal (p. ej. Telegram) con la identidad por teléfono."""
    __tablename__ = "identity_links"

    canal_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    reporter_id: Mapped[str] = mapped_column(String(64), index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
