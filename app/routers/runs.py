from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RunHistory

router = APIRouter(prefix="/runs", tags=["runs"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/{run_id}", response_class=HTMLResponse)
def run_detail(run_id: int, request: Request, db: Session = Depends(get_db)):
    run = db.get(RunHistory, run_id)
    if not run:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("runs/detail.html", {"request": request, "run": run})
