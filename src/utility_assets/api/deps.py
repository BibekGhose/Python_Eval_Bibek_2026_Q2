"""Database session and the signed-in user for HTTP handlers."""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from utility_assets.api.errors import UnauthenticatedError
from utility_assets.db import get_db
from utility_assets.models import User
from utility_assets.security import InvalidTokenError, decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Require a valid, unexpired bearer token. Missing or bad token is 401, not 403."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthenticatedError("sign in required")
    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise UnauthenticatedError("credential is invalid or expired") from None
    username = payload.get("sub")
    if not username:
        raise UnauthenticatedError("credential is invalid or expired")
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active:
        raise UnauthenticatedError("credential is invalid or expired")
    request.state.username = user.username
    return user
