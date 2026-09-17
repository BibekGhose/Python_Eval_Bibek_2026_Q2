"""List assets and fetch one by code (PDF 3.7, 3.8)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from utility_assets.api.deps import get_current_user
from utility_assets.db import get_db
from utility_assets.models import User
from utility_assets.schemas import AssetListResponse, AssetPublic
from utility_assets.services.assets import get_asset, list_assets

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=AssetListResponse)
def list_assets_endpoint(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    asset_type: str | None = None,
    status: str | None = None,
    surveyor: str | None = None,
    condition_min: int | None = Query(default=None, ge=0, le=10),
    condition_max: int | None = Query(default=None, ge=0, le=10),
    q: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AssetListResponse:
    items, total = list_assets(
        db,
        asset_type=asset_type,
        status=status,
        surveyor=surveyor,
        condition_min=condition_min,
        condition_max=condition_max,
        q=q,
        limit=limit,
        offset=offset,
    )
    return AssetListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{asset_id}", response_model=AssetPublic)
def get_asset_endpoint(
    asset_id: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssetPublic:
    return get_asset(db, asset_id)
