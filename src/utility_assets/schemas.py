"""Pydantic shapes for the HTTP API and ingest."""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from utility_assets.models import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole


class UserPublic(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}


class AssetPublic(BaseModel):
    asset_id: str
    name: str
    asset_type: str
    latitude: float
    longitude: float
    elevation_m: float | None
    status: str
    attributes: dict[str, Any]
    latest_surveyed_on: date | None
    latest_surveyor: str | None
    latest_condition_score: int | None

    model_config = {"from_attributes": True}


class AssetListResponse(BaseModel):
    items: list[AssetPublic]
    total: int
    limit: int
    offset: int


class AssetWrite(BaseModel):
    asset_id: str
    name: str
    asset_type: str
    latitude: Any
    longitude: Any
    elevation_m: Any = None
    surveyed_on: date
    surveyor: str
    status: str
    condition_score: int
    attributes: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class AssetPatch(BaseModel):
    name: str | None = None
    asset_type: str | None = None
    latitude: Any = None
    longitude: Any = None
    elevation_m: Any = None
    surveyed_on: date | None = None
    surveyor: str | None = None
    status: str | None = None
    condition_score: int | None = None
    attributes: dict[str, Any] | None = None
    notes: str | None = None


class VisitPublic(BaseModel):
    id: int
    surveyed_on: date
    surveyor: str
    condition_score: int
    notes: str | None

    model_config = {"from_attributes": True}


class VisitListResponse(BaseModel):
    asset_id: str
    items: list[VisitPublic]


class NearestResponse(BaseModel):
    distance_km: float
    asset: AssetPublic
