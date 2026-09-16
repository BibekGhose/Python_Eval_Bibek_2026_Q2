"""Security primitives required by PDF 4.4."""

from datetime import timedelta

import pytest
from jose import jwt

from utility_assets.config import get_settings
from utility_assets.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_reversible() -> None:
    password = "correct-horse-battery"
    hashed = hash_password(password)

    assert hashed != password
    assert password not in hashed
    assert hashed.startswith("$2")
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_forged_token_is_rejected() -> None:
    token = create_access_token("admin", extra_claims={"role": "administrator"})
    forged = token[:-6] + "AAAAAA"

    with pytest.raises(InvalidTokenError):
        decode_access_token(forged)


def test_token_signed_with_another_key_is_rejected() -> None:
    other = jwt.encode(
        {"sub": "admin"},
        "not-the-application-secret",
        algorithm="HS256",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(other)


def test_expired_token_is_rejected() -> None:
    token = create_access_token("admin", expires_delta=timedelta(seconds=-1))

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_valid_token_carries_subject() -> None:
    token = create_access_token("surveyor1", extra_claims={"role": "surveyor"})
    payload = decode_access_token(token)

    assert payload["sub"] == "surveyor1"
    assert payload["role"] == "surveyor"
    assert "exp" in payload
    assert get_settings().secret_key not in token
