from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Block, Category, Page, RunHistory

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    categories = db.scalars(select(Category).order_by(Category.sort_order.asc(), Category.id.asc())).all()
    page_counts = dict(db.execute(select(Page.category_id, func.count(Page.id)).group_by(Page.category_id)).all())

    total_categories = db.scalar(select(func.count(Category.id))) or 0
    total_pages = db.scalar(select(func.count(Page.id))) or 0
    total_blocks = db.scalar(select(func.count(Block.id))) or 0

    recent_failed = db.scalars(
        select(RunHistory).where(RunHistory.status == "failed").order_by(RunHistory.started_at.desc()).limit(5)
    ).all()
    recent_updated_pages = db.scalars(select(Page).order_by(Page.updated_at.desc()).limit(8)).all()

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "categories": categories,
            "page_counts": page_counts,
            "total_categories": total_categories,
            "total_pages": total_pages,
            "total_blocks": total_blocks,
            "recent_failed": recent_failed,
            "recent_updated_pages": recent_updated_pages,
        },
    )
