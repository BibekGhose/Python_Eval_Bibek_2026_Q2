"""Analysis figures for the text summary and later HTTP reports (PDF 3.4)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from utility_assets.condition import condition_band
from utility_assets.geo import _field, nearest_asset


def _score(item: Any) -> int | None:
    value = _field(item, "condition_score", "latest_condition_score")
    if value is None:
        return None
    return int(value)


def _status(item: Any) -> str:
    return str(_field(item, "status") or "").lower()


def _type(item: Any) -> str:
    return str(_field(item, "asset_type") or "").lower()


def per_type_stats(assets: list[Any]) -> list[dict[str, Any]]:
    """Count, average condition, and worst-condition asset for each type."""
    grouped: dict[str, list[Any]] = defaultdict(list)
    for asset in assets:
        grouped[_type(asset)].append(asset)

    rows: list[dict[str, Any]] = []
    for asset_type in sorted(grouped):
        group = grouped[asset_type]
        scores = [(asset, _score(asset)) for asset in group]
        numeric = [(asset, score) for asset, score in scores if score is not None]
        average = (
            round(sum(score for _, score in numeric) / len(numeric), 2) if numeric else None
        )
        worst = None
        if numeric:
            worst_asset, _ = min(
                numeric,
                key=lambda pair: (pair[1], str(_field(pair[0], "asset_id"))),
            )
            worst = _field(worst_asset, "asset_id")
        rows.append(
            {
                "asset_type": asset_type,
                "count": len(group),
                "average_condition": average,
                "worst_asset_id": worst,
            }
        )
    return rows


def geographic_extent(assets: list[Any]) -> dict[str, float] | None:
    """Bounding rectangle of every accepted point, for the map's initial view."""
    latitudes: list[float] = []
    longitudes: list[float] = []
    for asset in assets:
        lat = _field(asset, "latitude")
        lon = _field(asset, "longitude")
        if lat is None or lon is None:
            continue
        latitudes.append(float(lat))
        longitudes.append(float(lon))
    if not latitudes:
        return None
    return {
        "min_latitude": min(latitudes),
        "max_latitude": max(latitudes),
        "min_longitude": min(longitudes),
        "max_longitude": max(longitudes),
    }


def assets_needing_repair(assets: list[Any]) -> list[Any]:
    """Still in service with condition below 5."""
    repairs = [
        asset
        for asset in assets
        if _status(asset) == "active" and (_score(asset) is not None and _score(asset) < 5)
    ]
    return sorted(repairs, key=lambda asset: (_score(asset), str(_field(asset, "asset_id"))))


def surveyors_on_date(assets: list[Any], day: date) -> list[str]:
    names: set[str] = set()
    for asset in assets:
        surveyed = _field(asset, "surveyed_on", "latest_surveyed_on")
        if surveyed is None:
            continue
        if isinstance(surveyed, date):
            surveyed_day = surveyed
        else:
            surveyed_day = date.fromisoformat(str(surveyed)[:10])
        if surveyed_day == day:
            surveyor = _field(asset, "surveyor", "latest_surveyor")
            if surveyor:
                names.add(str(surveyor))
    return sorted(names)


def summarise_assets(assets: list[Any]) -> dict[str, Any]:
    return {
        "by_type": per_type_stats(assets),
        "extent": geographic_extent(assets),
        "repairs": [
            {
                "asset_id": _field(asset, "asset_id"),
                "asset_type": _type(asset),
                "condition_score": _score(asset),
                "condition_band": condition_band(_score(asset)).value
                if _score(asset) is not None
                else None,
            }
            for asset in assets_needing_repair(assets)
        ],
        "count": len(assets),
    }


def nearest(latitude: float, longitude: float, assets: list[Any]) -> dict[str, Any] | None:
    return nearest_asset(latitude, longitude, assets)
