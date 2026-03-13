from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


CHILD_TEMPLATE = r'''
import importlib.util
import json
import traceback
from pathlib import Path

code_path = Path(r"{code_path}")
output_path = Path(r"{output_path}")
config = json.loads(r"""{config_json}""")

payload = {{
    "status": "failed",
    "summary": "",
    "content_html": "",
    "content_text": "",
    "error_text": "",
    "attachments": []
}}

try:
    spec = importlib.util.spec_from_file_location("user_block_module", str(code_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = None
    if hasattr(module, "main") and callable(module.main):
        try:
            result = module.main(config)
        except TypeError:
            result = module.main({{}})

    if isinstance(result, dict):
        payload.update(result)
    elif isinstance(getattr(module, "result", None), dict):
        payload.update(module.result)
    elif getattr(module, "RESULT_HTML", None):
        payload["content_html"] = str(module.RESULT_HTML)

    if isinstance(payload.get("html"), str) and not payload.get("content_html"):
        payload["content_html"] = payload["html"]

    if not payload.get("summary"):
        payload["summary"] = "Python block executed"
    payload["status"] = "success"
except Exception:
    payload["status"] = "failed"
    payload["summary"] = "Python block failed"
    payload["error_text"] = traceback.format_exc()

output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
'''


def run_python_block(source_code: str, env: dict, timeout_sec: int = 300) -> dict:
    with tempfile.TemporaryDirectory() as td:
        code_path = Path(td) / "block_runner.py"
        output_path = Path(td) / "result.json"
        code_path.write_text(source_code, encoding="utf-8")

        config_json = json.dumps(env, ensure_ascii=False)
        child_code = textwrap.dedent(
            CHILD_TEMPLATE.format(
                code_path=str(code_path),
                output_path=str(output_path),
                config_json=config_json,
            )
        )
        child_script = Path(td) / "child_exec.py"
        child_script.write_text(child_code, encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(child_script)],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env={**os.environ},
        )

        if not output_path.exists():
            return {
                "status": "failed",
                "summary": "Python runner failed",
                "content_html": "",
                "content_text": proc.stdout,
                "error_text": proc.stderr or "No output produced",
                "attachments": [],
            }

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        if payload.get("status") == "success" and proc.stderr:
            payload["content_text"] = (payload.get("content_text") or "") + f"\n{proc.stderr}"
        return payload
