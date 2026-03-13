from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attachment, SnapshotAttachment

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("/{attachment_id}/download")
def download_attachment(attachment_id: int, db: Session = Depends(get_db)):
    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        attachment = db.get(SnapshotAttachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404)
    p = Path(attachment.stored_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File missing")
    return FileResponse(path=str(p), filename=attachment.file_name, media_type=attachment.mime_type)
