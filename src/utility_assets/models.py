"""Persistent records: users, assets, and visit history (PDF 3.6)."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from utility_assets.db import Base


class UserRole(StrEnum):
    SURVEYOR = "surveyor"
    ADMINISTRATOR = "administrator"


class AssetType(StrEnum):
    POLE = "pole"
    VALVE = "valve"
    MANHOLE = "manhole"
    TRANSFORMER = "transformer"


class AssetStatus(StrEnum):
    ACTIVE = "active"
    DECOMMISSIONED = "decommissioned"
    PROPOSED = "proposed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class Asset(Base):
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(String(7), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    asset_type: Mapped[AssetType] = mapped_column(String(20), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[AssetStatus] = mapped_column(String(20), index=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    latest_surveyed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    latest_surveyor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latest_condition_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    visits: Mapped[list["Visit"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(
        String(7),
        ForeignKey("assets.asset_id", ondelete="CASCADE"),
        index=True,
    )
    surveyed_on: Mapped[date] = mapped_column(Date)
    surveyor: Mapped[str] = mapped_column(String(120), index=True)
    condition_score: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    asset: Mapped[Asset] = relationship(back_populates="visits")
