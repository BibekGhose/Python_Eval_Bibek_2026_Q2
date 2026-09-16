"""True distance over the curved surface of the earth, in kilometres."""

from __future__ import annotations

import math
from typing import Any

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in kilometres."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    chord = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.atan2(math.sqrt(chord), math.sqrt(1 - chord))


def _field(item: Any, *names: str) -> Any:
    for name in names:
        if isinstance(item, dict) and name in item:
            return item[name]
        if not isinstance(item, dict) and hasattr(item, name):
            value = getattr(item, name)
            if value is not None:
                return value
    return None


def nearest_asset(
    latitude: float,
    longitude: float,
    assets: list[Any],
) -> dict[str, Any] | None:
    """Return the surveyed asset closest to the given position, with distance_km."""
    best: dict[str, Any] | None = None
    best_distance = math.inf
    for asset in assets:
        asset_lat = _field(asset, "latitude")
        asset_lon = _field(asset, "longitude")
        if asset_lat is None or asset_lon is None:
            continue
        distance = haversine_km(latitude, longitude, float(asset_lat), float(asset_lon))
        asset_id = _field(asset, "asset_id")
        better = distance < best_distance
        if (
            not better
            and best is not None
            and math.isclose(distance, best_distance)
            and str(asset_id) < str(best["asset_id"])
        ):
            better = True
        if better:
            best_distance = distance
            best = {
                "asset": asset,
                "distance_km": round(distance, 3),
                "asset_id": asset_id,
            }
    if best is None:
        return None
    return {"asset": best["asset"], "distance_km": best["distance_km"]}
