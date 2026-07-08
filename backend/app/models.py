import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class CaptureStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class CaptureSource(str, enum.Enum):
    phone = "phone"
    drone = "drone"
    mixed = "mixed"  # drone p/ geometria geral + celular p/ close-ups


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Building(Base):
    __tablename__ = "buildings"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    captures: Mapped[list["Capture"]] = relationship(back_populates="building")


class Capture(Base):
    """Uma sessão de captura (fotos + GCP opcional) de um prédio."""
    __tablename__ = "captures"
    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), index=True)
    source: Mapped[CaptureSource] = mapped_column(Enum(CaptureSource),
                                                  default=CaptureSource.phone)
    status: Mapped[CaptureStatus] = mapped_column(Enum(CaptureStatus),
                                                  default=CaptureStatus.pending)
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    has_gcp: Mapped[bool] = mapped_column(default=False)
    has_video: Mapped[bool] = mapped_column(default=False, server_default="false")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # ex.: transcrição Whisper
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    building: Mapped[Building] = relationship(back_populates="captures")
    measurement: Mapped["Measurement | None"] = relationship(back_populates="capture",
                                                             uselist=False)


class Measurement(Base):
    """Medidas brutas da malha. Área líquida (menos aberturas) entra na Sessão 5."""
    __tablename__ = "measurements"
    id: Mapped[int] = mapped_column(primary_key=True)
    capture_id: Mapped[int] = mapped_column(ForeignKey("captures.id"), unique=True)
    surface_area_m2: Mapped[float] = mapped_column(Float)
    height_m: Mapped[float] = mapped_column(Float)
    footprint_perimeter_m: Mapped[float] = mapped_column(Float)
    mesh_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pointcloud_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    capture: Mapped[Capture] = relationship(back_populates="measurement")
