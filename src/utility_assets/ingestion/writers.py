"""Write rejects, GeoJSON map, text summary, and the accumulating ingest log."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from utility_assets.condition import condition_band
from utility_assets.ingestion.summary import geographic_extent, per_type_stats

ORIGINAL_COLUMNS = [
    "asset_id",
    "name",
    "asset_type",
    "latitude",
    "longitude",
    "elevation_m",
    "surveyed_on",
    "surveyor",
    "status",
    "condition_score",
    "attribute_json",
]

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    return datetime.now(tz=IST)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_rejects(path: str | Path, rejected: Iterable[Mapping[str, Any]]) -> Path:
    """Keep every original value and add line_number plus a combined reason."""
    target = Path(path)
    _ensure_parent(target)
    fieldnames = [*ORIGINAL_COLUMNS, "line_number", "reason"]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rejected:
            out = {column: row.get(column, "") for column in ORIGINAL_COLUMNS}
            out["line_number"] = row.get("line_number", "")
            out["reason"] = row.get("reason", "")
            writer.writerow(out)
    return target


def _surveyed_on_text(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def accepted_to_feature(asset: Mapping[str, Any]) -> dict[str, Any]:
    score = int(asset["condition_score"])
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(asset["longitude"]), float(asset["latitude"])],
        },
        "properties": {
            "asset_id": asset["asset_id"],
            "name": asset["name"],
            "asset_type": asset["asset_type"],
            "status": asset["status"],
            "condition_score": score,
            "condition_band": condition_band(score).value,
            "surveyor": asset.get("surveyor"),
            "surveyed_on": _surveyed_on_text(asset.get("surveyed_on")),
            "elevation_m": asset.get("elevation_m"),
            "attributes": asset.get("attributes") or {},
        },
    }


def write_geojson(path: str | Path, accepted: Iterable[Mapping[str, Any]]) -> Path:
    """Standard GeoJSON FeatureCollection. Coordinates are [longitude, latitude]."""
    target = Path(path)
    _ensure_parent(target)
    collection = {
        "type": "FeatureCollection",
        "features": [accepted_to_feature(asset) for asset in accepted],
    }
    target.write_text(json.dumps(collection, indent=2), encoding="utf-8")
    return target


def format_summary_report(
    accepted: list[Mapping[str, Any]],
    *,
    rows_read: int,
    rows_accepted: int,
    rows_rejected: int,
    run_at: datetime | None = None,
) -> str:
    stamp = (run_at or now_ist()).isoformat(timespec="seconds")
    stats = per_type_stats(list(accepted))
    extent = geographic_extent(list(accepted))
    lines = [
        "Utility asset survey summary",
        f"Run at: {stamp}",
        "",
        f"{'Type':<14}{'Count':>8}{'Avg condition':>16}{'Worst asset':>14}",
    ]
    if stats:
        for row in stats:
            average = (
                f"{row['average_condition']:.2f}"
                if row["average_condition"] is not None
                else "-"
            )
            worst = row["worst_asset_id"] or "-"
            lines.append(
                f"{row['asset_type']:<14}{row['count']:>8}{average:>16}{worst:>14}"
            )
    else:
        lines.append("(no accepted assets)")
    lines.append("")
    lines.append("Survey extent:")
    if extent:
        lines.append(
            f"  latitude  {extent['min_latitude']:.4f} to {extent['max_latitude']:.4f}"
        )
        lines.append(
            f"  longitude {extent['min_longitude']:.4f} to {extent['max_longitude']:.4f}"
        )
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append(
        f"Totals: read {rows_read}  accepted {rows_accepted}  rejected {rows_rejected}"
    )
    lines.append("")
    return "\n".join(lines)


def write_summary(
    path: str | Path,
    accepted: list[Mapping[str, Any]],
    *,
    rows_read: int,
    rows_accepted: int,
    rows_rejected: int,
    run_at: datetime | None = None,
) -> Path:
    target = Path(path)
    _ensure_parent(target)
    target.write_text(
        format_summary_report(
            accepted,
            rows_read=rows_read,
            rows_accepted=rows_accepted,
            rows_rejected=rows_rejected,
            run_at=run_at,
        ),
        encoding="utf-8",
    )
    return target


def append_ingest_log(
    path: str | Path,
    *,
    csv_path: str,
    rows_read: int,
    rows_accepted: int,
    rows_rejected: int,
    strict: bool,
    run_at: datetime | None = None,
) -> Path:
    """Append one dated line so later we can see which days were loaded."""
    target = Path(path)
    _ensure_parent(target)
    stamp = (run_at or now_ist()).isoformat(timespec="seconds")
    line = (
        f"{stamp}  file={csv_path}  read={rows_read}  "
        f"accepted={rows_accepted}  rejected={rows_rejected}  "
        f"strict={'true' if strict else 'false'}\n"
    )
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return target
