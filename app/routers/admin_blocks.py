from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ReportBlock, ReportPage
from app.services.run_service import block_latest_run, run_block
from app.services.scheduler import register_jobs

router = APIRouter(prefix="/admin/blocks", tags=["admin-blocks"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def list_blocks(request: Request, db: Session = Depends(get_db)):
    blocks = db.scalars(select(ReportBlock).order_by(ReportBlock.updated_at.desc())).all()
    pages = db.scalars(select(ReportPage).order_by(ReportPage.title.asc())).all()
    latest_map = {b.id: block_latest_run(db, b.id) for b in blocks}
    return templates.TemplateResponse(
        "admin/blocks.html",
        {"request": request, "blocks": blocks, "pages": pages, "latest_map": latest_map},
    )


@router.get("/{block_id}/edit", response_class=HTMLResponse)
def edit_block(block_id: int, request: Request, db: Session = Depends(get_db)):
    block = db.get(ReportBlock, block_id)
    if not block:
        raise HTTPException(status_code=404)
    pages = db.scalars(select(ReportPage).order_by(ReportPage.title.asc())).all()
    return templates.TemplateResponse("admin/block_edit.html", {"request": request, "block": block, "pages": pages})


@router.post("/create")
def create_block(
    page_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    block_type: str = Form(...),
    source_code_text: str = Form(""),
    config_json: str = Form("{}"),
    schedule_enabled: bool = Form(False),
    schedule_cron: str = Form("0 7 * * *"),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    db.add(
        ReportBlock(
            page_id=page_id,
            title=title,
            description=description,
            block_type=block_type,
            source_code_text=source_code_text,
            config_json=config_json,
            schedule_enabled=schedule_enabled,
            schedule_cron=schedule_cron,
            sort_order=sort_order,
            is_active=is_active,
        )
    )
    db.commit()
    register_jobs()
    return RedirectResponse(f"/admin/pages/{page_id}", status_code=303)


@router.post("/{block_id}/update")
def update_block(
    block_id: int,
    page_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    block_type: str = Form(...),
    source_code_text: str = Form(""),
    config_json: str = Form("{}"),
    schedule_enabled: bool = Form(False),
    schedule_cron: str = Form("0 7 * * *"),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    b = db.get(ReportBlock, block_id)
    if not b:
        raise HTTPException(status_code=404)
    b.page_id = page_id
    b.title = title
    b.description = description
    b.block_type = block_type
    b.source_code_text = source_code_text
    b.config_json = config_json
    b.schedule_enabled = schedule_enabled
    b.schedule_cron = schedule_cron
    b.sort_order = sort_order
    b.is_active = is_active
    db.commit()
    register_jobs()
    return RedirectResponse(f"/admin/blocks/{block_id}/edit", status_code=303)


@router.post("/{block_id}/run")
def run_block_endpoint(block_id: int, db: Session = Depends(get_db)):
    block = db.get(ReportBlock, block_id)
    if not block:
        raise HTTPException(status_code=404)
    if block.block_type != "markdown":
        run_block(db, block_id, run_type="manual")
    return RedirectResponse(f"/admin/pages/{block.page_id}", status_code=303)


@router.post("/{block_id}/delete")
def delete_block(block_id: int, db: Session = Depends(get_db)):
    b = db.get(ReportBlock, block_id)
    if b:
        page_id = b.page_id
        db.delete(b)
        db.commit()
        register_jobs()
        return RedirectResponse(f"/admin/pages/{page_id}", status_code=303)
    return RedirectResponse("/admin/blocks", status_code=303)
