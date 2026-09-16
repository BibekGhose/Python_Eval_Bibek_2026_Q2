"""Cleaning rules and their boundaries (PDF 3.2 and 4.8.3)."""

import pytest

from utility_assets.cleaning import (
    CleaningError,
    clean_record,
    parse_attributes,
    parse_coordinate,
    parse_elevation,
    standardise_asset_type,
    standardise_name,
    standardise_surveyor,
)


def test_name_is_trimmed_collapsed_and_title_cased() -> None:
    assert standardise_name("  north  FEEDER   pole ") == "North Feeder Pole"


def test_name_boundary_empty_and_already_tidy() -> None:
    assert standardise_name("") == ""
    assert standardise_name(None) == ""
    assert standardise_name("Old Town Junction Pole") == "Old Town Junction Pole"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("28.6148 N", 28.6148),
        ("28.6148 n", 28.6148),
        ("28.6148 S", -28.6148),
        ("85.8 E", 85.8),
        ("85.8 W", -85.8),
        ("85.8 w", -85.8),
        ("20.2701", 20.2701),
        (20.2701, 20.2701),
        ("-85.84", -85.84),
        ("0 N", 0.0),
        ("90 S", -90.0),
    ],
)
def test_compass_coordinates_become_signed_decimals(raw: object, expected: float) -> None:
    assert parse_coordinate(raw, field="latitude") == expected


def test_coordinate_without_a_number_cannot_be_cleaned() -> None:
    with pytest.raises(CleaningError) as error:
        parse_coordinate("east-of-station", field="longitude")
    assert error.value.field == "longitude"


def test_blank_coordinate_cannot_be_cleaned() -> None:
    with pytest.raises(CleaningError):
        parse_coordinate("   ", field="latitude")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Pole", "pole"),
        ("TRANSFORMER", "transformer"),
        ("  Valve  ", "valve"),
        ("MANHOLE", "manhole"),
        ("substation", "substation"),
    ],
)
def test_asset_type_is_matched_ignoring_case(raw: str, expected: str) -> None:
    assert standardise_asset_type(raw) == expected


def test_surveyor_aliases_collapse_to_one_name() -> None:
    assert standardise_surveyor("JOHN  smith") == "John Smith"
    assert standardise_surveyor("john smith") == "John Smith"
    assert standardise_surveyor("  John   Smith ") == "John Smith"


def test_valid_attribute_json_becomes_ordinary_data() -> None:
    parsed = parse_attributes('{"height_m": 9.5, "material": "concrete"}')
    assert parsed == {"height_m": 9.5, "material": "concrete"}
    assert isinstance(parsed, dict)


def test_already_parsed_attributes_are_kept() -> None:
    assert parse_attributes({"bore_mm": 150}) == {"bore_mm": 150}


def test_invalid_attribute_json_cannot_be_cleaned() -> None:
    with pytest.raises(CleaningError) as error:
        parse_attributes("{depth_m: 2.4,}")
    assert error.value.field == "attribute_json"


def test_blank_elevation_is_not_recorded() -> None:
    assert parse_elevation("") is None
    assert parse_elevation("   ") is None
    assert parse_elevation(None) is None


def test_numeric_elevation_is_kept() -> None:
    assert parse_elevation("12.4") == 12.4
    assert parse_elevation(11) == 11.0


def test_clean_record_standardises_a_messy_handheld_row() -> None:
    cleaned = clean_record(
        {
            "asset_id": " PL-0101 ",
            "name": "  north  FEEDER   pole ",
            "asset_type": "Pole",
            "latitude": "20.2701 N",
            "longitude": "85.8410 E",
            "elevation_m": "",
            "surveyed_on": "2026-08-03",
            "surveyor": "JOHN  smith",
            "status": "Active",
            "condition_score": "8",
            "attribute_json": '{"height_m": 9.5}',
        }
    )

    assert cleaned["asset_id"] == "PL-0101"
    assert cleaned["name"] == "North Feeder Pole"
    assert cleaned["asset_type"] == "pole"
    assert cleaned["latitude"] == 20.2701
    assert cleaned["longitude"] == 85.841
    assert cleaned["elevation_m"] is None
    assert cleaned["surveyor"] == "John Smith"
    assert cleaned["status"] == "active"
    assert cleaned["attributes"] == {"height_m": 9.5}
