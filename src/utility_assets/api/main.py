"""FastAPI application factory. CORS comes from the environment, never '*'."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utility_assets.api.auth import router as auth_router
from utility_assets.api.errors import register_error_handlers
from utility_assets.api.middleware import register_middleware
from utility_assets.api.status import router as status_router
from utility_assets.config import get_settings
from utility_assets.db import init_db


def _ensure_sqlite_parent(database_url: str) -> None:
    prefix = "sqlite:///"
    if database_url.startswith(prefix) and ":memory:" not in database_url:
        db_path = Path(database_url.removeprefix(prefix))
        if db_path.parent and str(db_path.parent) not in {".", ""}:
            db_path.parent.mkdir(parents=True, exist_ok=True)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        _ensure_sqlite_parent(settings.database_url)
        init_db()
        yield

    app = FastAPI(
        title="Utility Asset Registry",
        description=(
            "HTTP service for distribution poles, valves, manholes and transformers. "
            "The vendor web map connects here. Visit /docs to try every operation."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(status_router)
    app.include_router(auth_router)
    register_error_handlers(app)
    register_middleware(app)
    return app


app = create_app()
