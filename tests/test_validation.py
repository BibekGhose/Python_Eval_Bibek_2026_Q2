"""Every PDF 4.1 field rule, plus the decommissioned cross-rule."""

from datetime import date

import pytest

from utility_assets.validation import clean_and_validate

TODAY = date(2026, 9, 16)


def valid_row(**overrides: object) -> dict:
    row: dict = {
        "asset_id": "PL-0142",
        "name": "  north  FEEDER   pole ",
        "asset_type": "Pole",
        "latitude": "20.2701 N",
        "longitude": "85.8402",
        "elevation_m": "",
        "surveyed_on": "2026-08-03",
        "surveyor": "JOHN  smith",
        "status": "active",
        "condition_score": "8",
        "attribute_json": '{"height_m": 9.5}',
    }
    row.update(overrides)
    return row


def fields_of(result) -> set[str]:
    return {item.field for item in result.errors}


def test_valid_row_is_accepted_after_cleaning() -> None:
    result = clean_and_validate(valid_row(), today=TODAY)
    assert result.ok
    assert result.cleaned["name"] == "North Feeder Pole"
    assert result.cleaned["asset_type"] == "pole"
    assert result.cleaned["latitude"] == 20.2701
    assert result.cleaned["surveyor"] == "John Smith"
    assert result.cleaned["elevation_m"] is None
    assert result.cleaned["attributes"] == {"height_m": 9.5}


def test_missing_asset_id_is_rejected() -> None:
    result = clean_and_validate(valid_row(asset_id=""), today=TODAY)
    assert not result.ok
    assert "asset_id" in fields_of(result)


def test_malformed_asset_id_is_rejected() -> None:
    result = clean_and_validate(valid_row(asset_id="pl-0910"), today=TODAY)
    assert not result.ok
    assert "asset_id" in fields_of(result)


def test_duplicate_asset_id_on_create_is_rejected() -> None:
    result = clean_and_validate(
        valid_row(),
        existing_ids={"PL-0142"},
        require_unique_id=True,
        today=TODAY,
    )
    assert not result.ok
    assert "asset_id" in fields_of(result)


def test_name_too_short_after_tidying_is_rejected() -> None:
    result = clean_and_validate(valid_row(name="  ab  "), today=TODAY)
    assert not result.ok
    assert "name" in fields_of(result)


def test_name_too_long_after_tidying_is_rejected() -> None:
    result = clean_and_validate(valid_row(name="x" * 121), today=TODAY)
    assert not result.ok
    assert "name" in fields_of(result)


def test_unrecognised_asset_type_is_rejected() -> None:
    result = clean_and_validate(valid_row(asset_type="substation"), today=TODAY)
    assert not result.ok
    assert "asset_type" in fields_of(result)


def test_latitude_outside_range_is_rejected() -> None:
    result = clean_and_validate(valid_row(latitude="102.45"), today=TODAY)
    assert not result.ok
    assert "latitude" in fields_of(result)


def test_longitude_that_is_not_a_number_is_rejected() -> None:
    result = clean_and_validate(valid_row(longitude="east-of-station"), today=TODAY)
    assert not result.ok
    assert "longitude" in fields_of(result)


def test_blank_elevation_is_stored_as_not_recorded() -> None:
    result = clean_and_validate(valid_row(elevation_m=""), today=TODAY)
    assert result.ok
    assert result.cleaned["elevation_m"] is None


def test_non_numeric_elevation_is_rejected() -> None:
    result = clean_and_validate(valid_row(elevation_m="high"), today=TODAY)
    assert not result.ok
    assert "elevation_m" in fields_of(result)


def test_future_survey_date_is_rejected() -> None:
    result = clean_and_validate(valid_row(surveyed_on="2026-11-02"), today=TODAY)
    assert not result.ok
    assert "surveyed_on" in fields_of(result)


def test_invalid_survey_date_is_rejected() -> None:
    result = clean_and_validate(valid_row(surveyed_on="03-08-2026"), today=TODAY)
    assert not result.ok
    assert "surveyed_on" in fields_of(result)


def test_today_is_an_allowed_survey_date() -> None:
    result = clean_and_validate(valid_row(surveyed_on="2026-09-16"), today=TODAY)
    assert result.ok


def test_invalid_status_is_rejected() -> None:
    result = clean_and_validate(valid_row(status="retired"), today=TODAY)
    assert not result.ok
    assert "status" in fields_of(result)


def test_condition_score_14_is_rejected() -> None:
    result = clean_and_validate(valid_row(condition_score="14"), today=TODAY)
    assert not result.ok
    assert "condition_score" in fields_of(result)


def test_blank_condition_score_is_rejected() -> None:
    result = clean_and_validate(valid_row(condition_score=""), today=TODAY)
    assert not result.ok
    assert "condition_score" in fields_of(result)


def test_invalid_attribute_json_is_rejected() -> None:
    result = clean_and_validate(valid_row(attribute_json="{depth_m: 2.4,}"), today=TODAY)
    assert not result.ok
    assert "attribute_json" in fields_of(result)


def test_decommissioned_with_condition_above_two_is_rejected() -> None:
    result = clean_and_validate(
        valid_row(status="decommissioned", condition_score="3"),
        today=TODAY,
    )
    assert not result.ok
    assert "status" in fields_of(result)


def test_decommissioned_with_condition_two_is_accepted() -> None:
    result = clean_and_validate(
        valid_row(status="decommissioned", condition_score="2"),
        today=TODAY,
    )
    assert result.ok


def test_multiple_field_errors_are_all_named() -> None:
    result = clean_and_validate(
        valid_row(
            asset_id="",
            latitude="102.45",
            condition_score="14",
            attribute_json="{not json",
        ),
        today=TODAY,
    )
    assert fields_of(result) >= {
        "asset_id",
        "latitude",
        "condition_score",
        "attribute_json",
    }
    assert "asset_id" in result.reason_text()
    assert "latitude" in result.reason_text()
