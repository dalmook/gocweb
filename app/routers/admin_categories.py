from __future__ import annotations

from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, ReportPage
from app.services.admin_ops import safe_delete_or_archive_category, set_archive_state

router = APIRouter(prefix="/admin/categories", tags=["admin-categories"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def list_categories(
    request: Request,
    show_archived: bool = Query(False),
    msg: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = select(Category)
    if not show_archived:
        q = q.where(Category.is_archived.is_(False))
    categories = db.scalars(q.order_by(Category.sort_order.asc(), Category.id.asc())).all()
    page_counts = dict(db.execute(select(ReportPage.category_id, func.count(ReportPage.id)).group_by(ReportPage.category_id)).all())
    return templates.TemplateResponse(
        "admin/categories.html",
        {"request": request, "categories": categories, "page_counts": page_counts, "show_archived": show_archived, "message": msg},
    )


@router.post("/create")
def create_category(
    name: str = Form(...),
    slug: str = Form(...),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    db.add(Category(name=name, slug=slug, sort_order=sort_order, is_active=is_active))
    db.commit()
    return RedirectResponse("/admin/categories", status_code=303)


@router.post("/{category_id}/update")
def update_category(
    category_id: int,
    name: str = Form(...),
    slug: str = Form(...),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    c = db.get(Category, category_id)
    if not c:
        raise HTTPException(status_code=404)
    c.name = name
    c.slug = slug
    c.sort_order = sort_order
    c.is_active = is_active
    db.commit()
    return RedirectResponse("/admin/categories", status_code=303)


@router.post("/{category_id}/archive")
def archive_category(category_id: int, archive: bool = Form(True), db: Session = Depends(get_db)):
    c = db.get(Category, category_id)
    if not c:
        raise HTTPException(status_code=404)
    set_archive_state(c, archive)
    db.commit()
    return RedirectResponse("/admin/categories", status_code=303)


@router.post("/{category_id}/delete")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    action, msg = safe_delete_or_archive_category(db, category_id)
    return RedirectResponse(f"/admin/categories?msg={quote_plus(f'[{action}] {msg}')}", status_code=303)
