"""Summary, repairs, frequent visits, and surveyors on a given day (PDF 3.9)."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from utility_assets.api.deps import get_current_user
from utility_assets.db import get_db
from utility_assets.models import User
from utility_assets.schemas import (
    FrequentVisitResponse,
    RepairListResponse,
    SummaryResponse,
    SurveyorsResponse,
)
from utility_assets.services.reports import (
    frequent_visits,
    get_summary,
    list_repairs,
    surveyors_for_day,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary", response_model=SummaryResponse)
def summary_endpoint(
    response: Response,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    payload, hit = get_summary(db)
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return payload


@router.get("/repairs", response_model=RepairListResponse)
def repairs_endpoint(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return {"items": list_repairs(db)}


@router.get("/frequent-visits", response_model=FrequentVisitResponse)
def frequent_visits_endpoint(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return {"items": frequent_visits(db)}


@router.get("/surveyors", response_model=SurveyorsResponse)
def surveyors_endpoint(
    date: date = Query(..., description="Calendar day in YYYY-MM-DD"),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return {"date": date, "surveyors": surveyors_for_day(db, date)}
