"""Asset queries and writes used by the HTTP API."""

from typing import Any

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from utility_assets.api.errors import ConflictError, NotFoundError, ValidationFailed
from utility_assets.cleaning import standardise_asset_type, standardise_surveyor
from utility_assets.geo import nearest_asset
from utility_assets.models import Asset, Visit
from utility_assets.validation import clean_and_validate

SURVEY_FIELDS = frozenset({"surveyed_on", "surveyor", "condition_score", "notes"})


def get_asset(session: Session, asset_id: str) -> Asset:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise NotFoundError(f"asset {asset_id} does not exist")
    return asset


def list_assets(
    session: Session,
    *,
    asset_type: str | None = None,
    status: str | None = None,
    surveyor: str | None = None,
    condition_min: int | None = None,
    condition_max: int | None = None,
    q: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Asset], int]:
    stmt = select(Asset)
    if asset_type:
        stmt = stmt.where(Asset.asset_type == standardise_asset_type(asset_type))
    if status:
        stmt = stmt.where(Asset.status == status.strip().lower())
    if surveyor:
        stmt = stmt.where(Asset.latest_surveyor == standardise_surveyor(surveyor))
    if condition_min is not None:
        stmt = stmt.where(Asset.latest_condition_score >= condition_min)
    if condition_max is not None:
        stmt = stmt.where(Asset.latest_condition_score <= condition_max)
    if q:
        stmt = stmt.where(Asset.name.ilike(f"%{q.strip()}%"))

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        session.scalars(
            stmt.order_by(Asset.asset_id).limit(limit).offset(offset)
        ).all()
    )
    return rows, total


def save_cleaned_asset(
    session: Session,
    cleaned: dict[str, Any],
    *,
    append_visit: bool = True,
) -> Asset:
    asset = session.get(Asset, cleaned["asset_id"])
    if asset is None:
        asset = Asset(asset_id=cleaned["asset_id"])
        session.add(asset)
    asset.name = cleaned["name"]
    asset.asset_type = cleaned["asset_type"]
    asset.latitude = cleaned["latitude"]
    asset.longitude = cleaned["longitude"]
    asset.elevation_m = cleaned["elevation_m"]
    asset.status = cleaned["status"]
    asset.attributes = cleaned.get("attributes") or {}
    asset.latest_surveyed_on = cleaned["surveyed_on"]
    asset.latest_surveyor = cleaned["surveyor"]
    asset.latest_condition_score = cleaned["condition_score"]
    if append_visit:
        session.add(
            Visit(
                asset_id=cleaned["asset_id"],
                surveyed_on=cleaned["surveyed_on"],
                surveyor=cleaned["surveyor"] or "",
                condition_score=cleaned["condition_score"],
                notes=cleaned.get("notes"),
            )
        )
    return asset


def _raise_if_invalid(check) -> None:
    if not check.ok:
        raise ValidationFailed(
            [{"field": item.field, "message": item.message} for item in check.errors]
        )


def create_asset(session: Session, raw: dict[str, Any]) -> Asset:
    asset_id = str(raw.get("asset_id") or "").strip()
    if asset_id and session.get(Asset, asset_id) is not None:
        raise ConflictError(f"asset {asset_id} already exists")
    check = clean_and_validate(raw, require_unique_id=False)
    _raise_if_invalid(check)
    asset = save_cleaned_asset(session, check.cleaned, append_visit=True)
    session.commit()
    session.refresh(asset)
    return asset


def replace_asset(session: Session, asset_id: str, raw: dict[str, Any]) -> Asset:
    get_asset(session, asset_id)
    payload = {**raw, "asset_id": asset_id}
    check = clean_and_validate(payload, require_unique_id=False)
    _raise_if_invalid(check)
    asset = save_cleaned_asset(session, check.cleaned, append_visit=True)
    session.commit()
    session.refresh(asset)
    return asset


def _asset_as_raw(asset: Asset) -> dict[str, Any]:
    return {
        "asset_id": asset.asset_id,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "latitude": asset.latitude,
        "longitude": asset.longitude,
        "elevation_m": asset.elevation_m,
        "surveyed_on": asset.latest_surveyed_on,
        "surveyor": asset.latest_surveyor,
        "status": asset.status,
        "condition_score": asset.latest_condition_score,
        "attributes": asset.attributes or {},
        "notes": None,
    }


def patch_asset(session: Session, asset_id: str, updates: dict[str, Any]) -> Asset:
    asset = get_asset(session, asset_id)
    raw = _asset_as_raw(asset)
    raw.update(updates)
    raw["asset_id"] = asset_id
    check = clean_and_validate(raw, require_unique_id=False)
    _raise_if_invalid(check)
    append_visit = bool(SURVEY_FIELDS.intersection(updates.keys()))
    asset = save_cleaned_asset(session, check.cleaned, append_visit=append_visit)
    session.commit()
    session.refresh(asset)
    return asset


def delete_asset(session: Session, asset_id: str) -> None:
    asset = get_asset(session, asset_id)
    session.execute(sql_delete(Visit).where(Visit.asset_id == asset_id))
    session.delete(asset)
    session.commit()
    session.expire_all()


def list_visits(session: Session, asset_id: str) -> list[Visit]:
    get_asset(session, asset_id)
    return list(
        session.scalars(
            select(Visit)
            .where(Visit.asset_id == asset_id)
            .order_by(Visit.surveyed_on.desc(), Visit.id.desc())
        ).all()
    )


def nearest_to(session: Session, latitude: float, longitude: float) -> dict[str, Any]:
    assets = list(session.scalars(select(Asset)).all())
    result = nearest_asset(latitude, longitude, assets)
    if result is None:
        raise NotFoundError("no surveyed asset is available")
    return result
