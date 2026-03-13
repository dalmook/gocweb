from __future__ import annotations

import json
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, PreviewRun, ReportBlock, ReportPage
from app.services.admin_ops import clone_block, safe_delete_or_archive_block, set_archive_state, validate_block_payload
from app.services.run_service import block_latest_run, run_block
from app.services.scheduler import register_jobs

router = APIRouter(prefix="/admin/blocks", tags=["admin-blocks"])
templates = Jinja2Templates(directory="app/templates")


def _to_dict(txt: str, default: dict | list):
    try:
        obj = json.loads(txt or json.dumps(default))
        return obj if isinstance(obj, type(default)) else default
    except Exception:
        return default


@router.get("", response_class=HTMLResponse)
def list_blocks(
    request: Request,
    q: str = Query(""),
    block_type: str = Query("all"),
    page_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    active: str = Query("all"),
    show_archived: bool = Query(False),
    msg: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    filters = []
    if not show_archived:
        filters.append(ReportBlock.is_archived.is_(False))
    if q:
        keyword = f"%{q}%"
        filters.append(or_(ReportBlock.title.like(keyword), ReportBlock.description.like(keyword)))
    if block_type != "all":
        filters.append(ReportBlock.block_type == block_type)
    if page_id:
        filters.append(ReportBlock.page_id == page_id)
    if active == "active":
        filters.append(ReportBlock.is_active.is_(True))
    elif active == "inactive":
        filters.append(ReportBlock.is_active.is_(False))

    stmt = select(ReportBlock).join(ReportPage, ReportPage.id == ReportBlock.page_id)
    if filters:
        stmt = stmt.where(and_(*filters))
    blocks = db.scalars(stmt.order_by(ReportBlock.updated_at.desc())).all()
    if category_id:
        blocks = [b for b in blocks if b.page.category_id == category_id]
    latest_map = {b.id: block_latest_run(db, b.id) for b in blocks}
    pages = db.scalars(select(ReportPage).where(ReportPage.is_archived.is_(False)).order_by(ReportPage.title.asc())).all()
    categories = db.scalars(select(Category).where(Category.is_archived.is_(False)).order_by(Category.sort_order.asc())).all()
    return templates.TemplateResponse(
        "admin/blocks.html",
        {
            "request": request,
            "blocks": blocks,
            "latest_map": latest_map,
            "pages": pages,
            "categories": categories,
            "filters": {"q": q, "block_type": block_type, "page_id": page_id, "category_id": category_id, "active": active, "show_archived": show_archived},
            "message": msg,
        },
    )


@router.get("/{block_id}/edit", response_class=HTMLResponse)
def edit_block(block_id: int, request: Request, msg: str | None = Query(default=None), db: Session = Depends(get_db)):
    block = db.get(ReportBlock, block_id)
    if not block:
        raise HTTPException(status_code=404)
    pages = db.scalars(select(ReportPage).where(ReportPage.is_archived.is_(False)).order_by(ReportPage.title.asc())).all()
    previews = db.scalars(select(PreviewRun).where(PreviewRun.block_id == block_id).order_by(PreviewRun.created_at.desc()).limit(5)).all()
    return templates.TemplateResponse("admin/blocks/form.html", {"request": request, "block": block, "pages": pages, "errors": ([msg] if msg else []), "previews": previews})


@router.post("/create")
def create_block(
    page_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    block_type: str = Form(...),
    source_code_text: str = Form(""),
    config_json: str = Form("{}"),
    params_schema_json: str = Form("[]"),
    default_params_json: str = Form("{}"),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    # 스케줄은 리포트(page) 기준으로만 운영. 블록 개별 스케줄은 비활성 고정.
    errors = validate_block_payload(config_json, params_schema_json, default_params_json, None)
    if errors:
        return RedirectResponse(f"/admin/pages/{page_id}?msg={quote_plus(errors[0])}", status_code=303)

    b = ReportBlock(
        page_id=page_id,
        title=title,
        description=description,
        block_type=block_type,
        source_code_text=source_code_text,
        config_json=config_json,
        params_schema_json=params_schema_json,
        default_params_json=default_params_json,
        schedule_enabled=False,
        schedule_cron="",
        sort_order=sort_order,
        is_active=is_active,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    register_jobs()
    # 블록 추가 후 바로 페이지로 복귀 (추가 설정 화면 이동 제거)
    return RedirectResponse(f"/admin/pages/{b.page_id}?msg={quote_plus('블록이 추가되었습니다.')}", status_code=303)


@router.post("/{block_id}/update")
def update_block(
    block_id: int,
    page_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    block_type: str = Form(...),
    source_code_text: str = Form(""),
    config_json: str = Form("{}"),
    params_schema_json: str = Form("[]"),
    default_params_json: str = Form("{}"),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    b = db.get(ReportBlock, block_id)
    if not b:
        raise HTTPException(status_code=404)
    errors = validate_block_payload(config_json, params_schema_json, default_params_json, None)
    if errors:
        return RedirectResponse(f"/admin/blocks/{block_id}/edit?msg={quote_plus(errors[0])}", status_code=303)

    b.page_id = page_id
    b.title = title
    b.description = description
    b.block_type = block_type
    b.source_code_text = source_code_text
    b.config_json = config_json
    b.params_schema_json = params_schema_json
    b.default_params_json = default_params_json
    # 스케줄은 리포트(page) 기준으로만 운영. 블록 개별 스케줄은 비활성 고정.
    b.schedule_enabled = False
    b.schedule_cron = ""
    b.sort_order = sort_order
    b.is_active = is_active
    db.commit()
    register_jobs()
    return RedirectResponse(f"/admin/blocks/{block_id}/edit", status_code=303)


@router.post("/{block_id}/run")
def run_block_endpoint(block_id: int, run_params_json: str = Form("{}"), db: Session = Depends(get_db)):
    block = db.get(ReportBlock, block_id)
    if not block:
        raise HTTPException(status_code=404)
    params = _to_dict(run_params_json, {})
    if block.block_type in {"python", "sql"}:
        run_block(db, block_id, run_type="manual", run_params=params)
    return RedirectResponse(f"/admin/pages/{block.page_id}?msg={quote_plus('블록 실행 완료')}", status_code=303)


@router.post("/{block_id}/preview")
def preview_block(block_id: int, run_params_json: str = Form("{}"), db: Session = Depends(get_db)):
    block = db.get(ReportBlock, block_id)
    if not block:
        raise HTTPException(status_code=404)
    params = _to_dict(run_params_json, {})
    if block.block_type in {"python", "sql"}:
        run = run_block(db, block_id, run_type="manual", run_params=params)
        db.add(
            PreviewRun(
                block_id=block_id,
                status=run.status,
                summary=run.summary,
                content_html=run.content_html,
                content_text=run.content_text,
                error_text=run.error_text,
                run_params_json=json.dumps(params, ensure_ascii=False),
            )
        )
        db.commit()
    return RedirectResponse(f"/admin/blocks/{block_id}/edit", status_code=303)


@router.post("/{block_id}/clone")
def clone_block_endpoint(block_id: int, db: Session = Depends(get_db)):
    cloned = clone_block(db, block_id)
    register_jobs()
    return RedirectResponse(f"/admin/blocks/{cloned.id}/edit", status_code=303)


@router.post("/{block_id}/archive")
def archive_block(block_id: int, archive: bool = Form(True), db: Session = Depends(get_db)):
    b = db.get(ReportBlock, block_id)
    if not b:
        raise HTTPException(status_code=404)
    set_archive_state(b, archive)
    db.commit()
    return RedirectResponse(f"/admin/blocks/{block_id}/edit", status_code=303)


@router.post("/{block_id}/delete")
def delete_block(block_id: int, db: Session = Depends(get_db)):
    b = db.get(ReportBlock, block_id)
    page_id = b.page_id if b else None
    action, msg = safe_delete_or_archive_block(db, block_id)
    if page_id:
        return RedirectResponse(f"/admin/pages/{page_id}?msg={quote_plus(f'[{action}] {msg}')}", status_code=303)
    return RedirectResponse(f"/admin/blocks?msg={quote_plus(f'[{action}] {msg}')}", status_code=303)
