"""Bulk CSV upload. Administrators only (PDF 3.10, 3.11.2)."""

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from utility_assets.api.deps import get_current_admin
from utility_assets.api.errors import ValidationFailed
from utility_assets.db import get_db
from utility_assets.ingestion.pipeline import MissingColumnError, StrictIngestError, ingest_csv
from utility_assets.models import User

router = APIRouter(tags=["ingest"])


@router.post("/ingest")
def bulk_ingest(
    file: UploadFile = File(...),
    strict: bool = False,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    with TemporaryDirectory() as tmp:
        upload_path = Path(tmp) / (file.filename or "upload.csv")
        upload_path.write_bytes(file.file.read())
        try:
            result = ingest_csv(
                upload_path,
                db,
                rejects_path=Path(tmp) / "rejects.csv",
                map_path=Path(tmp) / "assets.geojson",
                summary_path=Path(tmp) / "summary.txt",
                log_path=None,
                strict=strict,
            )
        except MissingColumnError as exc:
            raise ValidationFailed(
                [{"field": "file", "message": str(exc)}]
            ) from exc
        except StrictIngestError as exc:
            raise ValidationFailed(
                [{"field": "file", "message": str(exc)}]
            ) from exc
    return {
        "rows_read": result.rows_read,
        "rows_accepted": result.rows_accepted,
        "rows_rejected": result.rows_rejected,
    }
