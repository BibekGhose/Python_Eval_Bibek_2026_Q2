"""Asset queries used by the HTTP list and fetch operations."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from utility_assets.api.errors import NotFoundError
from utility_assets.cleaning import standardise_asset_type, standardise_surveyor
from utility_assets.models import Asset


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
