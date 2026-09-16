"""Published documentation and the open status address (PDF 3.9.4, 4.6.2, 4.4.5)."""

from fastapi.testclient import TestClient

from utility_assets.api.main import create_app


def test_status_does_not_require_sign_in() -> None:
    client = TestClient(create_app())
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_docs_page_is_published() -> None:
    client = TestClient(create_app())
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower() or "openapi" in response.text.lower()


def test_openapi_lists_the_status_operation() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/status" in response.json()["paths"]


def test_cors_allows_only_the_configured_map_origin() -> None:
    client = TestClient(create_app())
    allowed = client.get("/status", headers={"Origin": "http://127.0.0.1:3000"})
    assert allowed.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"

    blocked = client.get("/status", headers={"Origin": "http://evil.example"})
    assert blocked.headers.get("access-control-allow-origin") != "http://evil.example"
