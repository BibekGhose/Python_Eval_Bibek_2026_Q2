"""Successful sign-in and the current-user credential (PDF 3.11, 4.8.3)."""

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from utility_assets.api.deps import get_current_user
from utility_assets.api.main import create_app
from utility_assets.db import get_db
from utility_assets.models import User
from utility_assets.security import decode_access_token

from tests.conftest import ADMIN_PASSWORD, SURVEYOR_PASSWORD


def _client(session: Session) -> TestClient:
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    @app.get("/_probe/me")
    def me(user: User = Depends(get_current_user)) -> dict[str, str]:
        return {"username": user.username, "role": str(user.role)}

    return TestClient(app)


def test_login_success(seeded_session: Session) -> None:
    response = _client(seeded_session).post(
        "/auth/login",
        json={"username": "admin", "password": ADMIN_PASSWORD},
    )
    body = response.json()
    assert response.status_code == 200
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert "password" not in body
    assert ADMIN_PASSWORD not in str(body)
    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == "admin"
    assert payload["role"] == "administrator"


def test_login_rejects_wrong_password(seeded_session: Session) -> None:
    response = _client(seeded_session).post(
        "/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    body = response.json()
    assert response.status_code == 401
    assert body["error"] == "unauthenticated"
    assert "password" not in body
    assert "wrong-password" not in str(body)


def test_login_rejects_unknown_user(seeded_session: Session) -> None:
    response = _client(seeded_session).post(
        "/auth/login",
        json={"username": "nobody", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthenticated"


def test_missing_token_is_401_not_403(seeded_session: Session) -> None:
    response = _client(seeded_session).get("/_probe/me")
    assert response.status_code == 401
    assert response.json()["error"] == "unauthenticated"


def test_bearer_token_identifies_the_signed_in_user(seeded_session: Session) -> None:
    client = _client(seeded_session)
    token = client.post(
        "/auth/login",
        json={"username": "surveyor1", "password": SURVEYOR_PASSWORD},
    ).json()["access_token"]
    response = client.get(
        "/_probe/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == {"username": "surveyor1", "role": "surveyor"}
    assert "password" not in response.json()


def test_forged_token_is_401(seeded_session: Session) -> None:
    response = _client(seeded_session).get(
        "/_probe/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthenticated"


def _login(client: TestClient, username: str, password: str) -> str:
    return client.post(
        "/auth/login",
        json={"username": username, "password": password},
    ).json()["access_token"]


def test_administrator_can_create_a_user(seeded_session: Session) -> None:
    client = _client(seeded_session)
    token = _login(client, "admin", ADMIN_PASSWORD)
    response = client.post(
        "/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "surveyor2",
            "password": "new-user-pass",
            "role": "surveyor",
        },
    )
    body = response.json()
    assert response.status_code == 201
    assert body["username"] == "surveyor2"
    assert body["role"] == "surveyor"
    assert "password" not in body
    assert "password_hash" not in body
    assert "new-user-pass" not in str(body)

    login = client.post(
        "/auth/login",
        json={"username": "surveyor2", "password": "new-user-pass"},
    )
    assert login.status_code == 200


def test_duplicate_username_is_conflict(seeded_session: Session) -> None:
    client = _client(seeded_session)
    token = _login(client, "admin", ADMIN_PASSWORD)
    response = client.post(
        "/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "surveyor1",
            "password": "another-pass",
            "role": "surveyor",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"] == "conflict"


def test_surveyor_cannot_create_a_user(seeded_session: Session) -> None:
    client = _client(seeded_session)
    token = _login(client, "surveyor1", SURVEYOR_PASSWORD)
    response = client.post(
        "/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "surveyor2",
            "password": "new-user-pass",
            "role": "surveyor",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


def test_creating_a_user_without_a_token_is_401(seeded_session: Session) -> None:
    response = _client(seeded_session).post(
        "/users",
        json={
            "username": "surveyor2",
            "password": "new-user-pass",
            "role": "surveyor",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthenticated"
