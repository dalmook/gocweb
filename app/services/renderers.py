from __future__ import annotations

import html


def markdown_to_html(text: str) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            out.append(f"<h3>{html.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            out.append(f"<h2>{html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            out.append(f"<h1>{html.escape(stripped[2:])}</h1>")
        else:
            out.append(f"<p>{html.escape(line)}</p>")
    return "\n".join(out)


def text_to_pre(text: str) -> str:
    return f"<pre>{html.escape(text or '')}</pre>"
