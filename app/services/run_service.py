from __future__ import annotations

import hashlib
import json
import traceback
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Attachment,
    BlockSnapshot,
    Category,
    PageSnapshot,
    ReportBlock,
    ReportPage,
    RunHistory,
    SnapshotAttachment,
)
from app.services.runner_python import run_python_block
from app.services.runner_sql import run_sql_block
from app.services.storage import ensure_run_dir, file_meta


def _safe_json(text: str, default):
    try:
        return json.loads(text or json.dumps(default))
    except Exception:
        return default


def merge_run_params(input_params: dict | None, block_default_json: str | None, config_json: str | None) -> dict:
    merged = {}
    cfg = _safe_json(config_json or "{}", {})
    cfg_default = cfg.get("default_params") if isinstance(cfg, dict) else {}
    if isinstance(cfg_default, dict):
        merged.update(cfg_default)
    block_defaults = _safe_json(block_default_json or "{}", {})
    if isinstance(block_defaults, dict):
        merged.update(block_defaults)
    if isinstance(input_params, dict):
        merged.update(input_params)
    return merged


def run_block(db: Session, block_id: int, run_type: str = "manual", run_params: dict | None = None) -> RunHistory:
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

    params = merge_run_params(run_params, block.default_params_json, block.config_json)

    try:
        config = _safe_json(block.config_json, {})
        config["params"] = params
        if block.block_type == "python":
            timeout = int(config.get("timeout_sec") or 300)
            payload = run_python_block(block.source_code_text or "", config, timeout_sec=timeout)
        elif block.block_type == "sql":
            payload = run_sql_block(block.source_code_text or "", config, output_dir, params=params)
        else:
            payload = {"status": "skipped", "summary": "skipped", "attachments": []}
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


def _snapshot_key(page_id: int) -> str:
    now = datetime.utcnow()
    return f"p{page_id}-{now.strftime('%Y%m%d-%H%M%S-%f')}"


