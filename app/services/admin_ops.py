from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import TEMP_DIR
from app.models import BlockSnapshot, Category, PageSnapshot, PreviewRun, ReportBlock, ReportPage, RunHistory
from app.services.run_service import run_block, run_page_and_create_snapshot

TEMPLATE_DIR = Path("samples/page_templates")

WEEKDAY_LABEL = {"0": "일", "1": "월", "2": "화", "3": "수", "4": "목", "5": "금", "6": "토"}


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


def validate_schedule_form(kind: str, hhmm: str, weekdays: list[str], month_day: str, custom_cron: str) -> list[str]:
    errors: list[str] = []
    if kind in {"daily", "weekly", "monthly"}:
        if not re.match(r"^\d{2}:\d{2}$", hhmm or ""):
            errors.append("실행 시간은 HH:MM 형식이어야 합니다.")
        else:
            hh, mm = [int(x) for x in hhmm.split(":", 1)]
            if hh > 23 or mm > 59:
                errors.append("실행 시간이 올바르지 않습니다.")
    if kind == "weekly" and not weekdays:
        errors.append("매주 스케줄은 요일을 1개 이상 선택해야 합니다.")
    if kind == "monthly":
        try:
            day = int(month_day or "0")
            if day < 1 or day > 31:
                errors.append("매월 일자는 1~31 이어야 합니다.")
        except Exception:
            errors.append("매월 일자가 올바르지 않습니다.")
    if kind == "custom":
        ok, msg = validate_schedule_cron(custom_cron)
        if not ok:
            errors.append(msg)
    return errors


def build_cron_from_schedule_form(kind: str, hhmm: str, weekdays: list[str], month_day: str, custom_cron: str) -> tuple[bool, str, dict]:
    if kind in {"none", ""}:
        return True, "", {"kind": "none", "cron": "", "enabled": False, "meta": {}}

    errors = validate_schedule_form(kind, hhmm, weekdays, month_day, custom_cron)
    if errors:
        return False, errors[0], {"kind": kind, "cron": "", "enabled": False, "meta": {}}

    if kind == "custom":
        return True, "", {"kind": kind, "cron": custom_cron.strip(), "enabled": True, "meta": {"custom": True}}

    hh, mm = [int(x) for x in hhmm.split(":", 1)]
    if kind == "daily":
        cron = f"{mm} {hh} * * *"
        meta = {"time": hhmm}
    elif kind == "weekly":
        days = sorted({str(int(x) % 7) for x in weekdays}, key=int)
        cron = f"{mm} {hh} * * {','.join(days)}"
        meta = {"time": hhmm, "weekdays": days}
    else:
        day = int(month_day)
        cron = f"{mm} {hh} {day} * *"
        meta = {"time": hhmm, "month_day": day}
    return True, "", {"kind": kind, "cron": cron, "enabled": True, "meta": meta}


def describe_schedule(enabled: bool, kind: str, cron: str, meta_json: str | None) -> str:
    if not enabled:
        return "사용 안 함"
    meta = {}
    try:
        meta = json.loads(meta_json or "{}")
    except Exception:
        meta = {}
    if kind == "daily":
        return f"매일 {meta.get('time', '')}".strip()
    if kind == "weekly":
        labels = [WEEKDAY_LABEL.get(str(x), str(x)) for x in meta.get("weekdays", [])]
        return f"매주 {','.join(labels)} {meta.get('time', '')}".strip()
    if kind == "monthly":
        return f"매월 {meta.get('month_day', '')}일 {meta.get('time', '')}".strip()
    return f"사용자정의({cron})"


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
    return next((t for t in load_page_templates() if t.get("template_key") == template_key), None)


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
        is_archived=False,
        schedule_enabled=bool(t.get("schedule_enabled", False)),
        schedule_cron=t.get("schedule_cron", "0 7 * * *"),
        schedule_kind="custom",
        schedule_meta_json="{}",
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
                is_archived=False,
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
        is_archived=False,
        schedule_enabled=False,
        schedule_cron=src.schedule_cron,
        schedule_kind=src.schedule_kind,
        schedule_meta_json=src.schedule_meta_json,
    )
    db.add(page)
    db.flush()
    for b in src.blocks:
        if b.is_archived:
            continue
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
                is_archived=False,
            )
        )
    db.commit()
    db.refresh(page)
    return page


def clone_block(db: Session, block_id: int) -> ReportBlock:
    b = db.get(ReportBlock, block_id)
    if not b:
        raise ValueError("block not found")
    max_sort = db.scalars(select(func.max(ReportBlock.sort_order)).where(ReportBlock.page_id == b.page_id)).first() or 0
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
        sort_order=max_sort + 1,
        is_active=b.is_active,
        is_archived=False,
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


