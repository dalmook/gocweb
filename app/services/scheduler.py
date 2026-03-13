from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ReportBlock
from app.services.run_service import run_block

scheduler = BackgroundScheduler()


def _parse_cron_5(expr: str) -> CronTrigger:
    parts = (expr or "").split()
    if len(parts) != 5:
        return CronTrigger(hour=7, minute=0)
    minute, hour, day, month, dow = parts
    return CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=dow)


def _run_block_job(block_id: int) -> None:
    db = SessionLocal()
    try:
        run_block(db, block_id, run_type="scheduled")
    except Exception:
        pass
    finally:
        db.close()


def register_jobs() -> None:
    scheduler.remove_all_jobs()
    db = SessionLocal()
    try:
        blocks = db.scalars(
            select(ReportBlock).where(ReportBlock.schedule_enabled.is_(True), ReportBlock.is_active.is_(True))
        ).all()
        for block in blocks:
            scheduler.add_job(
                _run_block_job,
                trigger=_parse_cron_5(block.schedule_cron),
                id=f"block-{block.id}",
                replace_existing=True,
                kwargs={"block_id": block.id},
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
