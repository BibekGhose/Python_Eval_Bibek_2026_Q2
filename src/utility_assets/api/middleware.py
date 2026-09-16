"""Record how long each request took, without logging secrets."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from utility_assets.config import get_settings
from utility_assets.ingestion.writers import now_ist


def _client_address(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host


def _username(request: Request) -> str:
    return getattr(request.state, "username", None) or "anonymous"


def _append_request_log(line: str) -> None:
    path = Path(get_settings().request_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


class TimingAndRequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - started
        header_value = f"{duration:.3f}s"
        response.headers["X-Process-Time"] = header_value
        stamp = now_ist().isoformat(timespec="seconds")
        line = (
            f"{stamp}  {request.method} {request.url.path}  "
            f"{response.status_code}  {header_value}  "
            f"user={_username(request)}  client={_client_address(request)}\n"
        )
        _append_request_log(line)
        return response


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(TimingAndRequestLogMiddleware)
