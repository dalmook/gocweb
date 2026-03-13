from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, ReportBlock, ReportPage


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

    db.add_all(
        [
            ReportBlock(
                page_id=p1.id,
                title="리포트 안내",
                description="설명 블록",
                block_type="markdown",
                source_code_text="# 일일 출하 리포트\n- 관리자 실행 전용\n- 사용자 포털은 저장 결과만 조회",
                sort_order=1,
                is_active=True,
            ),
            ReportBlock(
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
            ),
            ReportBlock(
                page_id=p2.id,
                title="SQL 샘플 블록",
                description="오라클 SQL 샘플",
                block_type="sql",
                source_code_text=Path("samples/sample_query.sql").read_text(encoding="utf-8"),
                config_json='{"dsn":"", "user_env":"ORACLE_USER", "pw_env":"ORACLE_PASSWORD", "thick_mode":false, "oracle_client_lib_dir":"C:\\\\instantclient", "max_rows_preview": 200}',
                sort_order=1,
                is_active=True,
            ),
        ]
    )
    db.commit()
