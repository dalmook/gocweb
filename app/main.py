from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import Base, SessionLocal, engine
from app.init_data import seed_sample_data
from app.routers import (
    admin_blocks,
    admin_categories,
    admin_home,
    admin_pages,
    admin_runs,
    attachments,
    view_portal,
)
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

app = FastAPI(title="Scheduled Report Admin Portal")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_sample_data(db)
    finally:
        db.close()
    start_scheduler()


@app.on_event("shutdown")
def shutdown_event() -> None:
    stop_scheduler()


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/admin", status_code=302)


@app.exception_handler(Exception)
async def error_handler(request: Request, exc: Exception):
    return templates.TemplateResponse("shared/error.html", {"request": request, "error": str(exc)}, status_code=500)


app.include_router(admin_home.router)
app.include_router(admin_categories.router)
app.include_router(admin_pages.router)
app.include_router(admin_blocks.router)
app.include_router(admin_runs.router)
app.include_router(attachments.router)
app.include_router(view_portal.router)


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8000"))
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=True)
