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
