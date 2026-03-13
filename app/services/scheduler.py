from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ReportPage
from app.services.run_service import run_page_and_create_snapshot

scheduler = BackgroundScheduler()


def _parse_cron_5(expr: str) -> CronTrigger:
    parts = (expr or "").split()
    if len(parts) != 5:
        return CronTrigger(hour=7, minute=0)
    minute, hour, day, month, dow = parts
    return CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=dow)


def _run_page_job(page_id: int) -> None:
    db = SessionLocal()
    try:
        run_page_and_create_snapshot(db, page_id, run_type="scheduled", trigger_source="scheduler")
    except Exception:
        pass
    finally:
        db.close()


def register_jobs() -> None:
    scheduler.remove_all_jobs()
    db = SessionLocal()
    try:
        pages = db.scalars(
            select(ReportPage).where(ReportPage.schedule_enabled.is_(True), ReportPage.is_active.is_(True), ReportPage.is_archived.is_(False))
        ).all()
        for p in pages:
            scheduler.add_job(
                _run_page_job,
                trigger=_parse_cron_5(p.schedule_cron),
                id=f"page-{p.id}",
                replace_existing=True,
                kwargs={"page_id": p.id},
            )

    finally:
        db.close()


def start_scheduler() -> None:
    if not scheduler.running:
        register_jobs()
        scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
