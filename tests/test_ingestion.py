"""Ingestion: reject-and-continue, strict abort, column check, 62-row timing."""

from __future__ import annotations

import csv
import time
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from utility_assets.ingestion.cli import build_parser
from utility_assets.ingestion.pipeline import (
    MissingColumnError,
    StrictIngestError,
    ingest_csv,
)
from utility_assets.ingestion.writers import ORIGINAL_COLUMNS
from utility_assets.models import Asset, Visit

TODAY = date(2026, 9, 16)
SAMPLE_CSV = Path("data/survey_export.csv")

GOOD_ROW = {
    "asset_id": "PL-0101",
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

BAD_ROW = {
    **GOOD_ROW,
    "asset_id": "PL-0901",
    "name": "Airport approach pole",
    "latitude": "102.45",
    "condition_score": "6",
}

SECOND_GOOD = {
    **GOOD_ROW,
    "asset_id": "VL-0201",
    "name": "unit 4 inlet valve",
    "asset_type": "valve",
    "condition_score": "7",
    "attribute_json": '{"bore_mm": 150}',
}


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str] | None = None) -> Path:
    fieldnames = columns or ORIGINAL_COLUMNS
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _ingest(session: Session, csv_path: Path, tmp_path: Path, **kwargs):
    return ingest_csv(
        csv_path,
        session,
        rejects_path=tmp_path / "rejects.csv",
        map_path=tmp_path / "assets.geojson",
        summary_path=tmp_path / "summary.txt",
        log_path=tmp_path / "ingestion.log",
        today=TODAY,
        **kwargs,
    )


def test_help_explains_usage() -> None:
    help_text = build_parser().format_help()
    assert "ingest-assets" in help_text
    assert "--strict" in help_text
    assert "--rejects" in help_text
    assert "--map" in help_text
    assert "--summary" in help_text


def test_bad_row_is_rejected_and_good_rows_are_stored(
    db_session: Session, tmp_path: Path
) -> None:
    csv_path = _write_csv(tmp_path / "mixed.csv", [GOOD_ROW, BAD_ROW, SECOND_GOOD])
    result = _ingest(db_session, csv_path, tmp_path)

    assert result.rows_read == 3
    assert result.rows_accepted == 2
    assert result.rows_rejected == 1
    assert db_session.get(Asset, "PL-0101") is not None
    assert db_session.get(Asset, "VL-0201") is not None
    assert db_session.get(Asset, "PL-0901") is None
    stored = db_session.get(Asset, "PL-0101")
    assert stored is not None
    assert stored.name == "North Feeder Pole"
    assert stored.asset_type == "pole"
    assert stored.latest_surveyor == "John Smith"
    visit_count = db_session.scalar(select(func.count()).select_from(Visit))
    assert visit_count == 2


def test_rejects_file_keeps_original_values_and_reason(
    db_session: Session, tmp_path: Path
) -> None:
    csv_path = _write_csv(tmp_path / "mixed.csv", [GOOD_ROW, BAD_ROW])
    result = _ingest(db_session, csv_path, tmp_path)

    assert result.rejects_path is not None
    with result.rejects_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["asset_id"] == "PL-0901"
    assert rows[0]["latitude"] == "102.45"
    assert rows[0]["name"] == "Airport approach pole"
    assert "latitude" in rows[0]["reason"]
    assert rows[0]["line_number"] == "3"


def test_missing_column_names_the_column_and_stops(
    db_session: Session, tmp_path: Path
) -> None:
    columns = [column for column in ORIGINAL_COLUMNS if column != "latitude"]
    csv_path = _write_csv(tmp_path / "broken.csv", [GOOD_ROW], columns=columns)

    with pytest.raises(MissingColumnError) as error:
        _ingest(db_session, csv_path, tmp_path)

    assert "latitude" in error.value.columns
    assert "latitude" in str(error.value)
    assert db_session.scalar(select(func.count()).select_from(Asset)) == 0


def test_strict_mode_aborts_and_stores_nothing(
    db_session: Session, tmp_path: Path
) -> None:
    csv_path = _write_csv(tmp_path / "mixed.csv", [GOOD_ROW, BAD_ROW, SECOND_GOOD])

    with pytest.raises(StrictIngestError) as error:
        _ingest(db_session, csv_path, tmp_path, strict=True)

    assert error.value.line_number == 3
    assert db_session.get(Asset, "PL-0101") is None
    assert db_session.get(Asset, "VL-0201") is None
    assert db_session.scalar(select(func.count()).select_from(Asset)) == 0
    assert db_session.scalar(select(func.count()).select_from(Visit)) == 0


def test_duplicate_code_in_the_same_file_rejects_the_later_row(
    db_session: Session, tmp_path: Path
) -> None:
    duplicate = {**SECOND_GOOD, "asset_id": "PL-0101", "name": "second sighting"}
    csv_path = _write_csv(tmp_path / "dup.csv", [GOOD_ROW, duplicate])
    result = _ingest(db_session, csv_path, tmp_path)

    assert result.rows_accepted == 1
    assert result.rows_rejected == 1
    assert "already in use" in result.rejected[0]["reason"]
    assert db_session.get(Asset, "PL-0101") is not None
    assert db_session.get(Asset, "PL-0101").name == "North Feeder Pole"


def test_later_file_with_same_code_appends_a_visit(
    db_session: Session, tmp_path: Path
) -> None:
    first = _write_csv(tmp_path / "day1.csv", [GOOD_ROW])
    _ingest(db_session, first, tmp_path / "day1")
    later = {
        **GOOD_ROW,
        "name": "north feeder pole resurvey",
        "surveyed_on": "2026-09-01",
        "condition_score": "4",
    }
    second = _write_csv(tmp_path / "day2.csv", [later])
    result = _ingest(db_session, second, tmp_path / "day2")

    assert result.rows_accepted == 1
    asset = db_session.get(Asset, "PL-0101")
    assert asset is not None
    assert asset.latest_condition_score == 4
    visits = db_session.scalars(select(Visit).where(Visit.asset_id == "PL-0101")).all()
    assert len(visits) == 2


def test_supplied_62_row_file_finishes_under_five_seconds(
    db_session: Session, tmp_path: Path
) -> None:
    started = time.perf_counter()
    result = _ingest(db_session, SAMPLE_CSV, tmp_path)
    elapsed = time.perf_counter() - started

    assert result.rows_read == 62
    assert result.rows_accepted == 52
    assert result.rows_rejected == 10
    assert elapsed < 5
    assert db_session.scalar(select(func.count()).select_from(Asset)) == 52
    summary = result.terminal_summary()
    assert "Rows read: 62" in summary
    assert "Rows accepted: 52" in summary
    assert "Rows rejected: 10" in summary
    assert str(result.rejects_path) in summary
