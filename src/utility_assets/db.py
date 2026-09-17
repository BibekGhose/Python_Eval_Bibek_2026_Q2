"""Database engine and session. Swap SQLite for Postgres by changing DATABASE_URL."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from utility_assets.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    """Declarative base for all models."""


def _sqlite_connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def create_engine_from_url(database_url: str) -> Engine:
    """Build an engine from a URL so tests can use a throwaway database."""
    engine = create_engine(
        database_url,
        connect_args=_sqlite_connect_args(database_url),
        future=True,
    )
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine_from_url(get_settings().database_url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _session_factory


def init_db(engine: Engine | None = None) -> None:
    """Create tables. Safe to call more than once."""
    from utility_assets import models  # noqa: F401

    create_engine_target = engine or get_engine()
    Base.metadata.create_all(bind=create_engine_target)


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
