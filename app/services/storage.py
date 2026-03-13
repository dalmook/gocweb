from __future__ import annotations

import mimetypes
from pathlib import Path

from app.db import ARTIFACTS_DIR


def ensure_run_dir(run_id: int) -> Path:
    run_dir = ARTIFACTS_DIR / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_text_artifact(run_id: int, filename: str, content: str) -> Path:
    target = ensure_run_dir(run_id) / filename
    target.write_text(content, encoding="utf-8")
    return target


def file_meta(path: Path) -> dict:
    mime, _ = mimetypes.guess_type(path.name)
    return {
        "file_name": path.name,
        "stored_path": str(path),
        "mime_type": mime or "application/octet-stream",
        "file_size": path.stat().st_size,
    }
