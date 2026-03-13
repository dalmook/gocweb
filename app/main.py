from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import Block, Category, Page
from app.routers import attachments, blocks, categories, home, pages, runs
from app.services.scheduler import start_scheduler, stop_scheduler


def load_dotenv_file() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


load_dotenv_file()

app = FastAPI(title="Code Register Report Portal")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    seed_sample_data()
    start_scheduler()


@app.on_event("shutdown")
def shutdown_event() -> None:
    stop_scheduler()


@app.exception_handler(Exception)
async def error_handler(request: Request, exc: Exception):
    return templates.TemplateResponse("error.html", {"request": request, "error": str(exc)}, status_code=500)


app.include_router(home.router)
app.include_router(categories.router)
app.include_router(pages.router)
app.include_router(blocks.router)
app.include_router(runs.router)
app.include_router(attachments.router)


def seed_sample_data() -> None:
    db = SessionLocal()
    try:
        exists = db.scalar(select(Category.id).limit(1))
        if exists:
            return

        sales = Category(name="영업", slug="sales", sort_order=1, is_active=True)
        ops = Category(name="운영", slug="ops", sort_order=2, is_active=True)
        db.add_all([sales, ops])
        db.flush()

        page_shipping = Page(
            category_id=sales.id,
            title="일일 출하 현황",
            slug="daily-shipping",
            description="출하 요약 및 SQL/Python 실행 결과를 한 화면에서 확인합니다.",
            sort_order=1,
            is_active=True,
        )
        page_order = Page(
            category_id=sales.id,
            title="주문 추이 점검",
            slug="order-trend",
            description="주문 추이와 특이사항 설명 페이지",
            sort_order=2,
            is_active=True,
        )
        page_ops = Page(
            category_id=ops.id,
            title="운영 모니터링",
            slug="ops-monitoring",
            description="운영 지표 점검 페이지",
            sort_order=1,
            is_active=True,
        )
        db.add_all([page_shipping, page_order, page_ops])
        db.flush()

        blocks_data = [
            Block(
                page_id=page_shipping.id,
                title="보고서 안내",
                block_type="markdown",
                source_code_text="""# 일일 출하 현황\n- 매일 오전 자동 실행\n- 실패 블록은 빨간 배지로 표시\n- SQL/Python 첨부를 카드에서 바로 다운로드 가능""",
                sort_order=1,
                is_active=True,
            ),
            Block(
                page_id=page_shipping.id,
                title="Python 샘플",
                block_type="python",
                source_code_text=Path("samples/sample_python_block.py").read_text(encoding="utf-8"),
                config_json='{"timeout_sec": 300}',
                schedule_enabled=True,
                schedule_cron="0 7 * * *",
                sort_order=2,
                is_active=True,
            ),
            Block(
                page_id=page_shipping.id,
                title="SQL 샘플 자리",
                block_type="sql",
                source_code_text=Path("samples/sample_query.sql").read_text(encoding="utf-8"),
                config_json='{"dsn":"", "user_env":"ORACLE_USER", "pw_env":"ORACLE_PASSWORD", "thick_mode":false, "oracle_client_lib_dir":"C:\\\\instantclient", "max_rows_preview": 200}',
                sort_order=3,
                is_active=True,
            ),
            Block(
                page_id=page_order.id,
                title="주문 트렌드 안내",
                block_type="markdown",
                source_code_text="## 확인 기준\n1. 전일 대비 증감\n2. 상위 고객 변동\n3. 비정상 주문 유무",
                sort_order=1,
                is_active=True,
            ),
            Block(
                page_id=page_order.id,
                title="주문 추이 Python",
                block_type="python",
                source_code_text=Path("samples/sample_python_block.py").read_text(encoding="utf-8"),
                config_json='{"timeout_sec": 120}',
                sort_order=2,
                is_active=True,
            ),
            Block(
                page_id=page_ops.id,
                title="운영 메모",
                block_type="markdown",
                source_code_text="### 운영 체크리스트\n- [ ] 장애 티켓\n- [ ] 배치 지연\n- [ ] 데이터 적재 상태",
                sort_order=1,
                is_active=True,
            ),
        ]
        db.add_all(blocks_data)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    load_dotenv_file()
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=True)
