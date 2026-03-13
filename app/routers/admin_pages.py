from __future__ import annotations

import json
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, PageSnapshot, ReportBlock, ReportPage, RunHistory
from app.services.admin_ops import (
    build_cron_from_schedule_form,
    clone_page,
    create_page_from_template,
    describe_schedule,
    load_page_templates,
    safe_delete_or_archive_page,
    set_archive_state,
)
from app.services.run_service import block_latest_run, get_latest_snapshot_for_page, get_snapshots_for_page, page_latest_run, run_page_and_create_snapshot

router = APIRouter(prefix="/admin/pages", tags=["admin-pages"])
templates = Jinja2Templates(directory="app/templates")


def _schedule_form_from_page(page: ReportPage) -> dict:
    meta = {}
    try:
        meta = json.loads(page.schedule_meta_json or "{}")
    except Exception:
        pass
    return {
        "kind": page.schedule_kind or ("custom" if page.schedule_enabled else "none"),
        "time": meta.get("time", "07:00"),
        "weekdays": ",".join(meta.get("weekdays", [])),
        "month_day": str(meta.get("month_day", 1)),
        "custom_cron": page.schedule_cron or "0 7 * * *",
    }


@router.get("", response_class=HTMLResponse)
def list_pages(
    request: Request,
    q: str = Query(""),
    category_id: int | None = Query(default=None),
    active: str = Query("all"),
    schedule: str = Query("all"),
    show_archived: bool = Query(False),
    has_snapshot: str = Query("all"),
    msg: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    filters = []
    if not show_archived:
        filters.append(ReportPage.is_archived.is_(False))
    if q:
        keyword = f"%{q}%"
        filters.append(or_(ReportPage.title.like(keyword), ReportPage.description.like(keyword), ReportPage.slug.like(keyword)))
    if category_id:
        filters.append(ReportPage.category_id == category_id)
    if active == "active":
        filters.append(ReportPage.is_active.is_(True))
    elif active == "inactive":
        filters.append(ReportPage.is_active.is_(False))
    if schedule == "on":
        filters.append(ReportPage.schedule_enabled.is_(True))
    elif schedule == "off":
        filters.append(ReportPage.schedule_enabled.is_(False))

    stmt = select(ReportPage)
    if filters:
        stmt = stmt.where(and_(*filters))
    pages = db.scalars(stmt.order_by(ReportPage.updated_at.desc())).all()
    if has_snapshot != "all":
        filtered_pages = []
        for p in pages:
            has = bool(db.scalar(select(func.count()).select_from(PageSnapshot).where(PageSnapshot.page_id == p.id, PageSnapshot.is_published.is_(True))))
            if (has_snapshot == "yes" and has) or (has_snapshot == "no" and not has):
                filtered_pages.append(p)
        pages = filtered_pages

    categories = db.scalars(select(Category).order_by(Category.sort_order.asc(), Category.id.asc())).all()
    block_counts = dict(db.execute(select(ReportBlock.page_id, func.count(ReportBlock.id)).group_by(ReportBlock.page_id)).all())
    latest_runs = dict(db.execute(select(RunHistory.page_id, func.max(RunHistory.started_at)).group_by(RunHistory.page_id)).all())
    latest_published = dict(
        db.execute(
            select(PageSnapshot.page_id, func.max(PageSnapshot.started_at)).where(PageSnapshot.is_published.is_(True)).group_by(PageSnapshot.page_id)
        ).all()
    )
    schedule_labels = {p.id: describe_schedule(p.schedule_enabled, p.schedule_kind, p.schedule_cron, p.schedule_meta_json) for p in pages}
    return templates.TemplateResponse(
        "admin/pages.html",
        {
            "request": request,
            "pages": pages,
            "categories": categories,
            "block_counts": block_counts,
            "latest_runs": latest_runs,
            "latest_published": latest_published,
            "schedule_labels": schedule_labels,
            "filters": {"q": q, "category_id": category_id, "active": active, "schedule": schedule, "show_archived": show_archived, "has_snapshot": has_snapshot},
            "message": msg,
        },
    )


@router.get("/new", response_class=HTMLResponse)
def new_page_form(request: Request, db: Session = Depends(get_db)):
    categories = db.scalars(select(Category).where(Category.is_archived.is_(False)).order_by(Category.sort_order.asc())).all()
    return templates.TemplateResponse("admin/pages/new_from_template.html", {"request": request, "categories": categories, "templates": load_page_templates()})


@router.post("/create")
def create_page(
    category_id: int = Form(...),
    title: str = Form(""),
    slug: str = Form(""),
    description: str = Form(""),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    template_key: str = Form(""),
    schedule_kind: str = Form("none"),
    schedule_time: str = Form("07:00"),
    schedule_weekdays: list[str] = Form(default=[]),
    schedule_month_day: str = Form("1"),
    schedule_custom_cron: str = Form("0 7 * * *"),
    db: Session = Depends(get_db),
):
    ok, msg, schedule = build_cron_from_schedule_form(schedule_kind, schedule_time, schedule_weekdays, schedule_month_day, schedule_custom_cron)
    if not ok:
        return RedirectResponse(f"/admin/pages/new?msg={quote_plus(msg)}", status_code=303)

    if template_key:
        page = create_page_from_template(db, category_id, title, slug, template_key)
        page.schedule_enabled = schedule["enabled"]
        page.schedule_kind = schedule["kind"]
        page.schedule_cron = schedule["cron"]
        page.schedule_meta_json = json.dumps(schedule["meta"], ensure_ascii=False)
        db.commit()
        return RedirectResponse(f"/admin/pages/{page.id}", status_code=303)

    if not slug:
        slug = (title or "page").strip().lower().replace(" ", "-")
    base_slug = slug
    idx = 1
    while db.scalars(select(ReportPage).where(ReportPage.slug == slug)).first():
        idx += 1
        slug = f"{base_slug}-{idx}"
    db.add(
        ReportPage(
            category_id=category_id,
            title=title,
            slug=slug,
            description=description,
            sort_order=sort_order,
            is_active=is_active,
            schedule_enabled=schedule["enabled"],
            schedule_cron=schedule["cron"],
            schedule_kind=schedule["kind"],
            schedule_meta_json=json.dumps(schedule["meta"], ensure_ascii=False),
        )
    )
    db.commit()
    return RedirectResponse("/admin/pages", status_code=303)


@router.post("/{page_id}/clone")
def clone_page_endpoint(page_id: int, db: Session = Depends(get_db)):
    p = clone_page(db, page_id)
    return RedirectResponse(f"/admin/pages/{p.id}", status_code=303)


@router.post("/{page_id}/update")
def update_page(
    page_id: int,
    category_id: int = Form(...),
    title: str = Form(""),
    slug: str = Form(""),
    description: str = Form(""),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    schedule_kind: str = Form("none"),
    schedule_time: str = Form("07:00"),
    schedule_weekdays: list[str] = Form(default=[]),
    schedule_month_day: str = Form("1"),
    schedule_custom_cron: str = Form("0 7 * * *"),
    db: Session = Depends(get_db),
):
    p = db.get(ReportPage, page_id)
    if not p:
        raise HTTPException(status_code=404)
    ok, msg, schedule = build_cron_from_schedule_form(schedule_kind, schedule_time, schedule_weekdays, schedule_month_day, schedule_custom_cron)
    if not ok:
        return RedirectResponse(f"/admin/pages/{page_id}?msg={quote_plus(msg)}", status_code=303)

    p.category_id = category_id
    p.title = title
    p.slug = slug or p.slug or (title or "page").strip().lower().replace(" ", "-")
    p.description = description
    p.sort_order = sort_order
    p.is_active = is_active
    p.schedule_enabled = schedule["enabled"]
    p.schedule_kind = schedule["kind"]
    p.schedule_cron = schedule["cron"]
    p.schedule_meta_json = json.dumps(schedule["meta"], ensure_ascii=False)
    db.commit()
    return RedirectResponse(f"/admin/pages/{page_id}", status_code=303)


@router.post("/{page_id}/archive")
def archive_page(page_id: int, archive: bool = Form(True), db: Session = Depends(get_db)):
    p = db.get(ReportPage, page_id)
    if not p:
        raise HTTPException(status_code=404)
    set_archive_state(p, archive)
    db.commit()
    return RedirectResponse(f"/admin/pages/{page_id}", status_code=303)


@router.post("/{page_id}/delete")
def delete_page(page_id: int, db: Session = Depends(get_db)):
    action, msg = safe_delete_or_archive_page(db, page_id)
    return RedirectResponse(f"/admin/pages?msg={quote_plus(f'[{action}] {msg}')}", status_code=303)


@router.get("/{page_id}", response_class=HTMLResponse)
def page_detail(page_id: int, request: Request, msg: str | None = Query(default=None), db: Session = Depends(get_db)):
    page = db.get(ReportPage, page_id)
    if not page:
        raise HTTPException(status_code=404)
    blocks = db.scalars(select(ReportBlock).where(ReportBlock.page_id == page_id).order_by(ReportBlock.sort_order.asc(), ReportBlock.id.asc())).all()
    latest_map = {b.id: block_latest_run(db, b.id) for b in blocks}
    snapshots = get_snapshots_for_page(db, page_id, 10)
    page_schedule = describe_schedule(page.schedule_enabled, page.schedule_kind, page.schedule_cron, page.schedule_meta_json)
    recent_runs = db.scalars(select(RunHistory).where(RunHistory.page_id == page_id).order_by(RunHistory.started_at.desc()).limit(8)).all()
    return templates.TemplateResponse(
        "admin/page_detail.html",
        {
            "request": request,
            "page": page,
            "blocks": blocks,
            "latest_map": latest_map,
            "page_latest": page_latest_run(db, page_id),
            "latest_snapshot": get_latest_snapshot_for_page(db, page_id),
            "snapshots": snapshots,
            "message": msg,
            "schedule": _schedule_form_from_page(page),
            "page_schedule": page_schedule,
            "recent_runs": recent_runs,
        },
    )


@router.post("/{page_id}/run")
def run_page_endpoint(page_id: int, common_params_json: str = Form("{}"), db: Session = Depends(get_db)):
    try:
        common_params = json.loads(common_params_json or "{}")
        if not isinstance(common_params, dict):
            common_params = {}
    except Exception:
        common_params = {}
    snap = run_page_and_create_snapshot(db, page_id, run_type="manual", trigger_source="admin", run_params=common_params)
    msg = quote_plus(f"스냅샷 생성 완료: #{snap.id} / {snap.status}")
    return RedirectResponse(f"/admin/pages/{page_id}?msg={msg}", status_code=303)
