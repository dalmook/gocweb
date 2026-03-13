from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Page

router = APIRouter(prefix="/categories", tags=["categories"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def category_list(request: Request, db: Session = Depends(get_db)):
    categories = db.scalars(select(Category).order_by(Category.sort_order.asc(), Category.id.asc())).all()
    return templates.TemplateResponse("categories/list.html", {"request": request, "categories": categories})


@router.post("/create")
def category_create(
    name: str = Form(...),
    slug: str = Form(...),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    db.add(Category(name=name, slug=slug, sort_order=sort_order, is_active=is_active))
    db.commit()
    return RedirectResponse("/categories", status_code=303)


@router.get("/{category_id}", response_class=HTMLResponse)
def category_detail(category_id: int, request: Request, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404)
    pages = db.scalars(select(Page).where(Page.category_id == category_id).order_by(Page.sort_order.asc())).all()
    return templates.TemplateResponse("categories/detail.html", {"request": request, "category": category, "pages": pages})


@router.post("/{category_id}/update")
def category_update(
    category_id: int,
    name: str = Form(...),
    slug: str = Form(...),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404)
    category.name = name
    category.slug = slug
    category.sort_order = sort_order
    category.is_active = is_active
    db.commit()
    return RedirectResponse(f"/categories/{category_id}", status_code=303)


@router.post("/{category_id}/delete")
def category_delete(category_id: int, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category:
        db.delete(category)
        db.commit()
    return RedirectResponse("/categories", status_code=303)
