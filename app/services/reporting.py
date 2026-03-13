from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attachment, Block, Page, RunHistory
from app.services.renderers import markdown_to_html
from app.services.runner_python import run_python_block
from app.services.runner_sql import run_sql_block
from app.services.storage import ensure_run_dir, file_meta


def _safe_json(text: str) -> dict:
    try:
        return json.loads(text or "{}")
    except Exception:
        return {}


def get_latest_preferred_run(db: Session, block_id: int) -> RunHistory | None:
    latest_success = db.scalars(
        select(RunHistory)
        .where(RunHistory.block_id == block_id, RunHistory.status == "success")
        .order_by(RunHistory.started_at.desc())
        .limit(1)
    ).first()
    if latest_success:
        return latest_success
    return db.scalars(
        select(RunHistory).where(RunHistory.block_id == block_id).order_by(RunHistory.started_at.desc()).limit(1)
    ).first()


def list_block_attachments(db: Session, block_id: int) -> list[Attachment]:
    run = get_latest_preferred_run(db, block_id)
    if not run:
        return []
    return db.scalars(
        select(Attachment).where(Attachment.run_history_id == run.id).order_by(Attachment.created_at.desc(), Attachment.id.desc())
    ).all()


def summarize_page_status(db: Session, page_id: int) -> dict:
    blocks = db.scalars(
        select(Block).where(Block.page_id == page_id, Block.is_active.is_(True)).order_by(Block.sort_order.asc(), Block.id.asc())
    ).all()
    summary = {
        "active_block_count": len(blocks),
        "success_count": 0,
        "failed_count": 0,
        "never_run_count": 0,
        "last_updated_at": None,
    }
    for block in blocks:
        latest = db.scalars(
            select(RunHistory).where(RunHistory.block_id == block.id).order_by(RunHistory.started_at.desc()).limit(1)
        ).first()
        if not latest:
            summary["never_run_count"] += 1
            continue
        if latest.status == "success":
            summary["success_count"] += 1
        else:
            summary["failed_count"] += 1
        if not summary["last_updated_at"] or latest.finished_at > summary["last_updated_at"]:
            summary["last_updated_at"] = latest.finished_at
    return summary


def _execute_block_object(db: Session, block: Block, run_type: str = "manual") -> RunHistory:
    started = datetime.utcnow()
    run = RunHistory(
        page_id=block.page_id,
        block_id=block.id,
        run_type=run_type,
        status="failed",
        summary="started",
        started_at=started,
        finished_at=started,
        duration_ms=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    output_dir = ensure_run_dir(run.id)
    payload: dict

    try:
        config = _safe_json(block.config_json)
        if block.block_type == "python":
            timeout = int(config.get("timeout_sec") or 300)
            payload = run_python_block(block.source_code_text or "", config, timeout_sec=timeout)
        elif block.block_type == "sql":
            payload = run_sql_block(block.source_code_text or "", config, output_dir)
        else:
            payload = {
                "status": "success",
                "summary": "Markdown rendered",
                "content_html": markdown_to_html(block.source_code_text or ""),
                "content_text": block.source_code_text or "",
                "error_text": "",
                "attachments": [],
            }
    except Exception:
        payload = {
            "status": "failed",
            "summary": "Execution exception",
            "content_html": "",
            "content_text": "",
            "error_text": traceback.format_exc(),
            "attachments": [],
        }

    finished = datetime.utcnow()
    run.status = payload.get("status", "failed")
    run.summary = payload.get("summary", "")
    run.content_html = payload.get("content_html", "")
    run.content_text = payload.get("content_text", "")
    run.error_text = payload.get("error_text", "")
    run.finished_at = finished
    run.duration_ms = int((finished - started).total_seconds() * 1000)

    for ap in payload.get("attachments", []):
        p = Path(ap)
        if p.exists():
            db.add(Attachment(run_history_id=run.id, **file_meta(p)))

    db.commit()
    db.refresh(run)
    return run


def run_block(db: Session, block_id: int, run_type: str = "manual") -> RunHistory:
    block = db.get(Block, block_id)
    if not block:
        raise ValueError(f"Block not found: {block_id}")
    return _execute_block_object(db, block, run_type=run_type)


def run_page(db: Session, page_id: int, run_type: str = "manual") -> dict:
    page = db.get(Page, page_id)
    if not page:
        raise ValueError(f"Page not found: {page_id}")

    blocks = db.scalars(
        select(Block)
        .where(Block.page_id == page_id, Block.is_active.is_(True), Block.block_type.in_(["python", "sql"]))
        .order_by(Block.sort_order.asc(), Block.id.asc())
    ).all()

    runs: list[RunHistory] = []
    success = 0
    failed = 0
    for block in blocks:
        run = _execute_block_object(db, block, run_type=run_type)
        runs.append(run)
        if run.status == "success":
            success += 1
        else:
            failed += 1

    return {
        "total": len(blocks),
        "success": success,
        "failed": failed,
        "runs": runs,
    }


def get_page_dashboard_data(db: Session, page_id: int) -> dict:
    page = db.get(Page, page_id)
    if not page:
        raise ValueError(f"Page not found: {page_id}")
    blocks = db.scalars(
        select(Block).where(Block.page_id == page_id).order_by(Block.sort_order.asc(), Block.id.asc())
    ).all()

    cards = []
    for block in blocks:
        latest_any = db.scalars(
            select(RunHistory).where(RunHistory.block_id == block.id).order_by(RunHistory.started_at.desc()).limit(1)
        ).first()
        preferred = get_latest_preferred_run(db, block.id)
        attachments = []
        if preferred:
            attachments = db.scalars(
                select(Attachment)
                .where(Attachment.run_history_id == preferred.id)
                .order_by(Attachment.created_at.desc(), Attachment.id.desc())
            ).all()
        cards.append(
            {
                "block": block,
                "latest_any": latest_any,
                "preferred_run": preferred,
                "attachments": attachments,
            }
        )

    summary = summarize_page_status(db, page_id)
    return {"page": page, "cards": cards, "summary": summary}

