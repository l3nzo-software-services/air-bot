"""
SQLAlchemy ORM models for CellSentinel.
Defines Devices, Telemetry, and Cell Tower Cache tables with indexes and constraints.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index
)
from sqlalchemy.orm import relationship

from cellsentinel.database import Base


class Device(Base):
    """Registered cellular device hardware identity."""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    imei_hash = Column(String(64), unique=True, index=True, nullable=False)
    device_name = Column(String(120), nullable=False)
    device_token_hash = Column(String(64), nullable=False)
    registration_timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    last_seen_timestamp = Column(DateTime(timezone=True), nullable=True)
    device_status = Column(String(30), default="ACTIVE", nullable=False)

    # Relationships
    telemetry_records = relationship(
        "Telemetry",
        back_populates="device",
        cascade="all, delete-orphan",
        order_by="desc(Telemetry.timestamp)"
    )

    def __repr__(self):
        return f"<Device(id={self.id}, name='{self.device_name}', status='{self.device_status}')>"


class Telemetry(Base):
    """Ingested cellular tower broadcast telemetry record."""
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(
        Integer,
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    mcc = Column(Integer, nullable=False)
    mnc = Column(Integer, nullable=False)
    lac = Column(Integer, nullable=False)
    cell_id = Column(Integer, nullable=False)
    signal_strength = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    accuracy_radius = Column(Float, nullable=True)
    location_source = Column(String(50), nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # Relationships
    device = relationship("Device", back_populates="telemetry_records")

    __table_args__ = (
        Index("idx_telemetry_device_time", "device_id", "timestamp"),
        Index("idx_telemetry_tower", "mcc", "mnc", "lac", "cell_id"),
    )

    def __repr__(self):
        return (
            f"<Telemetry(id={self.id}, device_id={self.device_id}, "
            f"cell_id={self.cell_id}, lat={self.latitude}, lon={self.longitude})>"
        )


class CellTowerCache(Base):
    """Local SQLite persistent cell tower geolocation cache."""
    __tablename__ = "cell_tower_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mcc = Column(Integer, nullable=False)
    mnc = Column(Integer, nullable=False)
    lac = Column(Integer, nullable=False)
    cell_id = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy_radius = Column(Float, nullable=True)
    source = Column(String(50), nullable=False)
    last_updated = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint("mcc", "mnc", "lac", "cell_id", name="uq_cell_tower_tuple"),
        Index("idx_cache_lookup", "mcc", "mnc", "lac", "cell_id"),
    )

    def __repr__(self):
        return (
            f"<CellTowerCache(mcc={self.mcc}, mnc={self.mnc}, lac={self.lac}, "
            f"cell_id={self.cell_id}, lat={self.latitude}, lon={self.longitude})>"
        )
