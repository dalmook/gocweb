from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PageSnapshot
from app.services.run_service import count_entities, latest_failed_runs, latest_runs

router = APIRouter(prefix="/admin", tags=["admin-home"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "admin/home.html",
        {
            "request": request,
            "counts": count_entities(db),
            "recent_runs": latest_runs(db, 10),
            "failed_runs": latest_failed_runs(db, 5),
            "recent_snapshots": db.scalars(select(PageSnapshot).order_by(PageSnapshot.started_at.desc()).limit(10)).all(),
        },
    )
