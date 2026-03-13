from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RunHistory

router = APIRouter(prefix="/admin/runs", tags=["admin-runs"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def list_runs(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=100),
    db: Session = Depends(get_db),
):
    q = select(RunHistory).order_by(RunHistory.started_at.desc())
    if status in {"success", "failed"}:
        q = q.where(RunHistory.status == status)
    runs = db.scalars(q.limit(limit)).all()
    return templates.TemplateResponse("admin/runs.html", {"request": request, "runs": runs, "status": status or "", "limit": limit})


@router.get("/{run_id}", response_class=HTMLResponse)
def run_detail(run_id: int, request: Request, db: Session = Depends(get_db)):
    run = db.get(RunHistory, run_id)
    return templates.TemplateResponse("admin/run_detail.html", {"request": request, "run": run})
