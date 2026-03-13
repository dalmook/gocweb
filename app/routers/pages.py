from __future__ import annotations

from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Page
from app.services.renderers import markdown_to_html, run_content_html
from app.services.reporting import get_page_dashboard_data, run_page

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
def page_detail(
    page_id: int,
    request: Request,
    msg: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        data = get_page_dashboard_data(db, page_id)
    except ValueError:
        raise HTTPException(status_code=404)

    page = data["page"]
    categories = db.scalars(select(Category).order_by(Category.sort_order.asc())).all()

    for card in data["cards"]:
        block = card["block"]
        preferred = card["preferred_run"]
        latest = card["latest_any"]
        if block.block_type == "markdown":
            card["display_html"] = markdown_to_html(block.source_code_text)
        else:
            card["display_html"] = run_content_html(preferred)
        if latest:
            card["status"] = latest.status
            card["last_run_at"] = latest.finished_at
            card["duration_ms"] = latest.duration_ms
        else:
            card["status"] = "never-run"
            card["last_run_at"] = None
            card["duration_ms"] = None

    return templates.TemplateResponse(
        "pages/detail.html",
        {
            "request": request,
            "page": page,
            "categories": categories,
            "cards": data["cards"],
            "summary": data["summary"],
            "message": msg,
        },
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
    return RedirectResponse(f"/pages/{page_id}?msg={quote_plus('페이지 정보를 저장했습니다')}", status_code=303)


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
def run_page_all(page_id: int, db: Session = Depends(get_db)):
    try:
        result = run_page(db, page_id, run_type="manual")
    except ValueError:
        raise HTTPException(status_code=404)
    msg = f"페이지 실행 완료: 총 {result['total']}개, 성공 {result['success']}개, 실패 {result['failed']}개"
    return RedirectResponse(f"/pages/{page_id}?msg={quote_plus(msg)}", status_code=303)


@router.get("/{page_id}/result", response_class=HTMLResponse)
def page_result(page_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        data = get_page_dashboard_data(db, page_id)
    except ValueError:
        raise HTTPException(status_code=404)

    rendered_blocks = []
    for card in data["cards"]:
        block = card["block"]
        preferred = card["preferred_run"]
        latest_any = card["latest_any"]
        if block.block_type == "markdown":
            html = markdown_to_html(block.source_code_text)
        else:
            html = run_content_html(preferred)
        rendered_blocks.append({"block": block, "html": html, "latest_any": latest_any})

    return templates.TemplateResponse(
        "pages/result.html",
        {"request": request, "page": data["page"], "rendered_blocks": rendered_blocks},
    )
