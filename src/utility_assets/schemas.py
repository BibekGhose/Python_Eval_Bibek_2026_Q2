"""Pydantic shapes for the HTTP API and ingest."""

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
