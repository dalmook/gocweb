from __future__ import annotations

import html

import markdown as md


def markdown_to_html(text: str) -> str:
    if not text:
        return ""
    return md.markdown(text, extensions=["extra", "sane_lists"])


def text_to_pre(text: str) -> str:
    return f"<pre>{html.escape(text or '')}</pre>"


def run_content_html(run) -> str:
    if not run:
        return "<p>아직 실행 결과 없음</p>"
    if run.content_html:
        return run.content_html
    if run.content_text:
        return text_to_pre(run.content_text)
    return "<p>아직 실행 결과 없음</p>"
