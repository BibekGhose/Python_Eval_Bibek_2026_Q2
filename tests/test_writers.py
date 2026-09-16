"""Output writers for rejects, GeoJSON, text summary, and ingest log."""

import csv
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from utility_assets.ingestion.writers import (
    append_ingest_log,
    format_summary_report,
    write_geojson,
    write_rejects,
    write_summary,
)

IST = timezone(timedelta(hours=5, minutes=30))
RUN_AT = datetime(2026, 9, 15, 22, 10, 3, tzinfo=IST)


def test_rejects_keep_original_values_and_list_every_reason(tmp_path: Path) -> None:
    original = {
        "asset_id": "",
        "name": "Nameless chamber",
        "asset_type": "manhole",
        "latitude": "20.2708",
        "longitude": "85.8418",
        "elevation_m": "2.0",
        "surveyed_on": "2026-08-31",
        "surveyor": "Rina Das",
        "status": "active",
        "condition_score": "4",
        "attribute_json": '{"depth_m": 2.0}',
        "line_number": 56,
        "reason": "asset_id: must be present; latitude: must be a number between -90 and 90",
    }
    path = write_rejects(tmp_path / "rejects.csv", [original])
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["asset_id"] == ""
    assert rows[0]["name"] == "Nameless chamber"
    assert rows[0]["line_number"] == "56"
    assert "asset_id: must be present" in rows[0]["reason"]
    assert "latitude:" in rows[0]["reason"]
    assert "reason" in rows[0]
    assert list(rows[0].keys())[-2:] == ["line_number", "reason"]


def test_geojson_is_a_feature_collection_with_lon_lat_points(tmp_path: Path) -> None:
    accepted = [
        {
            "asset_id": "PL-0101",
            "name": "North Feeder Pole",
            "asset_type": "pole",
            "status": "active",
            "condition_score": 8,
            "surveyor": "John Smith",
            "surveyed_on": date(2026, 8, 3),
            "elevation_m": None,
            "latitude": 20.2701,
            "longitude": 85.8402,
            "attributes": {"height_m": 9.5},
        }
    ]
    path = write_geojson(tmp_path / "assets.geojson", accepted)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["type"] == "FeatureCollection"
    feature = payload["features"][0]
    assert feature["geometry"]["type"] == "Point"
    assert feature["geometry"]["coordinates"] == [85.8402, 20.2701]
    props = feature["properties"]
    assert props["asset_id"] == "PL-0101"
    assert props["condition_band"] == "GOOD"
    assert props["elevation_m"] is None
    assert props["attributes"] == {"height_m": 9.5}
    assert props["surveyed_on"] == "2026-08-03"


def test_summary_report_is_aligned_and_includes_totals() -> None:
    accepted = [
        {
            "asset_id": "PL-0001",
            "asset_type": "pole",
            "condition_score": 8,
            "latitude": 20.25,
            "longitude": 85.78,
        },
        {
            "asset_id": "PL-0002",
            "asset_type": "pole",
            "condition_score": 4,
            "latitude": 20.35,
            "longitude": 85.86,
        },
    ]
    text = format_summary_report(
        accepted,
        rows_read=62,
        rows_accepted=2,
        rows_rejected=10,
        run_at=RUN_AT,
    )
    assert text.startswith("Utility asset survey summary")
    assert "Run at: 2026-09-15T22:10:03+05:30" in text
    assert "pole" in text
    assert "PL-0002" in text
    assert "20.2500 to 20.3500" in text
    assert "Totals: read 62  accepted 2  rejected 10" in text


def test_summary_file_is_written(tmp_path: Path) -> None:
    path = write_summary(
        tmp_path / "summary.txt",
        [],
        rows_read=0,
        rows_accepted=0,
        rows_rejected=0,
        run_at=RUN_AT,
    )
    assert "no accepted assets" in path.read_text(encoding="utf-8")


def test_ingest_log_appends_a_dated_line(tmp_path: Path) -> None:
    log_path = tmp_path / "ingestion.log"
    append_ingest_log(
        log_path,
        csv_path="data/survey_export.csv",
        rows_read=62,
        rows_accepted=52,
        rows_rejected=10,
        strict=False,
        run_at=RUN_AT,
    )
    append_ingest_log(
        log_path,
        csv_path="data/survey_export.csv",
        rows_read=10,
        rows_accepted=10,
        rows_rejected=0,
        strict=True,
        run_at=RUN_AT,
    )
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("2026-09-15T22:10:03+05:30")
    assert "file=data/survey_export.csv" in lines[0]
    assert "read=62" in lines[0]
    assert "accepted=52" in lines[0]
    assert "rejected=10" in lines[0]
    assert "strict=false" in lines[0]
    assert "strict=true" in lines[1]
