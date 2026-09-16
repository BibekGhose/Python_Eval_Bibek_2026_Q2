"""Standardise untidy handheld values before validation (PDF 3.2)."""

from __future__ import annotations

import json
import re
from typing import Any

_COORDINATE_PATTERN = re.compile(
    r"^([+-]?\d+(?:\.\d+)?)\s*([NSEW])?$",
    re.IGNORECASE,
)

class CleaningError(ValueError):
    """A value could not be standardised."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def standardise_name(value: str | None) -> str:
    """Trim, collapse repeated spaces, and apply consistent title case."""
    if value is None:
        return ""
    return collapse_whitespace(str(value)).title()


def standardise_surveyor(value: str | None) -> str:
    """Same person typed different ways becomes one name."""
    return standardise_name(value)


def standardise_asset_type(value: str | None) -> str:
    """Match asset types regardless of the letter case used in the field."""
    if value is None:
        return ""
    return collapse_whitespace(str(value)).lower()


def parse_coordinate(value: Any, *, field: str) -> float:
    """Turn a plain number or a compass reading into a signed decimal degree."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise CleaningError(field, "must be a number")
    if isinstance(value, bool):
        raise CleaningError(field, "must be a number")
    if isinstance(value, (int, float)):
        return float(value)

    text = collapse_whitespace(str(value))
    match = _COORDINATE_PATTERN.fullmatch(text)
    if match is None:
        raise CleaningError(field, "must be a number")

    magnitude = float(match.group(1))
    hemisphere = (match.group(2) or "").upper()
    if hemisphere in {"S", "W"}:
        return -abs(magnitude)
    if hemisphere in {"N", "E"}:
        return abs(magnitude)
    return magnitude


def parse_elevation(value: Any) -> float | None:
    """Blank elevation is stored as not recorded. Do not reject."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise CleaningError("elevation_m", "must be a number if present")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise CleaningError("elevation_m", "must be a number if present") from exc


def parse_attributes(value: Any) -> Any:
    """Parse the attribute snippet so values are ordinary data, not a string."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise CleaningError("attribute_json", "must be valid JSON")
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise CleaningError("attribute_json", "must be valid JSON") from exc


def clean_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Apply every 3.2 rule. Range and presence checks belong to validation."""
    return {
        "asset_id": collapse_whitespace(str(raw.get("asset_id") or "")),
        "name": standardise_name(raw.get("name")),
        "asset_type": standardise_asset_type(raw.get("asset_type")),
        "latitude": parse_coordinate(raw.get("latitude"), field="latitude"),
        "longitude": parse_coordinate(raw.get("longitude"), field="longitude"),
        "elevation_m": parse_elevation(raw.get("elevation_m")),
        "surveyed_on": collapse_whitespace(str(raw.get("surveyed_on") or "")),
        "surveyor": standardise_surveyor(raw.get("surveyor")),
        "status": collapse_whitespace(str(raw.get("status") or "")).lower(),
        "condition_score": raw.get("condition_score"),
        "attributes": parse_attributes(raw.get("attribute_json", raw.get("attributes"))),
        "notes": raw.get("notes"),
    }
