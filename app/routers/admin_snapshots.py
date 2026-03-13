from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PageSnapshot, ReportPage
from app.services.run_service import compare_snapshot_with_previous, run_page_and_create_snapshot, summarize_snapshot_status

router = APIRouter(prefix="/admin/snapshots", tags=["admin-snapshots"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def list_snapshots(request: Request, db: Session = Depends(get_db)):
    snaps = db.scalars(select(PageSnapshot).order_by(PageSnapshot.started_at.desc()).limit(100)).all()
    return templates.TemplateResponse("admin/snapshots/list.html", {"request": request, "snapshots": snaps})


@router.get("/page/{page_id}", response_class=HTMLResponse)
def snapshots_for_page(page_id: int, request: Request, db: Session = Depends(get_db)):
    page = db.get(ReportPage, page_id)
    if not page:
        raise HTTPException(status_code=404)
    snaps = db.scalars(
        select(PageSnapshot).where(PageSnapshot.page_id == page_id).order_by(PageSnapshot.started_at.desc()).limit(50)
    ).all()
    return templates.TemplateResponse("admin/snapshots/list.html", {"request": request, "snapshots": snaps, "page": page})


@router.get("/{snapshot_id}", response_class=HTMLResponse)
def snapshot_detail(snapshot_id: int, request: Request, db: Session = Depends(get_db)):
    snap = db.get(PageSnapshot, snapshot_id)
    if not snap:
        raise HTTPException(status_code=404)
    compare_rows = compare_snapshot_with_previous(db, snapshot_id)
    summary = summarize_snapshot_status(snap)
    return templates.TemplateResponse(
        "admin/snapshots/detail.html",
        {"request": request, "snapshot": snap, "compare_rows": compare_rows, "summary": summary},
    )


@router.post("/{snapshot_id}/rerun")
def rerun_snapshot_page(snapshot_id: int, db: Session = Depends(get_db)):
    snap = db.get(PageSnapshot, snapshot_id)
    if not snap:
        raise HTTPException(status_code=404)
    new_snap = run_page_and_create_snapshot(db, snap.page_id, run_type="manual", trigger_source="admin")
    return RedirectResponse(f"/admin/snapshots/{new_snap.id}", status_code=303)


@router.post("/{snapshot_id}/delete")
def delete_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    snap = db.get(PageSnapshot, snapshot_id)
    if snap:
        db.delete(snap)
        db.commit()
    return RedirectResponse("/admin/snapshots", status_code=303)
