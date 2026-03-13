from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attachment, SnapshotAttachment

router = APIRouter(prefix="/attachments", tags=["attachments"])


def _send_file(file_name: str, stored_path: str, mime_type: str):
    p = Path(stored_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File missing")
    return FileResponse(path=str(p), filename=file_name, media_type=mime_type)


@router.get("/{attachment_id}/download")
def download_attachment(attachment_id: int, db: Session = Depends(get_db)):
    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404)
    return _send_file(attachment.file_name, attachment.stored_path, attachment.mime_type)


@router.get("/snapshot/{attachment_id}/download")
def download_snapshot_attachment(attachment_id: int, db: Session = Depends(get_db)):
    attachment = db.get(SnapshotAttachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404)
    return _send_file(attachment.file_name, attachment.stored_path, attachment.mime_type)
