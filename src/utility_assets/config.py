"""Load runtime settings from the environment. Nothing secret is hardcoded."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings supplied by the environment (PDF 4.5)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str
    secret_key: str
    access_token_expire_minutes: int = Field(default=60)
    cors_origins: str = Field(default="http://127.0.0.1:3000")
    rate_limit_per_minute: int = Field(default=60)
    summary_cache_ttl_seconds: int = Field(default=60)
    ingest_log_path: str = Field(default="logs/ingestion.log")
    request_log_path: str = Field(default="logs/requests.log")

    @field_validator("database_url", "secret_key")
    @classmethod
    def required_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must be set and not blank")
        return value.strip()

    @field_validator("cors_origins")
    @classmethod
    def cors_must_not_allow_all(cls, value: str) -> str:
        origins = [item.strip() for item in value.split(",") if item.strip()]
        if not origins:
            raise ValueError("must list at least one origin")
        if "*" in origins:
            raise ValueError("must not use * ; allow only specific map origins")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """Load settings once. Missing SECRET_KEY or DATABASE_URL fails immediately."""
    return Settings()
