from __future__ import annotations

from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, ReportBlock, ReportPage
from app.services.admin_ops import clone_page, create_page_from_template, load_page_templates
from app.services.run_service import (
    block_latest_run,
    get_latest_snapshot_for_page,
    get_snapshots_for_page,
    page_latest_run,
    run_page_and_create_snapshot,
)

router = APIRouter(prefix="/admin/pages", tags=["admin-pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def list_pages(request: Request, db: Session = Depends(get_db)):
    pages = db.scalars(select(ReportPage).order_by(ReportPage.sort_order.asc(), ReportPage.id.asc())).all()
    categories = db.scalars(select(Category).order_by(Category.sort_order.asc(), Category.id.asc())).all()
    block_counts = dict(db.execute(select(ReportBlock.page_id, func.count(ReportBlock.id)).group_by(ReportBlock.page_id)).all())
    return templates.TemplateResponse("admin/pages.html", {"request": request, "pages": pages, "categories": categories, "block_counts": block_counts})


@router.get("/new", response_class=HTMLResponse)
def new_page_form(request: Request, db: Session = Depends(get_db)):
    categories = db.scalars(select(Category).order_by(Category.sort_order.asc())).all()
    return templates.TemplateResponse("admin/pages/new_from_template.html", {"request": request, "categories": categories, "templates": load_page_templates()})


@router.post("/create")
def create_page(
    category_id: int = Form(...),
    title: str = Form(""),
    slug: str = Form(""),
    description: str = Form(""),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    schedule_enabled: bool = Form(False),
    schedule_cron: str = Form("0 7 * * *"),
    template_key: str = Form(""),
    db: Session = Depends(get_db),
):
    if template_key:
        page = create_page_from_template(db, category_id, title, slug, template_key)
        return RedirectResponse(f"/admin/pages/{page.id}", status_code=303)

    if not slug:
        slug = (title or "page").strip().lower().replace(" ", "-")
    base_slug = slug
    idx = 1
    while db.scalars(select(ReportPage).where(ReportPage.slug == slug)).first():
        idx += 1
        slug = f"{base_slug}-{idx}"
    db.add(
        ReportPage(
            category_id=category_id,
            title=title,
            slug=slug,
            description=description,
            sort_order=sort_order,
            is_active=is_active,
            schedule_enabled=schedule_enabled,
            schedule_cron=schedule_cron,
        )
    )
    db.commit()
    return RedirectResponse("/admin/pages", status_code=303)


@router.post("/{page_id}/clone")
def clone_page_endpoint(page_id: int, db: Session = Depends(get_db)):
    p = clone_page(db, page_id)
    return RedirectResponse(f"/admin/pages/{p.id}", status_code=303)


@router.post("/{page_id}/update")
def update_page(
    page_id: int,
    category_id: int = Form(...),
    title: str = Form(""),
    slug: str = Form(""),
    description: str = Form(""),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    schedule_enabled: bool = Form(False),
    schedule_cron: str = Form("0 7 * * *"),
    db: Session = Depends(get_db),
):
    p = db.get(ReportPage, page_id)
    if not p:
        raise HTTPException(status_code=404)
    p.category_id = category_id
    p.title = title
    p.slug = slug
    p.description = description
    p.sort_order = sort_order
    p.is_active = is_active
    p.schedule_enabled = schedule_enabled
    p.schedule_cron = schedule_cron
    db.commit()
    return RedirectResponse("/admin/pages", status_code=303)


@router.post("/{page_id}/delete")
def delete_page(page_id: int, db: Session = Depends(get_db)):
    p = db.get(ReportPage, page_id)
    if p:
        db.delete(p)
        db.commit()
    return RedirectResponse("/admin/pages", status_code=303)


@router.get("/{page_id}", response_class=HTMLResponse)
def page_detail(page_id: int, request: Request, msg: str | None = Query(default=None), db: Session = Depends(get_db)):
    page = db.get(ReportPage, page_id)
    if not page:
        raise HTTPException(status_code=404)
    blocks = db.scalars(select(ReportBlock).where(ReportBlock.page_id == page_id).order_by(ReportBlock.sort_order.asc(), ReportBlock.id.asc())).all()
    latest_map = {b.id: block_latest_run(db, b.id) for b in blocks}
    snapshots = get_snapshots_for_page(db, page_id, 10)
    return templates.TemplateResponse(
        "admin/page_detail.html",
        {
            "request": request,
            "page": page,
            "blocks": blocks,
            "latest_map": latest_map,
            "page_latest": page_latest_run(db, page_id),
            "latest_snapshot": get_latest_snapshot_for_page(db, page_id),
            "snapshots": snapshots,
            "message": msg,
        },
    )


@router.post("/{page_id}/run")
def run_page_endpoint(page_id: int, common_params_json: str = Form("{}"), db: Session = Depends(get_db)):
    try:
        common_params = __import__("json").loads(common_params_json or "{}")
        if not isinstance(common_params, dict):
            common_params = {}
    except Exception:
        common_params = {}
    snap = run_page_and_create_snapshot(db, page_id, run_type="manual", trigger_source="admin", run_params=common_params)
    msg = quote_plus(f"스냅샷 생성 완료: #{snap.id} / {snap.status}")
    return RedirectResponse(f"/admin/pages/{page_id}?msg={msg}", status_code=303)