def run_page_and_create_snapshot(
    db: Session,
    page_id: int,
    run_type: str = "manual",
    trigger_source: str = "admin",
    run_params: dict | None = None,
) -> PageSnapshot:
    page = db.get(ReportPage, page_id)
    if not page:
        raise ValueError("page not found")

    started = datetime.utcnow()
    snapshot = PageSnapshot(
        page_id=page_id,
        snapshot_key=_snapshot_key(page_id),
        snapshot_date=started.date(),
        run_type=run_type,
        status="failed",
        summary="running",
        started_at=started,
        finished_at=started,
        duration_ms=0,
        is_published=True,
        trigger_source=trigger_source,
        run_params_json=json.dumps(run_params or {}, ensure_ascii=False),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    blocks = db.scalars(
        select(ReportBlock)
        .where(ReportBlock.page_id == page_id, ReportBlock.is_active.is_(True))
        .order_by(ReportBlock.sort_order.asc(), ReportBlock.id.asc())
    ).all()
    exec_blocks = [b for b in blocks if b.block_type in {"python", "sql"}]
    succ = fail = 0

    for block in exec_blocks:
        bs_started = datetime.utcnow()
        try:
            run_log = run_block(db, block.id, run_type=run_type, run_params=run_params)
            status = "success" if run_log.status == "success" else "failed"
            summary = run_log.summary
            content_html = run_log.content_html
            content_text = run_log.content_text
            error_text = run_log.error_text
            source_attachments = run_log.attachments
        except Exception:
            status = "failed"
            summary = "Execution exception"
            content_html = ""
            content_text = ""
            error_text = traceback.format_exc()
            source_attachments = []

        if status == "success":
            succ += 1
        else:
            fail += 1

        bs_finished = datetime.utcnow()
        content_joined = (content_html or "") + "\n" + (content_text or "")
        bs = BlockSnapshot(
            page_snapshot_id=snapshot.id,
            block_id=block.id,
            status=status,
            summary=summary,
            content_html=content_html,
            content_text=content_text,
            error_text=error_text,
            started_at=bs_started,
            finished_at=bs_finished,
            duration_ms=int((bs_finished - bs_started).total_seconds() * 1000),
            content_hash=hashlib.sha256(content_joined.encode("utf-8")).hexdigest(),
            summary_hash=hashlib.sha256((summary or "").encode("utf-8")).hexdigest(),
        )
        db.add(bs)
        db.commit()
        db.refresh(bs)

        for a in source_attachments:
            db.add(
                SnapshotAttachment(
                    block_snapshot_id=bs.id,
                    file_name=a.file_name,
                    stored_path=a.stored_path,
                    mime_type=a.mime_type,
                    file_size=a.file_size,
                )
            )
        db.commit()

    finished = datetime.utcnow()
    snapshot.finished_at = finished
    snapshot.duration_ms = int((finished - started).total_seconds() * 1000)
    if not exec_blocks:
        snapshot.status = "failed"
        snapshot.summary = "실행 가능한 블록 없음"
    elif succ == len(exec_blocks):
        snapshot.status = "success"
        snapshot.summary = f"전체 성공 ({succ}/{len(exec_blocks)})"
    elif succ > 0:
        snapshot.status = "partial_failed"
        snapshot.summary = f"일부 실패 (성공 {succ}, 실패 {fail})"
    else:
        snapshot.status = "failed"
        snapshot.summary = f"전체 실패 ({fail}/{len(exec_blocks)})"
    db.commit()
    db.refresh(snapshot)
    return snapshot


def run_page(db: Session, page_id: int, run_type: str = "manual") -> dict:
    snap = run_page_and_create_snapshot(db, page_id, run_type=run_type, trigger_source="admin")
    total = len(snap.block_snapshots)
    success = len([x for x in snap.block_snapshots if x.status == "success"])
    failed = len([x for x in snap.block_snapshots if x.status == "failed"])
    return {"total": total, "success": success, "failed": failed, "snapshot": snap}


def get_latest_snapshot_for_page(db: Session, page_id: int) -> PageSnapshot | None:
    return db.scalars(select(PageSnapshot).where(PageSnapshot.page_id == page_id, PageSnapshot.is_published.is_(True)).order_by(PageSnapshot.started_at.desc()).limit(1)).first()


def get_snapshot_by_id(db: Session, snapshot_id: int) -> PageSnapshot | None:
    return db.get(PageSnapshot, snapshot_id)


def get_snapshots_for_page(db: Session, page_id: int, limit: int = 14):
    return db.scalars(select(PageSnapshot).where(PageSnapshot.page_id == page_id, PageSnapshot.is_published.is_(True)).order_by(PageSnapshot.started_at.desc()).limit(limit)).all()


def get_snapshot_blocks(db: Session, snapshot_id: int):
    return db.scalars(select(BlockSnapshot).where(BlockSnapshot.page_snapshot_id == snapshot_id).order_by(BlockSnapshot.id.asc())).all()


def summarize_snapshot_status(snapshot: PageSnapshot) -> dict:
    statuses = [b.status for b in snapshot.block_snapshots]
    return {"success": statuses.count("success"), "failed": statuses.count("failed"), "skipped": statuses.count("skipped")}


def compare_snapshot_with_previous(db: Session, snapshot_id: int) -> list[dict]:
    current = db.get(PageSnapshot, snapshot_id)
    if not current:
        return []
    previous = db.scalars(select(PageSnapshot).where(PageSnapshot.page_id == current.page_id, PageSnapshot.started_at < current.started_at).order_by(PageSnapshot.started_at.desc()).limit(1)).first()

    current_map = {b.block_id: b for b in current.block_snapshots}
    prev_map = {b.block_id: b for b in previous.block_snapshots} if previous else {}
    result = []
    for block_id, cur in current_map.items():
        prev = prev_map.get(block_id)
        if not prev:
            state = "이전 결과 없음"
        elif cur.summary_hash != prev.summary_hash or cur.content_hash != prev.content_hash or len(cur.attachments) != len(prev.attachments):
            state = "변경 있음"
        else:
            state = "동일"
        result.append({"block": cur.block, "state": state})
    return result


def latest_runs(db: Session, limit: int = 10) -> list[RunHistory]:
    return db.scalars(select(RunHistory).order_by(RunHistory.started_at.desc()).limit(limit)).all()


def latest_failed_runs(db: Session, limit: int = 5) -> list[RunHistory]:
    return db.scalars(select(RunHistory).where(RunHistory.status == "failed").order_by(RunHistory.started_at.desc()).limit(limit)).all()


def page_latest_run(db: Session, page_id: int) -> RunHistory | None:
    return db.scalars(select(RunHistory).where(RunHistory.page_id == page_id).order_by(RunHistory.started_at.desc()).limit(1)).first()


def block_latest_run(db: Session, block_id: int) -> RunHistory | None:
    return db.scalars(select(RunHistory).where(RunHistory.block_id == block_id).order_by(RunHistory.started_at.desc()).limit(1)).first()


def count_entities(db: Session) -> dict:
    return {
        "categories": db.scalar(select(func.count()).select_from(Category)) or 0,
        "pages": db.scalar(select(func.count()).select_from(ReportPage)) or 0,
        "blocks": db.scalar(select(func.count()).select_from(ReportBlock)) or 0,
        "scheduled_blocks": db.scalar(select(func.count()).select_from(ReportBlock).where(ReportBlock.schedule_enabled.is_(True), ReportBlock.is_active.is_(True))) or 0,
        "scheduled_pages": db.scalar(select(func.count()).select_from(ReportPage).where(ReportPage.schedule_enabled.is_(True), ReportPage.is_active.is_(True))) or 0,
    }
