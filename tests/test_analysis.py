"""Condition bands, extent, repairs, and haversine nearest (PDF 3.4)."""

from datetime import date
from math import pi

import pytest

from utility_assets.condition import ConditionBand, condition_band
from utility_assets.geo import EARTH_RADIUS_KM, haversine_km, nearest_asset
from utility_assets.ingestion.summary import (
    assets_needing_repair,
    geographic_extent,
    per_type_stats,
    surveyors_on_date,
)


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (10, ConditionBand.GOOD),
        (8, ConditionBand.GOOD),
        (7, ConditionBand.FAIR),
        (5, ConditionBand.FAIR),
        (4, ConditionBand.POOR),
        (3, ConditionBand.POOR),
        (2, ConditionBand.CRITICAL),
        (0, ConditionBand.CRITICAL),
    ],
)
def test_condition_band_boundaries(score: int, band: ConditionBand) -> None:
    assert condition_band(score) == band


def test_one_degree_of_latitude_is_about_111_km() -> None:
    expected = EARTH_RADIUS_KM * (1 * pi / 180)
    assert haversine_km(0, 0, 1, 0) == pytest.approx(expected, rel=1e-6)


def test_same_point_is_zero_kilometres() -> None:
    assert haversine_km(20.27, 85.84, 20.27, 85.84) == pytest.approx(0.0)


def test_nearest_asset_uses_haversine_distance() -> None:
    assets = [
        {"asset_id": "PL-0101", "latitude": 20.2701, "longitude": 85.8402},
        {"asset_id": "PL-0102", "latitude": 20.3532, "longitude": 85.8214},
        {"asset_id": "TR-0401", "latitude": 20.3502, "longitude": 85.8205},
    ]
    result = nearest_asset(20.2710, 85.8400, assets)
    assert result is not None
    assert result["asset"]["asset_id"] == "PL-0101"
    assert result["distance_km"] == pytest.approx(
        haversine_km(20.2710, 85.8400, 20.2701, 85.8402), abs=0.001
    )


def test_per_type_stats_count_average_and_worst() -> None:
    assets = [
        {"asset_id": "PL-0001", "asset_type": "pole", "condition_score": 8},
        {"asset_id": "PL-0002", "asset_type": "pole", "condition_score": 4},
        {"asset_id": "VL-0001", "asset_type": "valve", "condition_score": 6},
    ]
    stats = {row["asset_type"]: row for row in per_type_stats(assets)}
    assert stats["pole"]["count"] == 2
    assert stats["pole"]["average_condition"] == 6.0
    assert stats["pole"]["worst_asset_id"] == "PL-0002"
    assert stats["valve"]["count"] == 1


def test_geographic_extent_is_the_bounding_rectangle() -> None:
    assets = [
        {"latitude": 20.25, "longitude": 85.78},
        {"latitude": 20.35, "longitude": 85.86},
        {"latitude": 20.30, "longitude": 85.80},
    ]
    assert geographic_extent(assets) == {
        "min_latitude": 20.25,
        "max_latitude": 20.35,
        "min_longitude": 85.78,
        "max_longitude": 85.86,
    }


def test_repairs_are_active_assets_below_condition_five() -> None:
    assets = [
        {"asset_id": "PL-0001", "status": "active", "condition_score": 4},
        {"asset_id": "PL-0002", "status": "active", "condition_score": 5},
        {"asset_id": "PL-0003", "status": "decommissioned", "condition_score": 1},
        {"asset_id": "PL-0004", "status": "proposed", "condition_score": 3},
        {"asset_id": "VL-0001", "status": "active", "condition_score": 2},
    ]
    repairs = [item["asset_id"] for item in assets_needing_repair(assets)]
    assert repairs == ["VL-0001", "PL-0001"]


def test_surveyors_on_a_given_day_are_distinct() -> None:
    assets = [
        {"surveyor": "John Smith", "surveyed_on": date(2026, 8, 3)},
        {"surveyor": "Rina Das", "surveyed_on": "2026-08-03"},
        {"surveyor": "John Smith", "surveyed_on": "2026-08-03"},
        {"surveyor": "Anita Sahu", "surveyed_on": "2026-08-04"},
    ]
    assert surveyors_on_date(assets, date(2026, 8, 3)) == ["John Smith", "Rina Das"]
