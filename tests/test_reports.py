"""HTTP reports: summary, repairs, frequent visits, surveyors (PDF 3.4, 3.9)."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from utility_assets.api.main import create_app
from utility_assets.db import get_db

from tests.conftest import SURVEYOR_PASSWORD

POLE = {
    "asset_id": "PL-0142",
    "name": "North Feeder Pole",
    "asset_type": "pole",
    "latitude": 20.2701,
    "longitude": 85.8402,
    "elevation_m": 12.4,
    "surveyed_on": "2026-08-03",
    "surveyor": "John Smith",
    "status": "active",
    "condition_score": 4,
    "attributes": {"height_m": 9.5},
}

VALVE = {
    "asset_id": "VL-0201",
    "name": "Patia Inlet Valve",
    "asset_type": "valve",
    "latitude": 20.3532,
    "longitude": 85.8214,
    "elevation_m": None,
    "surveyed_on": "2026-08-03",
    "surveyor": "Rina Das",
    "status": "active",
    "condition_score": 8,
    "attributes": {"bore_mm": 150},
}

TRANSFORMER = {
    "asset_id": "TR-0401",
    "name": "Patia 250 kVA",
    "asset_type": "transformer",
    "latitude": 20.3502,
    "longitude": 85.8205,
    "elevation_m": 16.0,
    "surveyed_on": "2026-08-04",
    "surveyor": "Anita Sahu",
    "status": "decommissioned",
    "condition_score": 1,
    "attributes": {"rating_kva": 250},
}


def _client(session: Session) -> TestClient:
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _auth(client: TestClient) -> dict[str, str]:
    token = client.post(
        "/auth/login",
        json={"username": "surveyor1", "password": SURVEYOR_PASSWORD},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed(client: TestClient, headers: dict[str, str]) -> None:
    for body in (POLE, VALVE, TRANSFORMER):
        response = client.post("/assets", headers=headers, json=body)
        assert response.status_code == 201, response.text


def test_reports_require_sign_in(seeded_session: Session) -> None:
    client = _client(seeded_session)
    for path in (
        "/reports/summary",
        "/reports/repairs",
        "/reports/frequent-visits",
        "/reports/surveyors?date=2026-08-03",
    ):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"] == "unauthenticated"


def test_summary_includes_type_stats_extent_and_repairs(seeded_session: Session) -> None:
    client = _client(seeded_session)
    headers = _auth(client)
    _seed(client, headers)

    response = client.get("/reports/summary", headers=headers)
    body = response.json()
    assert response.status_code == 200
    assert body["count"] == 3
    by_type = {row["asset_type"]: row for row in body["by_type"]}
    assert by_type["pole"]["count"] == 1
    assert by_type["pole"]["average_condition"] == 4.0
    assert by_type["pole"]["worst_asset_id"] == "PL-0142"
    assert by_type["valve"]["average_condition"] == 8.0
    assert body["extent"]["min_latitude"] == 20.2701
    assert body["extent"]["max_longitude"] == 85.8402
    assert [item["asset_id"] for item in body["repairs"]] == ["PL-0142"]
    assert body["repairs"][0]["condition_band"] == "POOR"


def test_repairs_are_active_assets_below_condition_five(seeded_session: Session) -> None:
    client = _client(seeded_session)
    headers = _auth(client)
    _seed(client, headers)
    client.post(
        "/assets",
        headers=headers,
        json={
            **POLE,
            "asset_id": "PL-0143",
            "name": "Fair Pole",
            "condition_score": 5,
        },
    )
    client.post(
        "/assets",
        headers=headers,
        json={
            **POLE,
            "asset_id": "PL-0144",
            "name": "Proposed Poor Pole",
            "status": "proposed",
            "condition_score": 3,
        },
    )

    response = client.get("/reports/repairs", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["asset_id"] for item in items] == ["PL-0142"]
    assert items[0]["status"] == "active"
    assert items[0]["condition_score"] == 4


def test_frequent_visits_are_ordered_by_visit_count(seeded_session: Session) -> None:
    client = _client(seeded_session)
    headers = _auth(client)
    _seed(client, headers)
    client.patch(
        "/assets/PL-0142",
        headers=headers,
        json={"condition_score": 3, "surveyed_on": "2026-08-10", "surveyor": "Bikash Mohanty"},
    )
    client.patch(
        "/assets/PL-0142",
        headers=headers,
        json={"condition_score": 2, "surveyed_on": "2026-08-11"},
    )

    response = client.get("/reports/frequent-visits", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["asset_id"] for item in items] == ["PL-0142", "TR-0401", "VL-0201"]
    assert items[0]["visit_count"] == 3
    assert items[1]["visit_count"] == 1
    assert items[2]["visit_count"] == 1


def test_surveyors_on_a_given_day_come_from_visit_history(seeded_session: Session) -> None:
    client = _client(seeded_session)
    headers = _auth(client)
    _seed(client, headers)
    client.patch(
        "/assets/VL-0201",
        headers=headers,
        json={"surveyed_on": "2026-08-03", "surveyor": "Bikash Mohanty", "condition_score": 7},
    )

    response = client.get("/reports/surveyors?date=2026-08-03", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-08-03"
    assert body["surveyors"] == ["Bikash Mohanty", "John Smith", "Rina Das"]

    later = client.get("/reports/surveyors?date=2026-08-04", headers=headers)
    assert later.json()["surveyors"] == ["Anita Sahu"]


def test_surveyors_without_a_date_is_validation_failed(seeded_session: Session) -> None:
    client = _client(seeded_session)
    response = client.get("/reports/surveyors", headers=_auth(client))
    assert response.status_code == 422
    assert response.json()["error"] == "validation_failed"
