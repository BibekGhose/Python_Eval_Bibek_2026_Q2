"""Authentication service: verify a username and password."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from utility_assets.api.errors import UnauthenticatedError
from utility_assets.models import User
from utility_assets.security import verify_password


def authenticate_user(session: Session, username: str, password: str) -> User:
    user = session.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active:
        raise UnauthenticatedError("incorrect username or password")
    if not verify_password(password, user.password_hash):
        raise UnauthenticatedError("incorrect username or password")
    return user
