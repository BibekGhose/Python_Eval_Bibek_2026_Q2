"""Sign in and receive an expiring credential (PDF 3.11.1)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from utility_assets.config import get_settings
from utility_assets.db import get_db
from utility_assets.schemas import LoginRequest, TokenResponse
from utility_assets.security import create_access_token
from utility_assets.services.auth import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, body.username, body.password)
    settings = get_settings()
    token = create_access_token(
        user.username,
        extra_claims={"role": str(user.role)},
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )
