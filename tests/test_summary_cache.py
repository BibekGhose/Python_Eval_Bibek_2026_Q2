"""Summary cache: MISS then HIT, then MISS again after a change (PDF 4.3)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from utility_assets.api.main import create_app
from utility_assets.db import get_db
from utility_assets.ingestion.writers import ORIGINAL_COLUMNS
from utility_assets.services.cache import summary_cache

from tests.conftest import ADMIN_PASSWORD, SURVEYOR_PASSWORD

CREATE_BODY = {
    "asset_id": "PL-0142",
    "name": "North Feeder Pole",
    "asset_type": "pole",
    "latitude": 20.2701,
    "longitude": 85.8402,
    "elevation_m": None,
    "surveyed_on": "2026-08-03",
    "surveyor": "John Smith",
    "status": "active",
    "condition_score": 8,
    "attributes": {"height_m": 9.5},
}


def _client(session: Session) -> TestClient:
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _auth(
    client: TestClient,
    username: str = "surveyor1",
    password: str = SURVEYOR_PASSWORD,
) -> dict[str, str]:
    token = client.post(
        "/auth/login",
        json={"username": username, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_summary_is_served_from_cache_then_refreshed_after_a_change(
    seeded_session: Session,
) -> None:
    client = _client(seeded_session)
    headers = _auth(client)
    assert client.post("/assets", headers=headers, json=CREATE_BODY).status_code == 201
    assert (
        client.post(
            "/assets",
            headers=headers,
            json={**CREATE_BODY, "asset_id": "PL-0143", "condition_score": 4},
        ).status_code
        == 201
    )

    first = client.get("/reports/summary", headers=headers)
    assert first.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    first_avg = next(
        row["average_condition"]
        for row in first.json()["by_type"]
        if row["asset_type"] == "pole"
    )
    assert first_avg == 6.0

    second = client.get("/reports/summary", headers=headers)
    assert second.status_code == 200
    assert second.headers["X-Cache"] == "HIT"
    assert second.json() == first.json()

    patched = client.patch(
        "/assets/PL-0142",
        headers=headers,
        json={"condition_score": 2, "surveyed_on": "2026-09-02"},
    )
    assert patched.status_code == 200

    third = client.get("/reports/summary", headers=headers)
    assert third.status_code == 200
    assert third.headers["X-Cache"] == "MISS"
    new_avg = next(
        row["average_condition"]
        for row in third.json()["by_type"]
        if row["asset_type"] == "pole"
    )
    assert new_avg == 3.0
    assert new_avg != first_avg


def test_summary_cache_expires_after_ttl(seeded_session: Session) -> None:
    now = [100.0]
    summary_cache.clock = lambda: now[0]
    client = _client(seeded_session)
    headers = _auth(client)
    assert client.post("/assets", headers=headers, json=CREATE_BODY).status_code == 201

    miss = client.get("/reports/summary", headers=headers)
    assert miss.headers["X-Cache"] == "MISS"

    now[0] = 159.0
    hit = client.get("/reports/summary", headers=headers)
    assert hit.headers["X-Cache"] == "HIT"

    now[0] = 160.0
    expired = client.get("/reports/summary", headers=headers)
    assert expired.headers["X-Cache"] == "MISS"
    assert expired.json() == miss.json()


def test_delete_discards_the_cached_summary(seeded_session: Session) -> None:
    client = _client(seeded_session)
    surveyor = _auth(client)
    admin = _auth(client, "admin", ADMIN_PASSWORD)
    assert client.post("/assets", headers=surveyor, json=CREATE_BODY).status_code == 201

    first = client.get("/reports/summary", headers=surveyor)
    assert first.headers["X-Cache"] == "MISS"
    assert first.json()["count"] == 1
    assert client.get("/reports/summary", headers=surveyor).headers["X-Cache"] == "HIT"

    deleted = client.delete("/assets/PL-0142", headers=admin)
    assert deleted.status_code == 204

    refreshed = client.get("/reports/summary", headers=surveyor)
    assert refreshed.headers["X-Cache"] == "MISS"
    assert refreshed.json()["count"] == 0


def test_bulk_ingest_discards_the_cached_summary(seeded_session: Session) -> None:
    client = _client(seeded_session)
    surveyor = _auth(client)
    admin = _auth(client, "admin", ADMIN_PASSWORD)

    empty = client.get("/reports/summary", headers=surveyor)
    assert empty.headers["X-Cache"] == "MISS"
    assert empty.json()["count"] == 0
    assert client.get("/reports/summary", headers=surveyor).headers["X-Cache"] == "HIT"

    header = ",".join(ORIGINAL_COLUMNS)
    row = (
        "PL-0101,North Feeder Pole,pole,20.2701,85.8402,12.4,"
        '2026-08-03,John Smith,active,8,"{}"'
    )
    uploaded = client.post(
        "/ingest",
        headers=admin,
        files={"file": ("day.csv", f"{header}\n{row}\n", "text/csv")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["rows_accepted"] == 1

    refreshed = client.get("/reports/summary", headers=surveyor)
    assert refreshed.headers["X-Cache"] == "MISS"
    assert refreshed.json()["count"] == 1
