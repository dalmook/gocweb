from __future__ import annotations

from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, ReportBlock, ReportPage
from app.services.run_service import block_latest_run, page_latest_run, run_page

router = APIRouter(prefix="/admin/pages", tags=["admin-pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def list_pages(request: Request, db: Session = Depends(get_db)):
    pages = db.scalars(select(ReportPage).order_by(ReportPage.sort_order.asc(), ReportPage.id.asc())).all()
    categories = db.scalars(select(Category).order_by(Category.sort_order.asc())).all()
    block_counts = dict(db.execute(select(ReportBlock.page_id, func.count(ReportBlock.id)).group_by(ReportBlock.page_id)).all())
    return templates.TemplateResponse(
        "admin/pages.html",
        {"request": request, "pages": pages, "categories": categories, "block_counts": block_counts},
    )


@router.post("/create")
def create_page(
    category_id: int = Form(...),
    title: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    db.add(
        ReportPage(
            category_id=category_id,
            title=title,
            slug=slug,
            description=description,
            sort_order=sort_order,
            is_active=is_active,
        )
    )
    db.commit()
    return RedirectResponse("/admin/pages", status_code=303)


@router.post("/{page_id}/update")
def update_page(
    page_id: int,
    category_id: int = Form(...),
    title: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
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
def page_detail(page_id: int, request: Request, db: Session = Depends(get_db)):
    page = db.get(ReportPage, page_id)
    if not page:
        raise HTTPException(status_code=404)
    blocks = db.scalars(
        select(ReportBlock).where(ReportBlock.page_id == page_id).order_by(ReportBlock.sort_order.asc(), ReportBlock.id.asc())
    ).all()
    latest_map = {b.id: block_latest_run(db, b.id) for b in blocks}
    return templates.TemplateResponse(
        "admin/page_detail.html",
        {"request": request, "page": page, "blocks": blocks, "latest_map": latest_map, "page_latest": page_latest_run(db, page_id)},
    )


@router.post("/{page_id}/run")
def run_page_endpoint(page_id: int, db: Session = Depends(get_db)):
    result = run_page(db, page_id, run_type="manual")
    msg = quote_plus(f"실행완료: 총 {result['total']} / 성공 {result['success']} / 실패 {result['failed']}")
    return RedirectResponse(f"/admin/pages/{page_id}?msg={msg}", status_code=303)
