"""List, filter, page, and fetch one asset (PDF 3.7–3.8, 4.8.3)."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from utility_assets.api.main import create_app
from utility_assets.db import get_db
from utility_assets.models import Asset, Visit

from tests.conftest import ADMIN_PASSWORD, SURVEYOR_PASSWORD


def _client(session: Session) -> TestClient:
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _auth(client: TestClient, username: str = "surveyor1", password: str = SURVEYOR_PASSWORD) -> dict:
    token = client.post(
        "/auth/login",
        json={"username": username, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _add_asset(session: Session, asset_id: str, **overrides: object) -> None:
    values = {
        "asset_id": asset_id,
        "name": f"Asset {asset_id}",
        "asset_type": "pole",
        "latitude": 20.27,
        "longitude": 85.84,
        "elevation_m": None,
        "status": "active",
        "attributes": {},
        "latest_surveyed_on": date(2026, 8, 3),
        "latest_surveyor": "John Smith",
        "latest_condition_score": 8,
    }
    values.update(overrides)
    session.add(Asset(**values))
    session.commit()


def test_list_requires_sign_in(seeded_session: Session) -> None:
    response = _client(seeded_session).get("/assets")
    assert response.status_code == 401


def test_list_defaults_to_25_and_includes_total(seeded_session: Session) -> None:
    for index in range(1, 27):
        _add_asset(seeded_session, f"PL-{index:04d}")
    client = _client(seeded_session)
    response = client.get("/assets", headers=_auth(client))
    body = response.json()
    assert response.status_code == 200
    assert body["limit"] == 25
    assert body["offset"] == 0
    assert body["total"] == 26
    assert len(body["items"]) == 25


def test_list_rejects_limit_over_100(seeded_session: Session) -> None:
    client = _client(seeded_session)
    response = client.get("/assets?limit=101", headers=_auth(client))
    assert response.status_code == 422
    assert response.json()["error"] == "validation_failed"


def test_list_filters_and_search(seeded_session: Session) -> None:
    _add_asset(
        seeded_session,
        "PL-0101",
        name="North Feeder Pole",
        asset_type="pole",
        status="active",
        latest_surveyor="John Smith",
        latest_condition_score=4,
    )
    _add_asset(
        seeded_session,
        "VL-0201",
        name="Patia Inlet Valve",
        asset_type="valve",
        status="proposed",
        latest_surveyor="Rina Das",
        latest_condition_score=8,
    )
    _add_asset(
        seeded_session,
        "MH-0301",
        name="Old Town Chamber",
        asset_type="manhole",
        status="active",
        latest_surveyor="John Smith",
        latest_condition_score=2,
    )
    client = _client(seeded_session)
    headers = _auth(client)

    by_type = client.get("/assets?asset_type=Pole", headers=headers).json()
    assert by_type["total"] == 1
    assert by_type["items"][0]["asset_id"] == "PL-0101"

    by_status = client.get("/assets?status=proposed", headers=headers).json()
    assert by_status["total"] == 1
    assert by_status["items"][0]["asset_id"] == "VL-0201"

    by_surveyor = client.get("/assets?surveyor=JOHN%20%20smith", headers=headers).json()
    assert by_surveyor["total"] == 2

    by_condition = client.get(
        "/assets?condition_min=0&condition_max=4", headers=headers
    ).json()
    assert {item["asset_id"] for item in by_condition["items"]} == {"PL-0101", "MH-0301"}

    by_q = client.get("/assets?q=feeder", headers=headers).json()
    assert by_q["total"] == 1
    assert by_q["items"][0]["name"] == "North Feeder Pole"


def test_get_asset_by_code(seeded_session: Session) -> None:
    _add_asset(seeded_session, "PL-0142", name="Stencilled Pole")
    client = _client(seeded_session)
    response = client.get("/assets/PL-0142", headers=_auth(client, "admin", ADMIN_PASSWORD))
    assert response.status_code == 200
    assert response.json()["asset_id"] == "PL-0142"
    assert response.json()["name"] == "Stencilled Pole"


def test_get_unknown_asset_returns_404(seeded_session: Session) -> None:
    client = _client(seeded_session)
    response = client.get("/assets/PL-9999", headers=_auth(client))
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert "PL-9999" in body["message"]
    assert "traceback" not in str(body).lower()


CREATE_BODY = {
    "asset_id": "PL-0142",
    "name": "  north  FEEDER   pole ",
    "asset_type": "Pole",
    "latitude": "20.2701 N",
    "longitude": 85.8402,
    "elevation_m": None,
    "surveyed_on": "2026-08-03",
    "surveyor": "JOHN  smith",
    "status": "active",
    "condition_score": 8,
    "attributes": {"height_m": 9.5},
}


def test_create_asset_returns_201(seeded_session: Session) -> None:
    client = _client(seeded_session)
    response = client.post("/assets", headers=_auth(client), json=CREATE_BODY)
    body = response.json()
    assert response.status_code == 201
    assert body["asset_id"] == "PL-0142"
    assert body["name"] == "North Feeder Pole"
    assert body["asset_type"] == "pole"
    assert body["latest_surveyor"] == "John Smith"
    visits = seeded_session.scalars(select(Visit).where(Visit.asset_id == "PL-0142")).all()
    assert len(visits) == 1


def test_duplicate_create_returns_409_and_leaves_data(seeded_session: Session) -> None:
    _add_asset(seeded_session, "PL-0142", name="Original Name")
    client = _client(seeded_session)
    response = client.post("/assets", headers=_auth(client), json=CREATE_BODY)
    assert response.status_code == 409
    assert response.json()["error"] == "conflict"
    assert seeded_session.get(Asset, "PL-0142").name == "Original Name"


def test_put_replaces_asset_and_appends_visit(seeded_session: Session) -> None:
    client = _client(seeded_session)
    headers = _auth(client)
    client.post("/assets", headers=headers, json=CREATE_BODY)
    replacement = {
        **CREATE_BODY,
        "name": "Replaced Pole",
        "surveyed_on": "2026-09-01",
        "condition_score": 4,
    }
    response = client.put("/assets/PL-0142", headers=headers, json=replacement)
    assert response.status_code == 200
    assert response.json()["name"] == "Replaced Pole"
    assert response.json()["latest_condition_score"] == 4
    visits = seeded_session.scalars(select(Visit).where(Visit.asset_id == "PL-0142")).all()
    assert len(visits) == 2


def test_patch_name_does_not_append_visit(seeded_session: Session) -> None:
    client = _client(seeded_session)
    headers = _auth(client)
    client.post("/assets", headers=headers, json=CREATE_BODY)
    response = client.patch(
        "/assets/PL-0142",
        headers=headers,
        json={"name": "Corrected Pole Name"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Corrected Pole Name"
    visits = seeded_session.scalars(select(Visit).where(Visit.asset_id == "PL-0142")).all()
    assert len(visits) == 1


def test_patch_survey_fields_append_a_visit(seeded_session: Session) -> None:
    client = _client(seeded_session)
    headers = _auth(client)
    client.post("/assets", headers=headers, json=CREATE_BODY)
    response = client.patch(
        "/assets/PL-0142",
        headers=headers,
        json={"condition_score": 3, "surveyed_on": "2026-09-02", "surveyor": "Rina Das"},
    )
    assert response.status_code == 200
    assert response.json()["latest_condition_score"] == 3
    visits = seeded_session.scalars(select(Visit).where(Visit.asset_id == "PL-0142")).all()
    assert len(visits) == 2


def test_admin_delete_returns_204_and_cascades_visits(seeded_session: Session) -> None:
    client = _client(seeded_session)
    surveyor = _auth(client)
    client.post("/assets", headers=surveyor, json=CREATE_BODY)
    admin = _auth(client, "admin", ADMIN_PASSWORD)
    response = client.delete("/assets/PL-0142", headers=admin)
    assert response.status_code == 204
    assert seeded_session.get(Asset, "PL-0142") is None
    assert seeded_session.scalar(select(func.count()).select_from(Visit)) == 0


def test_surveyor_cannot_delete(seeded_session: Session) -> None:
    client = _client(seeded_session)
    headers = _auth(client)
    client.post("/assets", headers=headers, json=CREATE_BODY)
    response = client.delete("/assets/PL-0142", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"
    assert seeded_session.get(Asset, "PL-0142") is not None


def test_list_visits_for_one_asset(seeded_session: Session) -> None:
    client = _client(seeded_session)
    headers = _auth(client)
    client.post("/assets", headers=headers, json=CREATE_BODY)
    client.patch(
        "/assets/PL-0142",
        headers=headers,
        json={"condition_score": 3, "surveyed_on": "2026-09-02"},
    )
    response = client.get("/assets/PL-0142/visits", headers=headers)
    assert response.status_code == 200
    assert response.json()["asset_id"] == "PL-0142"
    assert len(response.json()["items"]) == 2


def test_nearest_asset_uses_haversine(seeded_session: Session) -> None:
    _add_asset(seeded_session, "PL-0101", latitude=20.2701, longitude=85.8402)
    _add_asset(seeded_session, "PL-0102", latitude=20.3532, longitude=85.8214)
    client = _client(seeded_session)
    response = client.get(
        "/assets/nearest?latitude=20.2710&longitude=85.8400",
        headers=_auth(client),
    )
    assert response.status_code == 200
    assert response.json()["asset"]["asset_id"] == "PL-0101"
    assert "distance_km" in response.json()
