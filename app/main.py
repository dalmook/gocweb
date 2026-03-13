from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import Block, Category, Page
from app.routers import attachments, blocks, categories, home, pages, runs
from app.services.scheduler import start_scheduler, stop_scheduler



def load_dotenv_file() -> None:
    env_path = Path('.env')
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, val = line.split('=', 1)
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

        c = Category(name="영업", slug="sales", sort_order=1, is_active=True)
        db.add(c)
        db.flush()
        p = Page(
            category_id=c.id,
            title="일일 출하 현황",
            slug="daily-shipping",
            description="Python/SQL/Markdown 블록 실행 예시 페이지",
            sort_order=1,
            is_active=True,
        )
        db.add(p)
        db.flush()
        md = Block(
            page_id=p.id,
            title="설명",
            block_type="markdown",
            source_code_text="# 일일 출하 현황\n샘플 블록입니다.",
            sort_order=1,
            is_active=True,
        )
        py = Block(
            page_id=p.id,
            title="Python 샘플",
            block_type="python",
            source_code_text=Path("samples/sample_python_block.py").read_text(encoding="utf-8"),
            config_json='{"timeout_sec": 300}',
            schedule_enabled=True,
            schedule_cron="0 7 * * *",
            sort_order=2,
            is_active=True,
        )
        sql = Block(
            page_id=p.id,
            title="SQL 샘플 자리",
            block_type="sql",
            source_code_text="SELECT 'sample' AS name, 1 AS value FROM dual",
            config_json='{"dsn":"", "user_env":"ORACLE_USER", "pw_env":"ORACLE_PASSWORD", "thick_mode":false, "oracle_client_lib_dir":"C:\\\\instantclient", "max_rows_preview": 200}',
            sort_order=3,
            is_active=True,
        )
        db.add_all([md, py, sql])
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    load_dotenv_file()
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))
    import uvicorn
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
