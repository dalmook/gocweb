from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/view", tags=["view-placeholder"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def view_home(request: Request):
    return templates.TemplateResponse("view/placeholder.html", {"request": request, "path": "/view"})


@router.get("/{category_slug}", response_class=HTMLResponse)
def view_category(category_slug: str, request: Request):
    return templates.TemplateResponse("view/placeholder.html", {"request": request, "path": f"/view/{category_slug}"})


@router.get("/{category_slug}/{page_slug}", response_class=HTMLResponse)
def view_page(category_slug: str, page_slug: str, request: Request):
    return templates.TemplateResponse(
        "view/placeholder.html",
        {"request": request, "path": f"/view/{category_slug}/{page_slug}"},
    )
