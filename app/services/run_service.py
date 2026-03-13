from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Attachment, ReportBlock, ReportPage, RunHistory
from app.services.renderers import markdown_to_html
from app.services.runner_python import run_python_block
from app.services.runner_sql import run_sql_block
from app.services.storage import ensure_run_dir, file_meta


def _safe_json(text: str) -> dict:
    try:
        return json.loads(text or "{}")
    except Exception:
        return {}


def run_block(db: Session, block_id: int, run_type: str = "manual") -> RunHistory:
    block = db.get(ReportBlock, block_id)
    if not block:
        raise ValueError("block not found")
    if block.block_type == "markdown":
        raise ValueError("markdown block is not executable")

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

    payload: dict
    output_dir = ensure_run_dir(run.id)

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
                "summary": "Unsupported block type skipped",
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

    for item in payload.get("attachments", []):
        p = Path(item)
        if p.exists():
            db.add(Attachment(run_history_id=run.id, **file_meta(p)))

    db.commit()
    db.refresh(run)
    return run


def run_page(db: Session, page_id: int, run_type: str = "manual") -> dict:
    blocks = db.scalars(
        select(ReportBlock)
        .where(
            ReportBlock.page_id == page_id,
            ReportBlock.is_active.is_(True),
            ReportBlock.block_type.in_(["python", "sql"]),
        )
        .order_by(ReportBlock.sort_order.asc(), ReportBlock.id.asc())
    ).all()
    runs = []
    success, failed = 0, 0
    for block in blocks:
        try:
            run = run_block(db, block.id, run_type=run_type)
        except Exception:
            failed += 1
            continue
        runs.append(run)
        if run.status == "success":
            success += 1
        else:
            failed += 1
    return {"total": len(blocks), "success": success, "failed": failed, "runs": runs}


def latest_runs(db: Session, limit: int = 10) -> list[RunHistory]:
    return db.scalars(select(RunHistory).order_by(RunHistory.started_at.desc()).limit(limit)).all()


def latest_failed_runs(db: Session, limit: int = 5) -> list[RunHistory]:
    return db.scalars(
        select(RunHistory).where(RunHistory.status == "failed").order_by(RunHistory.started_at.desc()).limit(limit)
    ).all()


def page_latest_run(db: Session, page_id: int) -> RunHistory | None:
    return db.scalars(select(RunHistory).where(RunHistory.page_id == page_id).order_by(RunHistory.started_at.desc()).limit(1)).first()


def block_latest_run(db: Session, block_id: int) -> RunHistory | None:
    return db.scalars(select(RunHistory).where(RunHistory.block_id == block_id).order_by(RunHistory.started_at.desc()).limit(1)).first()


def count_entities(db: Session) -> dict:
    from app.models import Category

    return {
        "categories": db.scalar(select(func.count()).select_from(Category)) or 0,
        "pages": db.scalar(select(func.count()).select_from(ReportPage)) or 0,
        "blocks": db.scalar(select(func.count()).select_from(ReportBlock)) or 0,
        "scheduled_blocks": db.scalar(
            select(func.count()).select_from(ReportBlock).where(ReportBlock.schedule_enabled.is_(True), ReportBlock.is_active.is_(True))
        )
        or 0,
    }
