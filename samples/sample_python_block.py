# -*- coding: utf-8 -*-
from datetime import datetime


def main(env):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    html = f"<h3>Python 샘플 실행</h3><p>실행 시각: {now}</p>"
    return {"html": html, "summary": "샘플 Python 실행 완료"}


out = main({})
RESULT_HTML = out.get('html', '')
result = {
    "summary": "출하 현황 HTML 생성 완료",
    "artifact_type": "html",
    "content_html": RESULT_HTML,
    "content_text": "HTML result generated",
}

if __name__ == '__main__':
    with open('output.html', 'w', encoding='utf-8') as f:
        f.write(RESULT_HTML)
    print('saved: output.html')
