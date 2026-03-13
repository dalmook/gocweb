# 스케줄형 리포트 관리자/조회 포털 (2단계)

이 프로젝트는 **관리자(/admin)** 가 Python/SQL 리포트를 등록·실행·스케줄링하고,
**사용자(/view)** 는 저장된 실행 결과만 읽는 **읽기 전용 포털**입니다.

## 핵심 분리 원칙
- `/admin/*`: 등록/수정/실행/스케줄/운영 이력
- `/view/*`: 저장된 RunHistory 조회 전용 (실행/수정 기능 없음)
- 사용자 화면에서 Python/SQL 실시간 실행 금지

## 기술 스택
- Python 3.11+
- FastAPI, Jinja2, SQLAlchemy, APScheduler
- SQLite, pandas, oracledb

## 폴더 구조
```text
app/
  main.py
  db.py
  models.py
  init_data.py
  services/
    run_service.py        # 관리자 실행 서비스
    view_service.py       # 사용자 조회 서비스
    runner_python.py
    runner_sql.py
    scheduler.py
    storage.py
  routers/
    admin_*.py
    view_portal.py
  templates/
    admin/
    view/
    shared/
  static/
```

## Windows CMD 실행
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

## URL
- 관리자: `http://127.0.0.1:8000/admin`
- 사용자 홈: `http://127.0.0.1:8000/view`
- 사용자 카테고리: `/view/{category_slug}`
- 사용자 페이지: `/view/{category_slug}/{page_slug}`

## 관리자/사용자 흐름
1. 관리자 화면에서 블록 등록/수정
2. 관리자 수동 실행 또는 스케줄러 실행
3. 결과는 `RunHistory`/`Attachment`에 저장
4. 사용자 화면은 저장 결과를 조회만 수행

## 사용자 조회 방식 (2단계)
- 기본: 블록별 최신 success 우선
- 실패만 있으면 최신 failed 표시
- 실행 이력 선택(`run_id`) 시 해당 시점 이전 가장 가까운 결과 표시
- 첨부파일 다운로드 지원(.sql/.csv/기타 attachments)
- 사용자 화면에서 내부 운영정보 노출 금지:
  - source_code_text, config_json, schedule_cron, traceback 전체

## 스케줄 동작
- `schedule_enabled=true` 블록을 앱 시작 시 등록
- cron 5필드 지원 (`minute hour day month day_of_week`)
- 블록 단위 scheduled 실행

## Python 블록 규격
결과 인식 순서:
1. `main(env)` 반환 dict
2. 전역 `result` dict
3. 전역 `RESULT_HTML`

`{'html': ...}` 는 `content_html`로 자동 매핑

## SQL 블록 규격
`source_code_text`를 SQL 원문으로 사용
- user/pw는 환경변수(`ORACLE_USER`, `ORACLE_PASSWORD`)에서 로드
- thick mode 옵션 지원
- HTML preview 저장
- SQL/CSV 파일 첨부 저장

## 환경변수 예시 (CMD)
```cmd
set ORACLE_USER=your_user
set ORACLE_PASSWORD=your_password
python -m app.main
```

## 주의사항
- 로그인/권한관리, React, Docker는 범위 외
- 사용자 포털은 조회 전용이며 실행/수정 기능을 제공하지 않음
