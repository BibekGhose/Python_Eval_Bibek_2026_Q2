"""Six asset operations, visit history, and nearest asset (PDF 3.7–3.8, 3.6.5)."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from utility_assets.api.deps import get_current_admin, get_current_user
from utility_assets.db import get_db
from utility_assets.models import User
from utility_assets.schemas import (
    AssetListResponse,
    AssetPatch,
    AssetPublic,
    AssetWrite,
    NearestResponse,
    VisitListResponse,
)
from utility_assets.services.assets import (
    create_asset,
    delete_asset,
    get_asset,
    list_assets,
    list_visits,
    nearest_to,
    patch_asset,
    replace_asset,
)

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


@router.post("", response_model=AssetPublic, status_code=status.HTTP_201_CREATED)
def create_asset_endpoint(
    body: AssetWrite,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssetPublic:
    return create_asset(db, body.model_dump())


@router.get("/nearest", response_model=NearestResponse)
def nearest_asset_endpoint(
    latitude: float = Query(...),
    longitude: float = Query(...),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NearestResponse:
    result = nearest_to(db, latitude, longitude)
    return NearestResponse(distance_km=result["distance_km"], asset=result["asset"])


@router.get("/{asset_id}/visits", response_model=VisitListResponse)
def list_visits_endpoint(
    asset_id: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VisitListResponse:
    items = list_visits(db, asset_id)
    return VisitListResponse(asset_id=asset_id, items=items)


@router.get("/{asset_id}", response_model=AssetPublic)
def get_asset_endpoint(
    asset_id: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssetPublic:
    return get_asset(db, asset_id)


@router.put("/{asset_id}", response_model=AssetPublic)
def replace_asset_endpoint(
    asset_id: str,
    body: AssetWrite,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssetPublic:
    payload = body.model_dump()
    payload["asset_id"] = asset_id
    return replace_asset(db, asset_id, payload)


@router.patch("/{asset_id}", response_model=AssetPublic)
def patch_asset_endpoint(
    asset_id: str,
    body: AssetPatch,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssetPublic:
    return patch_asset(db, asset_id, body.model_dump(exclude_unset=True))


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset_endpoint(
    asset_id: str,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Response:
    delete_asset(db, asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
