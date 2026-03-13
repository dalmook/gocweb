from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ReportPage
from app.services.view_service import (
    build_view_page_context,
    get_active_categories_for_view,
    get_active_pages_for_category,
    get_latest_page_status,
    get_page_for_view,
)

router = APIRouter(prefix="/view", tags=["view-portal"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def view_home(request: Request, db: Session = Depends(get_db)):
    categories, counts = get_active_categories_for_view(db)
    recent_pages = db.scalars(select(ReportPage).where(ReportPage.is_active.is_(True)).order_by(ReportPage.updated_at.desc()).limit(8)).all()
    today = datetime.now(timezone.utc).date()
    freshness = {}
    for p in recent_pages:
        _, latest = get_latest_page_status(db, p.id)
        freshness[p.id] = {"latest": latest, "is_today": bool(latest and latest.date() == today)}
    return templates.TemplateResponse(
        "view/home.html",
        {"request": request, "categories": categories, "page_counts": counts, "recent_pages": recent_pages, "freshness": freshness},
    )


@router.get("/{category_slug}", response_class=HTMLResponse)
def view_category(category_slug: str, request: Request, db: Session = Depends(get_db)):
    category, pages = get_active_pages_for_category(db, category_slug)
    if not category:
        raise HTTPException(status_code=404)

    page_meta = {}
    for p in pages:
        status, latest = get_latest_page_status(db, p.id)
        page_meta[p.id] = {"status": status, "latest": latest, "block_count": len([b for b in p.blocks if b.is_active])}

    return templates.TemplateResponse("view/category.html", {"request": request, "category": category, "pages": pages, "page_meta": page_meta})


@router.get("/{category_slug}/{page_slug}", response_class=HTMLResponse)
def view_page(
    category_slug: str,
    page_slug: str,
    request: Request,
    snapshot_id: int | None = Query(default=None),
    snapshot_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    page = get_page_for_view(db, category_slug, page_slug)
    if not page:
        raise HTTPException(status_code=404)

    context = build_view_page_context(
        db,
        page.id,
        selected_snapshot_id=snapshot_id,
        snapshot_date=snapshot_date,
        history_limit=14,
    )
    return templates.TemplateResponse("view/page_detail.html", {"request": request, **context})


@router.get("/{category_slug}/{page_slug}/print", response_class=HTMLResponse)
def view_page_print(
    category_slug: str,
    page_slug: str,
    request: Request,
    snapshot_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    page = get_page_for_view(db, category_slug, page_slug)
    if not page:
        raise HTTPException(status_code=404)
    context = build_view_page_context(db, page.id, selected_snapshot_id=snapshot_id, history_limit=14)
    return templates.TemplateResponse("view/print.html", {"request": request, **context})
