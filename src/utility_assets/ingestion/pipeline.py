"""Load a daily CSV: clean, validate, persist, and write output files."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, TextIO

from sqlalchemy.orm import Session

from utility_assets.ingestion.writers import (
    ORIGINAL_COLUMNS,
    append_ingest_log,
    write_geojson,
    write_rejects,
    write_summary,
)
from utility_assets.models import Asset, Visit
from utility_assets.validation import clean_and_validate

DEFAULT_REJECTS_PATH = Path("data/output/rejects.csv")
DEFAULT_MAP_PATH = Path("data/output/assets.geojson")
DEFAULT_SUMMARY_PATH = Path("data/output/summary.txt")


class MissingColumnError(Exception):
    def __init__(self, columns: list[str]) -> None:
        self.columns = columns
        listed = ", ".join(columns)
        super().__init__(f"CSV is missing required column(s): {listed}")


class StrictIngestError(Exception):
    def __init__(self, line_number: int, reason: str) -> None:
        self.line_number = line_number
        self.reason = reason
        super().__init__(
            f"strict mode: rejected row at line {line_number}; nothing was stored"
        )


@dataclass
class IngestResult:
    rows_read: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    rejects_path: Path | None = None
    map_path: Path | None = None
    summary_path: Path | None = None
    accepted: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    aborted: bool = False

    def terminal_summary(self) -> str:
        rejects = self.rejects_path if self.rejects_path is not None else ""
        return (
            f"Rows read: {self.rows_read}\n"
            f"Rows accepted: {self.rows_accepted}\n"
            f"Rows rejected: {self.rows_rejected}\n"
            f"Rejects file: {rejects}"
        )


def required_columns_present(fieldnames: list[str] | None) -> list[str]:
    present = {name.lstrip("\ufeff").strip() for name in (fieldnames or [])}
    return [column for column in ORIGINAL_COLUMNS if column not in present]


def persist_cleaned(session: Session, cleaned: dict[str, Any]) -> None:
    """Insert a new asset or append a visit when the code is already stored."""
    asset = session.get(Asset, cleaned["asset_id"])
    if asset is None:
        asset = Asset(asset_id=cleaned["asset_id"])
        session.add(asset)
    asset.name = cleaned["name"]
    asset.asset_type = cleaned["asset_type"]
    asset.latitude = cleaned["latitude"]
    asset.longitude = cleaned["longitude"]
    asset.elevation_m = cleaned["elevation_m"]
    asset.status = cleaned["status"]
    asset.attributes = cleaned.get("attributes") or {}
    asset.latest_surveyed_on = cleaned["surveyed_on"]
    asset.latest_surveyor = cleaned["surveyor"]
    asset.latest_condition_score = cleaned["condition_score"]
    session.add(
        Visit(
            asset_id=cleaned["asset_id"],
            surveyed_on=cleaned["surveyed_on"],
            surveyor=cleaned["surveyor"] or "",
            condition_score=cleaned["condition_score"],
            notes=cleaned.get("notes"),
        )
    )


def ingest_csv(
    csv_path: str | Path,
    session: Session,
    *,
    rejects_path: str | Path | None = DEFAULT_REJECTS_PATH,
    map_path: str | Path | None = DEFAULT_MAP_PATH,
    summary_path: str | Path | None = DEFAULT_SUMMARY_PATH,
    log_path: str | Path | None = None,
    strict: bool = False,
    today: date | None = None,
    source: TextIO | None = None,
) -> IngestResult:
    path = Path(csv_path)
    handle = source
    close_handle = False
    if handle is None:
        handle = path.open(encoding="utf-8-sig", newline="")
        close_handle = True

    result = IngestResult()
    seen_in_file: set[str] = set()
    try:
        reader = csv.DictReader(handle)
        missing = required_columns_present(reader.fieldnames)
        if missing:
            raise MissingColumnError(missing)

        for line_number, raw in enumerate(reader, start=2):
            result.rows_read += 1
            check = clean_and_validate(
                raw,
                existing_ids=seen_in_file,
                require_unique_id=True,
                today=today,
            )
            if not check.ok:
                rejected_row = {column: raw.get(column, "") for column in ORIGINAL_COLUMNS}
                rejected_row["line_number"] = line_number
                rejected_row["reason"] = check.reason_text()
                result.rejected.append(rejected_row)
                if strict:
                    session.rollback()
                    result.aborted = True
                    raise StrictIngestError(line_number, check.reason_text())
                continue

            persist_cleaned(session, check.cleaned)
            seen_in_file.add(check.cleaned["asset_id"])
            result.accepted.append(check.cleaned)

        session.commit()
    except StrictIngestError:
        session.rollback()
        result.rows_accepted = 0
        result.rows_rejected = len(result.rejected)
        if log_path is not None:
            append_ingest_log(
                log_path,
                csv_path=str(csv_path),
                rows_read=result.rows_read,
                rows_accepted=0,
                rows_rejected=result.rows_rejected,
                strict=True,
            )
        raise
    finally:
        if close_handle:
            handle.close()

    result.rows_accepted = len(result.accepted)
    result.rows_rejected = len(result.rejected)

    if rejects_path is not None:
        result.rejects_path = write_rejects(rejects_path, result.rejected)
    if map_path is not None:
        result.map_path = write_geojson(map_path, result.accepted)
    if summary_path is not None:
        result.summary_path = write_summary(
            summary_path,
            result.accepted,
            rows_read=result.rows_read,
            rows_accepted=result.rows_accepted,
            rows_rejected=result.rows_rejected,
        )
    if log_path is not None:
        append_ingest_log(
            log_path,
            csv_path=str(csv_path),
            rows_read=result.rows_read,
            rows_accepted=result.rows_accepted,
            rows_rejected=result.rows_rejected,
            strict=strict,
        )
    return result
