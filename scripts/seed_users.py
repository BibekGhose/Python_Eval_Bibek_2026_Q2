"""Create the local admin and surveyor accounts. Passwords come from the environment."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow `python scripts/seed_users.py` without an editable install.
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sqlalchemy import select

from utility_assets.db import get_session_factory, init_db
from utility_assets.models import User, UserRole
from utility_assets.security import hash_password


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} must be set in the environment (see .env.example).")
    return value


def _ensure_sqlite_parent() -> None:
    url = os.environ.get("DATABASE_URL", "")
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith("sqlite:///:memory:"):
        db_path = Path(url.removeprefix(prefix))
        if db_path.parent and str(db_path.parent) not in {".", ""}:
            db_path.parent.mkdir(parents=True, exist_ok=True)


def _upsert_user(session, username: str, password: str, role: UserRole) -> str:
    existing = session.scalar(select(User).where(User.username == username))
    if existing is not None:
        return "exists"
    session.add(
        User(
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
    )
    return "created"


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
    admin_password = _required_env("SEED_ADMIN_PASSWORD")
    surveyor_password = _required_env("SEED_SURVEYOR_PASSWORD")

    _ensure_sqlite_parent()
    init_db()
    session = get_session_factory()()
    try:
        admin_result = _upsert_user(
            session, "admin", admin_password, UserRole.ADMINISTRATOR
        )
        surveyor_result = _upsert_user(
            session, "surveyor1", surveyor_password, UserRole.SURVEYOR
        )
        session.commit()
    finally:
        session.close()

    print(f"admin: {admin_result}")
    print(f"surveyor1: {surveyor_result}")


if __name__ == "__main__":
    main()
