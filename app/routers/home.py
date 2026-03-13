from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Page, RunHistory

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    cats = db.scalars(select(Category).order_by(Category.sort_order.asc(), Category.id.asc())).all()
    page_counts = dict(db.execute(select(Page.category_id, func.count(Page.id)).group_by(Page.category_id)).all())
    latest_runs = db.scalars(select(RunHistory).order_by(RunHistory.started_at.desc()).limit(10)).all()
    run_summary = defaultdict(lambda: {"success": 0, "failed": 0})
    for run in latest_runs:
        run_summary[run.status]["count"] = run_summary[run.status].get("count", 0) + 1
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "categories": cats,
            "page_counts": page_counts,
            "latest_runs": latest_runs,
        },
    )
