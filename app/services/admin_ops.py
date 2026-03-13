from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import ARTIFACTS_DIR, TEMP_DIR
from app.models import BlockSnapshot, PageSnapshot, PreviewRun, ReportBlock, ReportPage
from app.services.run_service import merge_run_params, run_block, run_page_and_create_snapshot

TEMPLATE_DIR = Path("samples/page_templates")


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", text.strip().lower()).strip("-")
    return s or "page"


def ensure_unique_page_slug(db: Session, base: str) -> str:
    slug = _slugify(base)
    i = 1
    while db.scalars(select(ReportPage).where(ReportPage.slug == slug)).first():
        i += 1
        slug = f"{_slugify(base)}-{i}"
    return slug


def validate_schedule_cron(cron: str) -> tuple[bool, str]:
    parts = (cron or "").split()
    if len(parts) != 5:
        return False, "cron은 5필드(min hour day month dow) 형식이어야 합니다."
    return True, ""


def _validate_json(text: str, field: str) -> tuple[bool, str, object]:
    try:
        obj = json.loads(text or "{}")
        return True, "", obj
    except Exception as e:
        return False, f"{field} JSON 파싱 오류: {e}", None


def validate_block_payload(config_json: str, params_schema_json: str, default_params_json: str, cron: str | None = None) -> list[str]:
    errors: list[str] = []

    ok, msg, _ = _validate_json(config_json, "config_json")
    if not ok:
        errors.append(msg)

    ok, msg, schema_obj = _validate_json(params_schema_json or "[]", "params_schema_json")
    if not ok:
        errors.append(msg)
    elif not isinstance(schema_obj, list):
        errors.append("params_schema_json은 list 형식이어야 합니다.")
    else:
        for i, item in enumerate(schema_obj):
            if not isinstance(item, dict) or "name" not in item:
                errors.append(f"params_schema_json[{i}]는 name을 포함한 object여야 합니다.")

    ok, msg, default_obj = _validate_json(default_params_json or "{}", "default_params_json")
    if not ok:
        errors.append(msg)
    elif not isinstance(default_obj, dict):
        errors.append("default_params_json은 object 형식이어야 합니다.")

    if cron:
        ok, msg = validate_schedule_cron(cron)
        if not ok:
            errors.append(msg)

    return errors


def load_page_templates() -> list[dict]:
    templates = []
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    for p in sorted(TEMPLATE_DIR.glob("*.json")):
        try:
            templates.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return templates


def get_page_template(template_key: str) -> dict | None:
    for t in load_page_templates():
        if t.get("template_key") == template_key:
            return t
    return None


def create_page_from_template(db: Session, category_id: int, title: str, slug: str, template_key: str) -> ReportPage:
    t = get_page_template(template_key)
    if not t:
        raise ValueError("template not found")
    page = ReportPage(
        category_id=category_id,
        title=title or t.get("title", "템플릿 페이지"),
        slug=slug or ensure_unique_page_slug(db, title or t.get("title", "template")),
        description=t.get("description", ""),
        sort_order=0,
        is_active=True,
        schedule_enabled=bool(t.get("schedule_enabled", False)),
        schedule_cron=t.get("schedule_cron", "0 7 * * *"),
    )
    db.add(page)
    db.flush()

    for i, b in enumerate(t.get("blocks", []), start=1):
        db.add(
            ReportBlock(
                page_id=page.id,
                title=b.get("title", f"block-{i}"),
                description=b.get("description", ""),
                block_type=b.get("block_type", "markdown"),
                source_code_text=b.get("source_code_text", ""),
                config_json=json.dumps(b.get("config_json", {}), ensure_ascii=False),
                params_schema_json=json.dumps(b.get("params_schema_json", []), ensure_ascii=False),
                default_params_json=json.dumps(b.get("default_params_json", {}), ensure_ascii=False),
                schedule_enabled=bool(b.get("schedule_enabled", False)),
                schedule_cron=b.get("schedule_cron", "0 7 * * *"),
                sort_order=b.get("sort_order", i),
                is_active=bool(b.get("is_active", True)),
            )
        )

    db.commit()
    db.refresh(page)
    return page


