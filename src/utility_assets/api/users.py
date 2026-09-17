"""Administrators create further user accounts (PDF 3.11.4)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from utility_assets.api.deps import get_current_admin
from utility_assets.api.errors import ConflictError
from utility_assets.db import get_db
from utility_assets.models import User
from utility_assets.schemas import UserCreate, UserPublic
from utility_assets.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> User:
    existing = db.scalar(select(User).where(User.username == body.username))
    if existing is not None:
        raise ConflictError(f"username {body.username} is already in use")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
