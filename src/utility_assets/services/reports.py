"""Machine-readable reports over stored assets and visits (PDF 3.4, 3.9)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from utility_assets.condition import condition_band
from utility_assets.ingestion.summary import (
    assets_needing_repair,
    geographic_extent,
    per_type_stats,
)
from utility_assets.models import Asset, Visit
from utility_assets.services.cache import SUMMARY_CACHE_KEY, summary_cache


def _repair_item(asset: Asset) -> dict[str, Any]:
    score = int(asset.latest_condition_score)
    return {
        "asset_id": asset.asset_id,
        "name": asset.name,
        "asset_type": str(asset.asset_type),
        "status": str(asset.status),
        "condition_score": score,
        "condition_band": condition_band(score).value,
    }


def _all_assets(session: Session) -> list[Asset]:
    return list(session.scalars(select(Asset).order_by(Asset.asset_id)).all())


def build_summary(session: Session) -> dict[str, Any]:
    assets = _all_assets(session)
    return {
        "by_type": per_type_stats(assets),
        "extent": geographic_extent(assets),
        "repairs": [_repair_item(asset) for asset in assets_needing_repair(assets)],
        "count": len(assets),
    }


def get_summary(session: Session) -> tuple[dict[str, Any], bool]:
    """Return (payload, cache_hit). HIT only when an unexpired summary is stored."""
    cached = summary_cache.get(SUMMARY_CACHE_KEY)
    if cached is not None:
        return cached, True
    payload = build_summary(session)
    summary_cache.set(SUMMARY_CACHE_KEY, payload)
    return payload, False


def list_repairs(session: Session) -> list[dict[str, Any]]:
    return [_repair_item(asset) for asset in assets_needing_repair(_all_assets(session))]


def frequent_visits(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(Visit.asset_id, Asset.name, func.count(Visit.id).label("visit_count"))
        .join(Asset, Asset.asset_id == Visit.asset_id)
        .group_by(Visit.asset_id, Asset.name)
        .order_by(func.count(Visit.id).desc(), Visit.asset_id.asc())
    ).all()
    return [
        {
            "asset_id": asset_id,
            "name": name,
            "visit_count": visit_count,
        }
        for asset_id, name, visit_count in rows
    ]


def surveyors_for_day(session: Session, day: date) -> list[str]:
    names = session.scalars(
        select(Visit.surveyor).where(Visit.surveyed_on == day).distinct()
    ).all()
    return sorted({name for name in names if name})
