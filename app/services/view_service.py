from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Attachment, Category, ReportBlock, ReportPage, RunHistory
from app.services.renderers import markdown_to_html, run_content_html


@dataclass
class ViewBlockResult:
    block: ReportBlock
    run: RunHistory | None
    status: str
    display_html: str
    short_error: str
    attachments: list[Attachment]
    last_success_at: datetime | None


def get_active_categories_for_view(db: Session):
    categories = db.scalars(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order.asc(), Category.name.asc())
    ).all()
    counts = dict(
        db.execute(
            select(ReportPage.category_id, func.count(ReportPage.id))
            .where(ReportPage.is_active.is_(True))
            .group_by(ReportPage.category_id)
        ).all()
    )
    return categories, counts


def get_active_pages_for_category(db: Session, category_slug: str):
    category = db.scalars(
        select(Category).where(Category.slug == category_slug, Category.is_active.is_(True)).limit(1)
    ).first()
    if not category:
        return None, []
    pages = db.scalars(
        select(ReportPage)
        .where(ReportPage.category_id == category.id, ReportPage.is_active.is_(True))
        .order_by(ReportPage.sort_order.asc(), ReportPage.title.asc())
    ).all()
    return category, pages


def get_page_for_view(db: Session, category_slug: str, page_slug: str):
    return db.scalars(
        select(ReportPage)
        .join(Category, Category.id == ReportPage.category_id)
        .where(
            Category.slug == category_slug,
            Category.is_active.is_(True),
            ReportPage.slug == page_slug,
            ReportPage.is_active.is_(True),
        )
        .limit(1)
    ).first()


def get_latest_preferred_run(db: Session, block_id: int) -> RunHistory | None:
    success = db.scalars(
        select(RunHistory)
        .where(RunHistory.block_id == block_id, RunHistory.status == "success")
        .order_by(RunHistory.started_at.desc())
        .limit(1)
    ).first()
    if success:
        return success
    return db.scalars(
        select(RunHistory).where(RunHistory.block_id == block_id).order_by(RunHistory.started_at.desc()).limit(1)
    ).first()


def get_runs_for_page_history(db: Session, page_id: int, limit: int = 10):
    return db.scalars(
        select(RunHistory)
        .where(RunHistory.page_id == page_id)
        .order_by(RunHistory.started_at.desc())
        .limit(limit)
    ).all()


def get_run_for_block_at_or_before(db: Session, block_id: int, run_time: datetime) -> RunHistory | None:
    success = db.scalars(
        select(RunHistory)
        .where(RunHistory.block_id == block_id, RunHistory.started_at <= run_time, RunHistory.status == "success")
        .order_by(RunHistory.started_at.desc())
        .limit(1)
    ).first()
    if success:
        return success
    return db.scalars(
        select(RunHistory)
        .where(RunHistory.block_id == block_id, RunHistory.started_at <= run_time)
        .order_by(RunHistory.started_at.desc())
        .limit(1)
    ).first()


def get_latest_page_status(db: Session, page_id: int) -> tuple[str, datetime | None]:
    blocks = db.scalars(
        select(ReportBlock).where(
            ReportBlock.page_id == page_id,
            ReportBlock.is_active.is_(True),
            ReportBlock.block_type.in_(["python", "sql"]),
        )
    ).all()
    if not blocks:
        return "결과 없음", None
    has_success = False
    has_failed = False
    latest_time = None
    for b in blocks:
        r = db.scalars(select(RunHistory).where(RunHistory.block_id == b.id).order_by(RunHistory.started_at.desc()).limit(1)).first()
        if not r:
            continue
        if not latest_time or r.started_at > latest_time:
            latest_time = r.started_at
        if r.status == "success":
            has_success = True
        elif r.status == "failed":
            has_failed = True
    if not has_success and not has_failed:
        return "결과 없음", latest_time
    if has_success and has_failed:
        return "일부 실패", latest_time
    if has_success:
        return "정상", latest_time
    return "최근 갱신 전", latest_time


def _short_error(error_text: str) -> str:
    if not error_text:
        return ""
    line = error_text.strip().splitlines()[-1]
    return line[:180]


def build_view_page_context(db: Session, page_id: int, selected_run_id: int | None = None, history_limit: int = 14):
    page = db.get(ReportPage, page_id)
    blocks = db.scalars(
        select(ReportBlock).where(ReportBlock.page_id == page_id, ReportBlock.is_active.is_(True)).order_by(ReportBlock.sort_order.asc(), ReportBlock.id.asc())
    ).all()
    history = get_runs_for_page_history(db, page_id, limit=history_limit)

    selected_run = None
    selected_time = None
    if selected_run_id:
        selected_run = db.get(RunHistory, selected_run_id)
        if selected_run and selected_run.page_id == page_id:
            selected_time = selected_run.started_at

    block_results: list[ViewBlockResult] = []
    for block in blocks:
        if block.block_type == "markdown":
            block_results.append(
                ViewBlockResult(
                    block=block,
                    run=None,
                    status="안내",
                    display_html=markdown_to_html(block.source_code_text or ""),
                    short_error="",
                    attachments=[],
                    last_success_at=None,
                )
            )
            continue

        run = get_run_for_block_at_or_before(db, block.id, selected_time) if selected_time else get_latest_preferred_run(db, block.id)
        last_success = db.scalars(
            select(RunHistory)
            .where(RunHistory.block_id == block.id, RunHistory.status == "success")
            .order_by(RunHistory.started_at.desc())
            .limit(1)
        ).first()
        attachments = []
        if run:
            attachments = db.scalars(
                select(Attachment).where(Attachment.run_history_id == run.id).order_by(Attachment.created_at.desc())
            ).all()
        status = "no-data"
        if run:
            status = run.status
        block_results.append(
            ViewBlockResult(
                block=block,
                run=run,
                status=status,
                display_html=run_content_html(run),
                short_error=_short_error(run.error_text if run else ""),
                attachments=attachments,
                last_success_at=last_success.started_at if last_success else None,
            )
        )

    page_status, latest_update = get_latest_page_status(db, page_id)
    return {
        "page": page,
        "history": history,
        "selected_run_id": selected_run_id,
        "selected_time": selected_time,
        "latest_update": latest_update,
        "page_status": page_status,
        "block_results": block_results,
    }
