"""Consistent error bodies, process-time header, and request log (PDF 4.2, 4.7)."""

from pathlib import Path

from fastapi.testclient import TestClient

from utility_assets.api.errors import (
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    UnauthenticatedError,
    ValidationFailed,
)
from utility_assets.api.main import create_app
from utility_assets.config import get_settings


def _client(tmp_path: Path) -> TestClient:
    get_settings().request_log_path = str(tmp_path / "requests.log")
    return TestClient(create_app())


def test_every_response_includes_process_time(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/status")
    assert response.status_code == 200
    assert "X-Process-Time" in response.headers
    assert response.headers["X-Process-Time"].endswith("s")


def test_unknown_route_is_a_clear_404_not_a_stack_trace(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/does-not-exist")
    body = response.json()
    assert response.status_code == 404
    assert body["error"] == "not_found"
    assert "traceback" not in str(body).lower()
    assert "stack" not in str(body).lower()
    assert "X-Process-Time" in response.headers


def test_named_error_outcomes_use_distinct_bodies(tmp_path: Path) -> None:
    app = create_app()

    @app.get("/_probe/unauthenticated")
    def unauthenticated() -> None:
        raise UnauthenticatedError()

    @app.get("/_probe/forbidden")
    def forbidden() -> None:
        raise ForbiddenError()

    @app.get("/_probe/missing")
    def missing() -> None:
        raise NotFoundError("asset PL-9999 does not exist")

    @app.get("/_probe/invalid")
    def invalid() -> None:
        raise ValidationFailed(
            [
                {
                    "field": "condition_score",
                    "message": "must be a whole number between 0 and 10",
                }
            ]
        )

    @app.get("/_probe/limited")
    def limited() -> None:
        raise RateLimitedError("too many requests; try again shortly", retry_after=12)

    get_settings().request_log_path = str(tmp_path / "requests.log")
    client = TestClient(app)

    unauth = client.get("/_probe/unauthenticated")
    assert unauth.status_code == 401
    assert unauth.json()["error"] == "unauthenticated"

    forbid = client.get("/_probe/forbidden")
    assert forbid.status_code == 403
    assert forbid.json()["error"] == "forbidden"
    assert unauth.json()["error"] != forbid.json()["error"]

    missing_resp = client.get("/_probe/missing")
    assert missing_resp.status_code == 404
    assert "PL-9999" in missing_resp.json()["message"]

    invalid_resp = client.get("/_probe/invalid")
    assert invalid_resp.status_code == 422
    assert invalid_resp.json() == {
        "error": "validation_failed",
        "fields": [
            {
                "field": "condition_score",
                "message": "must be a whole number between 0 and 10",
            }
        ],
    }

    limited_resp = client.get("/_probe/limited")
    assert limited_resp.status_code == 429
    assert limited_resp.headers["Retry-After"] == "12"
    assert "try again" in limited_resp.json()["message"]


def test_request_log_records_method_path_status_and_duration(tmp_path: Path) -> None:
    log_path = tmp_path / "requests.log"
    get_settings().request_log_path = str(log_path)
    _client(tmp_path).get("/status")
    text = log_path.read_text(encoding="utf-8")
    assert "GET /status" in text
    assert " 200 " in text
    assert "user=anonymous" in text
    assert "s  " in text or "s\n" in text or "s  user" in text
    assert "password" not in text.lower()
    assert "secret" not in text.lower()
    assert "Bearer" not in text
