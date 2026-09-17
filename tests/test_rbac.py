"""Role guards: surveyor vs administrator (PDF 3.11.2, 4.2.6, 4.8.3)."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from utility_assets.api.main import create_app
from utility_assets.db import get_db
from utility_assets.models import Asset

from tests.conftest import ADMIN_PASSWORD, SURVEYOR_PASSWORD


def _client(session: Session) -> TestClient:
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _auth(client: TestClient, username: str, password: str) -> dict[str, str]:
    token = client.post(
        "/auth/login",
        json={"username": username, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_surveyor_cannot_delete(seeded_session: Session) -> None:
    seeded_session.add(
        Asset(
            asset_id="PL-0142",
            name="Stencilled Pole",
            asset_type="pole",
            latitude=20.27,
            longitude=85.84,
            status="active",
            attributes={},
            latest_surveyed_on=date(2026, 8, 3),
            latest_surveyor="John Smith",
            latest_condition_score=8,
        )
    )
    seeded_session.commit()
    client = _client(seeded_session)
    response = client.delete(
        "/assets/PL-0142",
        headers=_auth(client, "surveyor1", SURVEYOR_PASSWORD),
    )
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"
    assert seeded_session.get(Asset, "PL-0142") is not None


def test_unauthenticated_delete_is_401_not_403(seeded_session: Session) -> None:
    client = _client(seeded_session)
    response = client.delete("/assets/PL-0142")
    assert response.status_code == 401
    assert response.json()["error"] == "unauthenticated"


def test_surveyor_cannot_create_a_user(seeded_session: Session) -> None:
    client = _client(seeded_session)
    response = client.post(
        "/users",
        headers=_auth(client, "surveyor1", SURVEYOR_PASSWORD),
        json={
            "username": "surveyor2",
            "password": "new-user-pass",
            "role": "surveyor",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


def test_surveyor_cannot_bulk_ingest(seeded_session: Session) -> None:
    client = _client(seeded_session)
    response = client.post(
        "/ingest",
        headers=_auth(client, "surveyor1", SURVEYOR_PASSWORD),
        files={"file": ("day.csv", b"asset_id,name\n", "text/csv")},
    )
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


def test_unauthenticated_ingest_is_401(seeded_session: Session) -> None:
    client = _client(seeded_session)
    response = client.post(
        "/ingest",
        files={"file": ("day.csv", b"asset_id,name\n", "text/csv")},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthenticated"


def test_administrator_can_delete(seeded_session: Session) -> None:
    seeded_session.add(
        Asset(
            asset_id="PL-0142",
            name="Stencilled Pole",
            asset_type="pole",
            latitude=20.27,
            longitude=85.84,
            status="active",
            attributes={},
            latest_surveyed_on=date(2026, 8, 3),
            latest_surveyor="John Smith",
            latest_condition_score=8,
        )
    )
    seeded_session.commit()
    client = _client(seeded_session)
    response = client.delete(
        "/assets/PL-0142",
        headers=_auth(client, "admin", ADMIN_PASSWORD),
    )
    assert response.status_code == 204
    seeded_session.expire_all()
    assert seeded_session.get(Asset, "PL-0142") is None
