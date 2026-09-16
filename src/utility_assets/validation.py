"""Field rules shared by CSV ingestion and the HTTP API (PDF 4.1)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

from utility_assets.cleaning import (
    CleaningError,
    collapse_whitespace,
    parse_attributes,
    parse_coordinate,
    parse_elevation,
    standardise_asset_type,
    standardise_name,
    standardise_surveyor,
)

ASSET_ID_PATTERN = re.compile(r"^[A-Z]{2}-[0-9]{4}$")
ASSET_TYPES = frozenset({"pole", "valve", "manhole", "transformer"})
STATUSES = frozenset({"active", "decommissioned", "proposed"})


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


@dataclass
class RecordCheck:
    cleaned: dict[str, Any] = field(default_factory=dict)
    errors: list[FieldError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def reason_text(self) -> str:
        return "; ".join(f"{item.field}: {item.message}" for item in self.errors)


def _add(errors: list[FieldError], field_name: str, message: str) -> None:
    errors.append(FieldError(field=field_name, message=message))


def _parse_condition(value: Any) -> int:
    if value is None or (isinstance(value, str) and not str(value).strip()):
        raise ValueError("must be a whole number between 0 and 10")
    if isinstance(value, bool):
        raise ValueError("must be a whole number between 0 and 10")
    if isinstance(value, int):
        number = value
    elif isinstance(value, float):
        if not value.is_integer():
            raise ValueError("must be a whole number between 0 and 10")
        number = int(value)
    else:
        text = str(value).strip()
        try:
            as_float = float(text)
        except ValueError as exc:
            raise ValueError("must be a whole number between 0 and 10") from exc
        if not as_float.is_integer():
            raise ValueError("must be a whole number between 0 and 10")
        number = int(as_float)
    if number < 0 or number > 10:
        raise ValueError("must be a whole number between 0 and 10")
    return number


def _parse_survey_date(value: Any, today: date) -> date:
    if isinstance(value, datetime):
        surveyed = value.date()
    elif isinstance(value, date):
        surveyed = value
    elif value is None or (isinstance(value, str) and not str(value).strip()):
        raise ValueError("must be a valid date not later than today")
    else:
        try:
            surveyed = date.fromisoformat(str(value).strip())
        except ValueError as exc:
            raise ValueError("must be a valid date not later than today") from exc
    if surveyed > today:
        raise ValueError("must not be later than today")
    return surveyed


def clean_and_validate(
    raw: dict[str, Any],
    *,
    existing_ids: Iterable[str] | None = None,
    require_unique_id: bool = True,
    today: date | None = None,
) -> RecordCheck:
    """Clean first, then apply every 4.1 rule. Collect every field error."""
    today = today or date.today()
    used_ids = set(existing_ids or [])
    errors: list[FieldError] = []
    cleaned: dict[str, Any] = {}

    asset_id = collapse_whitespace(str(raw.get("asset_id") or ""))
    cleaned["asset_id"] = asset_id
    if not asset_id:
        _add(errors, "asset_id", "must be present")
    elif ASSET_ID_PATTERN.fullmatch(asset_id) is None:
        _add(
            errors,
            "asset_id",
            "must be two capital letters, a hyphen, and four digits",
        )
    elif require_unique_id and asset_id in used_ids:
        _add(errors, "asset_id", "is already in use")

    name = standardise_name(raw.get("name"))
    cleaned["name"] = name
    if not name:
        _add(errors, "name", "must be present")
    elif len(name) < 3 or len(name) > 120:
        _add(errors, "name", "must be between 3 and 120 characters after tidying")

    asset_type = standardise_asset_type(raw.get("asset_type"))
    cleaned["asset_type"] = asset_type
    if asset_type not in ASSET_TYPES:
        _add(errors, "asset_type", "must be one of pole, valve, manhole, transformer")

    try:
        latitude = parse_coordinate(raw.get("latitude"), field="latitude")
        cleaned["latitude"] = latitude
        if latitude < -90 or latitude > 90:
            _add(errors, "latitude", "must be a number between -90 and 90")
    except CleaningError as exc:
        cleaned["latitude"] = raw.get("latitude")
        _add(errors, exc.field, exc.message)

    try:
        longitude = parse_coordinate(raw.get("longitude"), field="longitude")
        cleaned["longitude"] = longitude
        if longitude < -180 or longitude > 180:
            _add(errors, "longitude", "must be a number between -180 and 180")
    except CleaningError as exc:
        cleaned["longitude"] = raw.get("longitude")
        _add(errors, exc.field, exc.message)

    try:
        cleaned["elevation_m"] = parse_elevation(raw.get("elevation_m"))
    except CleaningError as exc:
        cleaned["elevation_m"] = raw.get("elevation_m")
        _add(errors, exc.field, exc.message)

    try:
        cleaned["surveyed_on"] = _parse_survey_date(raw.get("surveyed_on"), today)
    except ValueError as exc:
        cleaned["surveyed_on"] = raw.get("surveyed_on")
        _add(errors, "surveyed_on", str(exc))

    cleaned["surveyor"] = standardise_surveyor(raw.get("surveyor"))

    status = collapse_whitespace(str(raw.get("status") or "")).lower()
    cleaned["status"] = status
    if status not in STATUSES:
        _add(errors, "status", "must be one of active, decommissioned, proposed")

    try:
        condition_score = _parse_condition(raw.get("condition_score"))
        cleaned["condition_score"] = condition_score
    except ValueError as exc:
        condition_score = None
        cleaned["condition_score"] = raw.get("condition_score")
        _add(errors, "condition_score", str(exc))

    try:
        cleaned["attributes"] = parse_attributes(
            raw.get("attribute_json", raw.get("attributes"))
        )
    except CleaningError as exc:
        cleaned["attributes"] = raw.get("attribute_json", raw.get("attributes"))
        _add(errors, exc.field, exc.message)

    if status == "decommissioned" and condition_score is not None and condition_score > 2:
        _add(
            errors,
            "status",
            "decommissioned assets may not have condition_score above 2",
        )

    cleaned["notes"] = raw.get("notes")
    return RecordCheck(cleaned=cleaned, errors=errors)
