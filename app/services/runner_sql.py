from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

try:
    import oracledb
except Exception:  # pragma: no cover
    oracledb = None


def run_sql_block(source_sql: str, config: dict, output_dir: Path, params: dict | None = None) -> dict:
    if not source_sql.strip():
        return {"status": "failed", "summary": "SQL empty", "error_text": "source SQL is empty"}
    if oracledb is None:
        return {"status": "failed", "summary": "oracledb import failed", "error_text": "oracledb package is not available"}

    dsn = config.get("dsn", "")
    user = os.getenv(config.get("user_env", "ORACLE_USER"), "")
    pw = os.getenv(config.get("pw_env", "ORACLE_PASSWORD"), "")

    if config.get("thick_mode") and config.get("oracle_client_lib_dir"):
        try:
            oracledb.init_oracle_client(lib_dir=config.get("oracle_client_lib_dir"))
        except Exception:
            pass

    if not all([dsn, user, pw]):
        return {
            "status": "failed",
            "summary": "Missing DB credentials",
            "error_text": "dsn/user/password(env) is required",
        }

    with oracledb.connect(user=user, password=pw, dsn=dsn) as conn:
        df = pd.read_sql(source_sql, conn, params=params or {})

    max_rows = int(config.get("max_rows_preview", 200))
    preview = df.head(max_rows)
    html = preview.to_html(index=False, classes="sql-table")

    sql_file = output_dir / "query.sql"
    csv_file = output_dir / "result.csv"
    sql_file.write_text(source_sql, encoding="utf-8")
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")

    return {
        "status": "success",
        "summary": f"SQL executed ({len(df)} rows)",
        "content_html": html,
        "content_text": preview.to_string(index=False),
        "error_text": "",
        "attachments": [str(sql_file), str(csv_file)],
    }
