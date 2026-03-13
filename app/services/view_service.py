from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
from app.services.renderers import markdown_to_html, run_content_html
from app.services.run_service import compare_snapshot_with_previous


@dataclass
class ViewBlockResult:
    block: ReportBlock
    run: BlockSnapshot | RunHistory | None
    status: str
    summary: str
    display_html: str
    short_error: str
    attachments: list[SnapshotAttachment] | list[Attachment]
    last_success_at: datetime | None


def get_active_categories_for_view(db: Session):
    categories = db.scalars(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order.asc(), Category.name.asc())
    ).all()
    counts = dict(
        db.execute(
            select(ReportPage.category_id, func.count(ReportPage.id)).where(ReportPage.is_active.is_(True)).group_by(ReportPage.category_id)
        ).all()
    )
    return categories, counts


def get_active_pages_for_category(db: Session, category_slug: str):
    category = db.scalars(select(Category).where(Category.slug == category_slug, Category.is_active.is_(True))).first()
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
        .where(Category.slug == category_slug, Category.is_active.is_(True), ReportPage.slug == page_slug, ReportPage.is_active.is_(True))
        .limit(1)
    ).first()


def get_latest_snapshot_for_page(db: Session, page_id: int) -> PageSnapshot | None:
    return db.scalars(
        select(PageSnapshot)
        .where(PageSnapshot.page_id == page_id, PageSnapshot.is_published.is_(True))
        .order_by(PageSnapshot.started_at.desc())
        .limit(1)
    ).first()


def get_snapshots_for_page(db: Session, page_id: int, limit: int = 14):
    return db.scalars(
        select(PageSnapshot)
        .where(PageSnapshot.page_id == page_id, PageSnapshot.is_published.is_(True))
        .order_by(PageSnapshot.started_at.desc())
        .limit(limit)
    ).all()


def get_snapshot_by_id(db: Session, snapshot_id: int) -> PageSnapshot | None:
    return db.get(PageSnapshot, snapshot_id)


def get_snapshot_by_date(db: Session, page_id: int, snapshot_date: str) -> PageSnapshot | None:
    return db.scalars(
        select(PageSnapshot)
        .where(PageSnapshot.page_id == page_id, PageSnapshot.snapshot_date == snapshot_date, PageSnapshot.is_published.is_(True))
        .order_by(PageSnapshot.started_at.desc())
        .limit(1)
    ).first()


def get_latest_page_status(db: Session, page_id: int) -> tuple[str, datetime | None]:
    snap = get_latest_snapshot_for_page(db, page_id)
    if not snap:
        return "결과 없음", None
    if snap.status == "success":
        return "정상", snap.started_at
    if snap.status == "partial_failed":
        return "일부 실패", snap.started_at
    return "실패", snap.started_at


def _short_error(text: str) -> str:
    if not text:
        return ""
    return text.strip().splitlines()[-1][:180]


def _fallback_block_results(db: Session, page: ReportPage) -> list[ViewBlockResult]:
    results: list[ViewBlockResult] = []
    for block in page.blocks:
        if not block.is_active:
            continue
        if block.block_type == "markdown":
            results.append(ViewBlockResult(block, None, "안내", "", markdown_to_html(block.source_code_text or ""), "", [], None))
            continue
        run = db.scalars(select(RunHistory).where(RunHistory.block_id == block.id).order_by(RunHistory.started_at.desc()).limit(1)).first()
        status = run.status if run else "no-data"
        atts = run.attachments if run else []
        last_success = db.scalars(
            select(RunHistory).where(RunHistory.block_id == block.id, RunHistory.status == "success").order_by(RunHistory.started_at.desc()).limit(1)
        ).first()
        results.append(
            ViewBlockResult(
                block=block,
                run=run,
                status=status,
                summary=run.summary if run else "",
                display_html=run_content_html(run),
                short_error=_short_error(run.error_text if run else ""),
                attachments=atts,
                last_success_at=last_success.started_at if last_success else None,
            )
        )
    return results


def build_view_page_context(
    db: Session,
    page_id: int,
    selected_snapshot_id: int | None = None,
    snapshot_date: str | None = None,
    history_limit: int = 14,
):
    page = db.get(ReportPage, page_id)
    snapshots = get_snapshots_for_page(db, page_id, history_limit)

    snapshot = None
    if selected_snapshot_id:
        candidate = get_snapshot_by_id(db, selected_snapshot_id)
        if candidate and candidate.page_id == page_id:
            snapshot = candidate
    elif snapshot_date:
        snapshot = get_snapshot_by_date(db, page_id, snapshot_date)

    if not snapshot:
        snapshot = snapshots[0] if snapshots else None

    block_results: list[ViewBlockResult] = []
    compare_rows = []

    if snapshot:
        compare_rows = compare_snapshot_with_previous(db, snapshot.id)
        block_snap_map = {bs.block_id: bs for bs in snapshot.block_snapshots}
        for block in sorted([b for b in page.blocks if b.is_active], key=lambda x: (x.sort_order, x.id)):
            if block.block_type == "markdown":
                block_results.append(
                    ViewBlockResult(block, None, "안내", "", markdown_to_html(block.source_code_text or ""), "", [], None)
                )
                continue

            bs = block_snap_map.get(block.id)
            if not bs:
                block_results.append(
                    ViewBlockResult(
                        block=block,
                        run=None,
                        status="no-data",
                        summary="",
                        display_html="<p>해당 스냅샷에 결과 없음</p>",
                        short_error="",
                        attachments=[],
                        last_success_at=None,
                    )
                )
                continue

            last_success = db.scalars(
                select(BlockSnapshot)
                .where(BlockSnapshot.block_id == block.id, BlockSnapshot.status == "success")
                .order_by(BlockSnapshot.started_at.desc())
                .limit(1)
            ).first()
            content_html = bs.content_html or run_content_html(type("x", (), {"content_html": "", "content_text": bs.content_text})())
            block_results.append(
                ViewBlockResult(
                    block=block,
                    run=bs,
                    status=bs.status,
                    summary=bs.summary,
                    display_html=content_html,
                    short_error=_short_error(bs.error_text),
                    attachments=bs.attachments,
                    last_success_at=last_success.started_at if last_success else None,
                )
            )
    else:
        block_results = _fallback_block_results(db, page)

    page_status, latest_update = get_latest_page_status(db, page_id)
    return {
        "page": page,
        "snapshots": snapshots,
        "selected_snapshot": snapshot,
        "latest_update": latest_update,
        "page_status": page_status,
        "block_results": block_results,
        "compare_rows": compare_rows,
    }