def clone_page(db: Session, page_id: int) -> ReportPage:
    src = db.get(ReportPage, page_id)
    if not src:
        raise ValueError("page not found")
    new_title = f"{src.title} - 복사본"
    page = ReportPage(
        category_id=src.category_id,
        title=new_title,
        slug=ensure_unique_page_slug(db, new_title),
        description=src.description,
        sort_order=src.sort_order,
        is_active=src.is_active,
        schedule_enabled=False,
        schedule_cron=src.schedule_cron,
    )
    db.add(page)
    db.flush()
    for b in src.blocks:
        db.add(
            ReportBlock(
                page_id=page.id,
                title=f"{b.title} - 복사본",
                description=b.description,
                block_type=b.block_type,
                source_code_text=b.source_code_text,
                config_json=b.config_json,
                params_schema_json=b.params_schema_json,
                default_params_json=b.default_params_json,
                schedule_enabled=False,
                schedule_cron=b.schedule_cron,
                sort_order=b.sort_order,
                is_active=b.is_active,
            )
        )
    db.commit()
    db.refresh(page)
    return page


def clone_block(db: Session, block_id: int) -> ReportBlock:
    b = db.get(ReportBlock, block_id)
    if not b:
        raise ValueError("block not found")
    max_sort = db.scalars(select(ReportBlock.sort_order).where(ReportBlock.page_id == b.page_id).order_by(ReportBlock.sort_order.desc())).first()
    cloned = ReportBlock(
        page_id=b.page_id,
        title=f"{b.title} - 복사본",
        description=b.description,
        block_type=b.block_type,
        source_code_text=b.source_code_text,
        config_json=b.config_json,
        params_schema_json=b.params_schema_json,
        default_params_json=b.default_params_json,
        schedule_enabled=False,
        schedule_cron=b.schedule_cron,
        sort_order=(max_sort or 0) + 1,
        is_active=b.is_active,
    )
    db.add(cloned)
    db.commit()
    db.refresh(cloned)
    return cloned


def preview_block_run(db: Session, block_id: int, run_params: dict) -> PreviewRun:
    run = run_block(db, block_id, run_type="manual", run_params=run_params)
    pr = PreviewRun(
        block_id=block_id,
        status=run.status,
        summary=run.summary,
        content_html=run.content_html,
        content_text=run.content_text,
        error_text=run.error_text,
        run_params_json=json.dumps(run_params, ensure_ascii=False),
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    return pr


def run_page_with_params(db: Session, page_id: int, run_type: str, trigger_source: str, common_params: dict) -> PageSnapshot:
    return run_page_and_create_snapshot(db, page_id, run_type=run_type, trigger_source=trigger_source, run_params=common_params)


def cleanup_old_snapshots(db: Session, keep_per_page: int = 20) -> dict:
    deleted = 0
    pages = db.scalars(select(ReportPage)).all()
    for p in pages:
        snaps = db.scalars(select(PageSnapshot).where(PageSnapshot.page_id == p.id).order_by(PageSnapshot.started_at.desc())).all()
        for s in snaps[keep_per_page:]:
            db.delete(s)
            deleted += 1
    db.commit()
    return {"deleted_snapshots": deleted}


def cleanup_temp_files(days: int = 30) -> dict:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    threshold = datetime.utcnow() - timedelta(days=days)
    deleted = 0
    for p in TEMP_DIR.iterdir():
        try:
            if datetime.utcfromtimestamp(p.stat().st_mtime) < threshold:
                if p.is_file():
                    p.unlink()
                else:
                    import shutil

                    shutil.rmtree(p, ignore_errors=True)
                deleted += 1
        except Exception:
            pass
    return {"deleted_temp_entries": deleted}


def get_recent_failures(db: Session, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        select(BlockSnapshot).where(BlockSnapshot.status == "failed").order_by(BlockSnapshot.started_at.desc()).limit(limit)
    ).all()
    out = []
    for r in rows:
        err = (r.error_text or "").strip().splitlines()
        out.append(
            {
                "page_title": r.page_snapshot.page.title,
                "block_title": r.block.title,
                "started_at": r.started_at,
                "summary": r.summary,
                "error_short": (err[-1] if err else "")[:200],
                "snapshot_id": r.page_snapshot_id,
            }
        )
    return out
