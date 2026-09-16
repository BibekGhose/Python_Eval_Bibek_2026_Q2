"""Command-line ingestion tool for a night-shift operator (PDF 3.1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from utility_assets.config import get_settings
from utility_assets.db import get_session_factory, init_db
from utility_assets.ingestion.pipeline import (
    DEFAULT_MAP_PATH,
    DEFAULT_REJECTS_PATH,
    DEFAULT_SUMMARY_PATH,
    MissingColumnError,
    StrictIngestError,
    ingest_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ingest-assets",
        description=(
            "Load a day's handheld GPS export, store trusted rows, "
            "and set unusable rows aside with a reason."
        ),
    )
    parser.add_argument(
        "csv_path",
        help="Path to the CSV file exported by the handheld unit",
    )
    parser.add_argument(
        "--rejects",
        default=str(DEFAULT_REJECTS_PATH),
        help=f"Where to write rejected rows (default: {DEFAULT_REJECTS_PATH})",
    )
    parser.add_argument(
        "--map",
        default=str(DEFAULT_MAP_PATH),
        help=f"Where to write the GeoJSON map file (default: {DEFAULT_MAP_PATH})",
    )
    parser.add_argument(
        "--summary",
        default=str(DEFAULT_SUMMARY_PATH),
        help=f"Where to write the text summary (default: {DEFAULT_SUMMARY_PATH})",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Abort the whole run if any row is rejected, and store nothing",
    )
    return parser


def _ensure_sqlite_parent(database_url: str) -> None:
    prefix = "sqlite:///"
    if database_url.startswith(prefix) and ":memory:" not in database_url:
        db_path = Path(database_url.removeprefix(prefix))
        if db_path.parent and str(db_path.parent) not in {".", ""}:
            db_path.parent.mkdir(parents=True, exist_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    csv_path = Path(args.csv_path)
    if not csv_path.is_file():
        print(f"File not found: {csv_path}", file=sys.stderr)
        return 1

    load_dotenv()
    settings = get_settings()
    _ensure_sqlite_parent(settings.database_url)
    init_db()
    session = get_session_factory()()
    try:
        result = ingest_csv(
            csv_path,
            session,
            rejects_path=args.rejects,
            map_path=args.map,
            summary_path=args.summary,
            log_path=settings.ingest_log_path,
            strict=args.strict,
        )
    except MissingColumnError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except StrictIngestError as exc:
        print(str(exc), file=sys.stderr)
        print(f"Reason: {exc.reason}", file=sys.stderr)
        return 1
    finally:
        session.close()

    print(result.terminal_summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
