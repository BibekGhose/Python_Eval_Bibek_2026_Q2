"""Stable, vendor-readable error bodies (PDF 4.2). No stack traces, no secrets."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code = 500
    error = "error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def body(self) -> dict[str, Any]:
        return {"error": self.error, "message": self.message}


class UnauthenticatedError(AppError):
    status_code = 401
    error = "unauthenticated"

    def __init__(self, message: str = "sign in required") -> None:
        super().__init__(message)


class ForbiddenError(AppError):
    status_code = 403
    error = "forbidden"

    def __init__(self, message: str = "you are not permitted to do that") -> None:
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    error = "not_found"


class ConflictError(AppError):
    status_code = 409
    error = "conflict"


class RateLimitedError(AppError):
    status_code = 429
    error = "rate_limited"

    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after

    def body(self) -> dict[str, Any]:
        return {
            "error": self.error,
            "message": self.message,
            "retry_after": self.retry_after,
        }


class ValidationFailed(AppError):
    status_code = 422
    error = "validation_failed"

    def __init__(self, fields: list[dict[str, str]]) -> None:
        self.fields = fields
        super().__init__("validation_failed")

    def body(self) -> dict[str, Any]:
        return {"error": self.error, "fields": self.fields}


def _pydantic_fields(exc: RequestValidationError) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    for item in exc.errors():
        parts = [
            str(part)
            for part in item.get("loc", ())
            if part not in {"body", "query", "path", "header"}
        ]
        fields.append(
            {
                "field": ".".join(parts) if parts else "request",
                "message": str(item.get("msg", "is invalid")),
            }
        )
    return fields


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        headers: dict[str, str] = {}
        if isinstance(exc, RateLimitedError):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.body(),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "validation_failed", "fields": _pydantic_fields(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        mapping = {
            401: "unauthenticated",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "validation_failed",
            429: "rate_limited",
        }
        error = mapping.get(exc.status_code, "error")
        message = str(exc.detail) if exc.detail else "request failed"
        if exc.status_code == 404:
            message = (
                message
                if message not in {"Not Found", "not found"}
                else "that resource does not exist"
            )
        content: dict[str, Any] = {"error": error, "message": message}
        return JSONResponse(status_code=exc.status_code, content=content)
