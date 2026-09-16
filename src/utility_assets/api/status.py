"""Unprotected status address for the utility's monitoring system (PDF 3.9.4)."""

from fastapi import APIRouter

router = APIRouter(tags=["status"])


@router.get("/status")
def get_status() -> dict[str, str]:
    """Confirm the application is running. No sign-in required."""
    return {"status": "ok"}
