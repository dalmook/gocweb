from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.admin_ops import cleanup_old_snapshots, cleanup_temp_files, get_recent_failures

router = APIRouter(prefix="/admin/maintenance", tags=["admin-maintenance"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def maintenance_home(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "admin/maintenance.html",
        {"request": request, "result": None, "failures": get_recent_failures(db, 20)},
    )


@router.post("/cleanup", response_class=HTMLResponse)
def do_cleanup(
    request: Request,
    keep_per_page: int = Form(20),
    temp_days: int = Form(30),
    db: Session = Depends(get_db),
):
    r1 = cleanup_old_snapshots(db, keep_per_page=keep_per_page)
    r2 = cleanup_temp_files(days=temp_days)
    result = {**r1, **r2, "keep_per_page": keep_per_page, "temp_days": temp_days}
    return templates.TemplateResponse(
        "admin/maintenance.html",
        {"request": request, "result": result, "failures": get_recent_failures(db, 20)},
    )
