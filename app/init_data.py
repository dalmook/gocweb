from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import ARTIFACTS_DIR
from app.models import Attachment, Category, ReportBlock, ReportPage, RunHistory


def seed_sample_data(db: Session) -> None:
    if db.scalar(select(Category.id).limit(1)):
        return

    sales = Category(name="영업", slug="sales", sort_order=1, is_active=True)
    ops = Category(name="운영", slug="ops", sort_order=2, is_active=True)
    db.add_all([sales, ops])
    db.flush()

    p1 = ReportPage(
        category_id=sales.id,
        title="일일 출하 리포트",
        slug="daily-shipping",
        description="관리자가 실행/운영하는 출하 리포트",
        sort_order=1,
        is_active=True,
    )
    p2 = ReportPage(
        category_id=ops.id,
        title="운영 점검 리포트",
        slug="ops-check",
        description="운영성 점검용 리포트",
        sort_order=1,
        is_active=True,
    )
    db.add_all([p1, p2])
    db.flush()

    b1 = ReportBlock(
        page_id=p1.id,
        title="리포트 안내",
        description="설명 블록",
        block_type="markdown",
        source_code_text="# 일일 출하 리포트\n- 관리자 실행 전용\n- 사용자 포털은 저장 결과만 조회",
        sort_order=1,
        is_active=True,
    )
    b2 = ReportBlock(
        page_id=p1.id,
        title="Python 샘플 블록",
        description="샘플 파이썬 실행",
        block_type="python",
        source_code_text=Path("samples/sample_python_block.py").read_text(encoding="utf-8"),
        config_json='{"timeout_sec": 300}',
        schedule_enabled=True,
        schedule_cron="0 7 * * *",
        sort_order=2,
        is_active=True,
    )
    b3 = ReportBlock(
        page_id=p2.id,
        title="SQL 샘플 블록",
        description="오라클 SQL 샘플",
        block_type="sql",
        source_code_text=Path("samples/sample_query.sql").read_text(encoding="utf-8"),
        config_json='{"dsn":"", "user_env":"ORACLE_USER", "pw_env":"ORACLE_PASSWORD", "thick_mode":false, "oracle_client_lib_dir":"C:\\\\instantclient", "max_rows_preview": 200}',
        sort_order=1,
        is_active=True,
    )
    db.add_all([b1, b2, b3])
    db.flush()

    now = datetime.utcnow()
    py_run = RunHistory(
        page_id=p1.id,
        block_id=b2.id,
        run_type="scheduled",
        status="success",
        summary="샘플 Python 결과 생성",
        content_html="<h3>출하 요약</h3><p>오늘 출하량: 12,340</p>",
        content_text="오늘 출하량: 12340",
        error_text="",
        started_at=now - timedelta(hours=2),
        finished_at=now - timedelta(hours=2) + timedelta(seconds=1),
        duration_ms=1000,
    )
    sql_run = RunHistory(
        page_id=p2.id,
        block_id=b3.id,
        run_type="scheduled",
        status="failed",
        summary="DB 접속 실패",
        content_html="",
        content_text="",
        error_text="ORA-12541: TNS:no listener",
        started_at=now - timedelta(hours=1),
        finished_at=now - timedelta(hours=1) + timedelta(seconds=2),
        duration_ms=2000,
    )
    db.add_all([py_run, sql_run])
    db.flush()

    run_dir = ARTIFACTS_DIR / f"run_{py_run.id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    f1 = run_dir / "summary.txt"
    f1.write_text("출하 요약 첨부 파일", encoding="utf-8")
    db.add(
        Attachment(
            run_history_id=py_run.id,
            file_name=f1.name,
            stored_path=str(f1),
            mime_type="text/plain",
            file_size=f1.stat().st_size,
        )
    )

    db.commit()
