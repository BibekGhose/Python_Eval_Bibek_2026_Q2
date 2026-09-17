"""Shared test setup. Uses a throwaway database and never reads data/app.db."""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["CORS_ORIGINS"] = "http://127.0.0.1:3000"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["RATE_LIMIT_PER_MINUTE"] = "60"
os.environ["SUMMARY_CACHE_TTL_SECONDS"] = "60"

from utility_assets.config import get_settings
from utility_assets.db import create_engine_from_url, init_db
from utility_assets.models import User, UserRole
from utility_assets.security import hash_password

get_settings.cache_clear()


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    """Fresh SQLite file per test. Never the demo data/app.db."""
    url = f"sqlite:///{(tmp_path / 'throwaway.db').resolve().as_posix()}"
    engine = create_engine_from_url(url)
    init_db(engine)
    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


ADMIN_PASSWORD = "admin-pass"
SURVEYOR_PASSWORD = "surveyor-pass"


@pytest.fixture
def seeded_session(db_session: Session) -> Session:
    db_session.add(
        User(
            username="admin",
            password_hash=hash_password(ADMIN_PASSWORD),
            role=UserRole.ADMINISTRATOR,
            is_active=True,
        )
    )
    db_session.add(
        User(
            username="surveyor1",
            password_hash=hash_password(SURVEYOR_PASSWORD),
            role=UserRole.SURVEYOR,
            is_active=True,
        )
    )
    db_session.commit()
    return db_session
