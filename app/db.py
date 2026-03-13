from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
UPLOADS_DIR = DATA_DIR / "uploads"
TEMP_DIR = DATA_DIR / "temp"
LOGS_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "app.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

for p in [DATA_DIR, ARTIFACTS_DIR, UPLOADS_DIR, TEMP_DIR, LOGS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_compat_columns() -> None:
    alter_candidates = {
        "report_pages": [
            ("schedule_enabled", "ALTER TABLE report_pages ADD COLUMN schedule_enabled BOOLEAN DEFAULT 0"),
            ("schedule_cron", "ALTER TABLE report_pages ADD COLUMN schedule_cron VARCHAR(50) DEFAULT ''"),
        ],
        "report_blocks": [
            ("params_schema_json", "ALTER TABLE report_blocks ADD COLUMN params_schema_json TEXT DEFAULT '[]'"),
            ("default_params_json", "ALTER TABLE report_blocks ADD COLUMN default_params_json TEXT DEFAULT '{}'"),
        ],
        "page_snapshots": [
            ("run_params_json", "ALTER TABLE page_snapshots ADD COLUMN run_params_json TEXT DEFAULT '{}'"),
        ],
    }
    with engine.begin() as conn:
        for table, columns in alter_candidates.items():
            table_exists = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table}).first()
            if not table_exists:
                continue
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for col, ddl in columns:
                if col not in existing:
                    conn.execute(text(ddl))
