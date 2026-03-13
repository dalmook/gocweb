from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attachment, Block, RunHistory
from app.services.renderers import markdown_to_html
from app.services.runner_python import run_python_block
from app.services.runner_sql import run_sql_block
from app.services.storage import ensure_run_dir, file_meta


def _safe_json(text: str) -> dict:
    try:
        return json.loads(text or "{}")
    except Exception:
        return {}


def execute_block(db: Session, block: Block, run_type: str = "manual") -> RunHistory:
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


def execute_page_blocks(db: Session, page_id: int, run_type: str = "manual") -> list[RunHistory]:
    blocks = db.scalars(
        select(Block)
        .where(Block.page_id == page_id, Block.is_active.is_(True))
        .order_by(Block.sort_order.asc(), Block.id.asc())
    ).all()
    return [execute_block(db, b, run_type=run_type) for b in blocks]
