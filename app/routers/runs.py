from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Block, Page, RunHistory
from app.services.reporting import run_block

router = APIRouter(prefix="/runs", tags=["runs"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def run_list(
    request: Request,
    page_id: int | None = Query(default=None),
    block_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100),
    db: Session = Depends(get_db),
):
    q = select(RunHistory).order_by(RunHistory.started_at.desc())
    if page_id:
        q = q.where(RunHistory.page_id == page_id)
    if block_id:
        q = q.where(RunHistory.block_id == block_id)
    if status in {"success", "failed"}:
        q = q.where(RunHistory.status == status)

    runs = db.scalars(q.limit(limit)).all()
    pages = db.scalars(select(Page).order_by(Page.title.asc())).all()
    blocks = db.scalars(select(Block).order_by(Block.title.asc())).all()

    return templates.TemplateResponse(
        "runs/list.html",
        {
            "request": request,
            "runs": runs,
            "pages": pages,
            "blocks": blocks,
            "selected_page_id": page_id,
            "selected_block_id": block_id,
            "selected_status": status or "",
            "limit": limit,
        },
    )


@router.get("/{run_id}", response_class=HTMLResponse)
def run_detail(run_id: int, request: Request, db: Session = Depends(get_db)):
    run = db.get(RunHistory, run_id)
    if not run:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("runs/detail.html", {"request": request, "run": run})


@router.post("/{run_id}/rerun")
def rerun(run_id: int, db: Session = Depends(get_db)):
    prev = db.get(RunHistory, run_id)
    if not prev:
        raise HTTPException(status_code=404)
    run_block(db, prev.block_id, run_type="manual")
    return RedirectResponse(f"/pages/{prev.page_id}?msg=다시+실행했습니다", status_code=303)
