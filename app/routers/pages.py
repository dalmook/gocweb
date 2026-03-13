from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Block, Category, Page, RunHistory
from app.services.executor import execute_page_blocks
from app.services.renderers import markdown_to_html, text_to_pre

router = APIRouter(prefix="/pages", tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/create")
def page_create(
    category_id: int = Form(...),
    title: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    page = Page(
        category_id=category_id,
        title=title,
        slug=slug,
        description=description,
        sort_order=sort_order,
        is_active=is_active,
    )
    db.add(page)
    db.commit()
    return RedirectResponse(f"/categories/{category_id}", status_code=303)


@router.get("/{page_id}", response_class=HTMLResponse)
def page_detail(page_id: int, request: Request, db: Session = Depends(get_db)):
    page = db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404)
    categories = db.scalars(select(Category).order_by(Category.sort_order.asc())).all()
    blocks = db.scalars(select(Block).where(Block.page_id == page_id).order_by(Block.sort_order.asc(), Block.id.asc())).all()
    latest_map = {}
    for block in blocks:
        latest_map[block.id] = db.scalars(
            select(RunHistory).where(RunHistory.block_id == block.id).order_by(RunHistory.started_at.desc()).limit(1)
        ).first()
    return templates.TemplateResponse(
        "pages/detail.html",
        {"request": request, "page": page, "categories": categories, "blocks": blocks, "latest_map": latest_map},
    )


@router.post("/{page_id}/update")
def page_update(
    page_id: int,
    category_id: int = Form(...),
    title: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    page = db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404)
    page.category_id = category_id
    page.title = title
    page.slug = slug
    page.description = description
    page.sort_order = sort_order
    page.is_active = is_active
    db.commit()
    return RedirectResponse(f"/pages/{page_id}", status_code=303)


@router.post("/{page_id}/delete")
def page_delete(page_id: int, db: Session = Depends(get_db)):
    page = db.get(Page, page_id)
    redirect_to = "/"
    if page:
        redirect_to = f"/categories/{page.category_id}"
        db.delete(page)
        db.commit()
    return RedirectResponse(redirect_to, status_code=303)


@router.post("/{page_id}/run")
def run_page(page_id: int, db: Session = Depends(get_db)):
    execute_page_blocks(db, page_id, run_type="manual")
    return RedirectResponse(f"/pages/{page_id}", status_code=303)


@router.get("/{page_id}/result", response_class=HTMLResponse)
def page_result(page_id: int, request: Request, db: Session = Depends(get_db)):
    page = db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404)
    blocks = db.scalars(select(Block).where(Block.page_id == page_id).order_by(Block.sort_order.asc(), Block.id.asc())).all()
    rendered_blocks = []
    for block in blocks:
        latest_success = db.scalars(
            select(RunHistory)
            .where(RunHistory.block_id == block.id, RunHistory.status == "success")
            .order_by(RunHistory.started_at.desc())
            .limit(1)
        ).first()
        latest_any = db.scalars(
            select(RunHistory).where(RunHistory.block_id == block.id).order_by(RunHistory.started_at.desc()).limit(1)
        ).first()
        if block.block_type == "markdown":
            html = markdown_to_html(block.source_code_text)
        elif latest_success and latest_success.content_html:
            html = latest_success.content_html
        elif latest_success and latest_success.content_text:
            html = text_to_pre(latest_success.content_text)
        else:
            html = "<p>아직 실행 결과 없음</p>"
        rendered_blocks.append({"block": block, "html": html, "latest_any": latest_any})
    return templates.TemplateResponse("pages/result.html", {"request": request, "page": page, "rendered_blocks": rendered_blocks})