def safe_delete_or_archive_category(db: Session, category_id: int) -> tuple[str, str]:
    category = db.get(Category, category_id)
    if not category:
        return "not_found", "카테고리를 찾을 수 없습니다."
    page_count = db.scalar(select(func.count()).select_from(ReportPage).where(ReportPage.category_id == category_id)) or 0
    if page_count > 0:
        category.is_archived = True
        category.is_active = False
        category.archived_at = datetime.utcnow()
        db.commit()
        return "archived", f"연결된 페이지({page_count})가 있어 카테고리를 보관 처리했습니다."
    db.delete(category)
    db.commit()
    return "deleted", "카테고리를 삭제했습니다."


def safe_delete_or_archive_page(db: Session, page_id: int) -> tuple[str, str]:
    page = db.get(ReportPage, page_id)
    if not page:
        return "not_found", "페이지를 찾을 수 없습니다."
    block_count = db.scalar(select(func.count()).select_from(ReportBlock).where(ReportBlock.page_id == page_id)) or 0
    run_count = db.scalar(select(func.count()).select_from(RunHistory).where(RunHistory.page_id == page_id)) or 0
    snap_count = db.scalar(select(func.count()).select_from(PageSnapshot).where(PageSnapshot.page_id == page_id)) or 0
    if block_count > 0 or run_count > 0 or snap_count > 0:
        page.is_archived = True
        page.is_active = False
        page.archived_at = datetime.utcnow()
        db.commit()
        return "archived", f"참조(블록 {block_count}, 실행 {run_count}, 스냅샷 {snap_count})가 있어 보관 처리했습니다."
    db.delete(page)
    db.commit()
    return "deleted", "페이지를 삭제했습니다."


def safe_delete_or_archive_block(db: Session, block_id: int) -> tuple[str, str]:
    block = db.get(ReportBlock, block_id)
    if not block:
        return "not_found", "블록을 찾을 수 없습니다."
    run_count = db.scalar(select(func.count()).select_from(RunHistory).where(RunHistory.block_id == block_id)) or 0
    snap_count = db.scalar(select(func.count()).select_from(BlockSnapshot).where(BlockSnapshot.block_id == block_id)) or 0
    if run_count > 0 or snap_count > 0:
        block.is_archived = True
        block.is_active = False
        block.archived_at = datetime.utcnow()
        db.commit()
        return "archived", f"실행/스냅샷 이력({run_count + snap_count})이 있어 보관 처리했습니다."
    db.delete(block)
    db.commit()
    return "deleted", "블록을 삭제했습니다."


def set_archive_state(obj, archive: bool) -> None:
    obj.is_archived = archive
    if archive:
        obj.is_active = False
        obj.archived_at = datetime.utcnow()
    else:
        obj.archived_at = None


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
    rows = db.scalars(select(BlockSnapshot).where(BlockSnapshot.status == "failed").order_by(BlockSnapshot.started_at.desc()).limit(limit)).all()
    return [
        {
            "page_title": r.page_snapshot.page.title,
            "block_title": r.block.title,
            "started_at": r.started_at,
            "summary": r.summary,
            "error_short": ((r.error_text or "").strip().splitlines()[-1] if (r.error_text or "").strip() else "")[:200],
            "snapshot_id": r.page_snapshot_id,
        }
        for r in rows
    ]


def search_view_pages(db: Session, q: str, limit: int = 30) -> list[ReportPage]:
    keyword = f"%{(q or '').strip()}%"
    if not q:
        return []
    return db.scalars(
        select(ReportPage)
        .join(Category, Category.id == ReportPage.category_id)
        .where(
            Category.is_active.is_(True),
            Category.is_archived.is_(False),
            ReportPage.is_active.is_(True),
            ReportPage.is_archived.is_(False),
            or_(ReportPage.title.like(keyword), ReportPage.description.like(keyword), ReportPage.slug.like(keyword), Category.name.like(keyword)),
        )
        .order_by(ReportPage.updated_at.desc())
        .limit(limit)
    ).all()


def get_published_pages_for_sidebar(db: Session):
    pages = db.scalars(
        select(ReportPage)
        .join(Category, Category.id == ReportPage.category_id)
        .join(PageSnapshot, PageSnapshot.page_id == ReportPage.id)
        .where(
            Category.is_active.is_(True),
            Category.is_archived.is_(False),
            ReportPage.is_active.is_(True),
            ReportPage.is_archived.is_(False),
            PageSnapshot.is_published.is_(True),
        )
        .group_by(ReportPage.id)
        .order_by(Category.sort_order.asc(), ReportPage.sort_order.asc(), ReportPage.title.asc())
    ).all()
    return pages


def build_view_sidebar_tree(db: Session):
    categories = db.scalars(
        select(Category)
        .where(Category.is_active.is_(True), Category.is_archived.is_(False))
        .order_by(Category.sort_order.asc(), Category.name.asc())
    ).all()
    pages = get_published_pages_for_sidebar(db)
    pages_by_cat: dict[int, list[ReportPage]] = {}
    for p in pages:
        pages_by_cat.setdefault(p.category_id, []).append(p)
    return [{"category": c, "pages": pages_by_cat.get(c.id, [])} for c in categories]
