from __future__ import annotations

from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Block
from app.services.reporting import run_block
from app.services.scheduler import register_jobs

router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.post("/create")
def block_create(
    page_id: int = Form(...),
    title: str = Form(...),
    block_type: str = Form(...),
    source_code_text: str = Form(""),
    config_json: str = Form("{}"),
    schedule_enabled: bool = Form(False),
    schedule_cron: str = Form("0 7 * * *"),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    block = Block(
        page_id=page_id,
        title=title,
        block_type=block_type,
        source_code_text=source_code_text,
        config_json=config_json,
        schedule_enabled=schedule_enabled,
        schedule_cron=schedule_cron,
        sort_order=sort_order,
        is_active=is_active,
    )
    db.add(block)
    db.commit()
    register_jobs()
    return RedirectResponse(f"/pages/{page_id}?msg={quote_plus('블록을 추가했습니다')}", status_code=303)


@router.post("/{block_id}/update")
def block_update(
    block_id: int,
    title: str = Form(...),
    block_type: str = Form(...),
    source_code_text: str = Form(""),
    config_json: str = Form("{}"),
    schedule_enabled: bool = Form(False),
    schedule_cron: str = Form("0 7 * * *"),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    block = db.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404)
    block.title = title
    block.block_type = block_type
    block.source_code_text = source_code_text
    block.config_json = config_json
    block.schedule_enabled = schedule_enabled
    block.schedule_cron = schedule_cron
    block.sort_order = sort_order
    block.is_active = is_active
    db.commit()
    register_jobs()
    return RedirectResponse(f"/pages/{block.page_id}?msg={quote_plus('블록을 수정했습니다')}", status_code=303)


@router.post("/{block_id}/delete")
def block_delete(block_id: int, db: Session = Depends(get_db)):
    block = db.get(Block, block_id)
    redirect_to = "/"
    if block:
        redirect_to = f"/pages/{block.page_id}?msg={quote_plus('블록을 삭제했습니다')}"
        db.delete(block)
        db.commit()
        register_jobs()
    return RedirectResponse(redirect_to, status_code=303)


@router.post("/{block_id}/run")
def block_run(block_id: int, db: Session = Depends(get_db)):
    block = db.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=404)
    run = run_block(db, block_id, run_type="manual")
    msg = quote_plus(f"블록 실행 완료: {run.status} / {run.summary}")
    return RedirectResponse(f"/pages/{block.page_id}?msg={msg}", status_code=303)
