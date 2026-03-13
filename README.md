# 스케줄형 리포트 관리자 포털 (1단계)

이 프로젝트는 **관리자가 Python/SQL 리포트를 등록/수정/실행/스케줄링**하고, 실행 결과를 저장하는 로컬 Windows PC용 포털입니다.

핵심 원칙:
- 관리자 영역: `/admin/*`
- 사용자 영역(placeholder): `/view/*`
- 사용자 영역은 직접 실행/수정 기능 없이, 향후 저장 결과 조회 전용으로 확장

## 기술 스택
- Python 3.11+
- FastAPI
- Jinja2
- SQLAlchemy
- APScheduler
- pandas
- oracledb
- SQLite

## 폴더 구조
```text
app/
  main.py
  db.py
  models.py
  init_data.py
  services/
    runner_python.py
    runner_sql.py
    scheduler.py
    run_service.py
    storage.py
  routers/
    admin_home.py
    admin_categories.py
    admin_pages.py
    admin_blocks.py
    admin_runs.py
    view_portal.py
  templates/
    admin/
    view/
    shared/
  static/
data/
  app.db
  artifacts/
  uploads/
  temp/
samples/
requirements.txt
.env.example
README.md
```

## Windows CMD 실행 방법
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

## URL
- 관리자 포털: `http://127.0.0.1:8000/admin`
- 사용자 포털 placeholder: `http://127.0.0.1:8000/view`

## 환경변수
`.env.example` 주요 항목:
- `APP_HOST`, `APP_PORT`
- `ORACLE_USER`, `ORACLE_PASSWORD`
- `DEFAULT_PYTHON_TIMEOUT_SEC`

CMD 설정 예시:
```cmd
set ORACLE_USER=your_user
set ORACLE_PASSWORD=your_password
python -m app.main
```

## 관리자 기능 (1단계)
- 카테고리 CRUD (`/admin/categories`)
- 리포트 페이지 CRUD (`/admin/pages`)
- 블록 CRUD 및 편집 (`/admin/blocks`, `/admin/blocks/{id}/edit`)
- 블록 수동 실행
- 페이지 전체 실행 (활성 python/sql 블록만 sort_order 순)
- 실행 이력 목록/상세 (`/admin/runs`)
- 스케줄 사용여부/cron 관리 (블록 단위)

## 실행 구조
- 관리자 또는 스케줄러가 실행
- 실행 결과는 `RunHistory` 및 `Attachment`에 저장
- 사용자 포털은 향후 이 저장 결과만 읽도록 설계
- markdown 블록은 설명용이며 실행 대상 제외

## Python 블록 규격
러너 인식 순서:
1. `main(env)` 반환 dict
2. 전역 `result` dict
3. 전역 `RESULT_HTML`

우선 키:
- `summary`
- `artifact_type`
- `content_html`
- `content_text`
- `attachments`

추가 호환:
- `{'html': ...}` 반환 시 `content_html` 자동 매핑
- 예외 시 traceback 저장

## SQL 블록 규격
`source_code_text`를 SQL 원문으로 실행

예시 `config_json`:
```json
{
  "dsn": "host:port/service",
  "user_env": "ORACLE_USER",
  "pw_env": "ORACLE_PASSWORD",
  "thick_mode": true,
  "oracle_client_lib_dir": "C:\\instantclient",
  "max_rows_preview": 200
}
```

동작:
- user/pw는 환경변수에서 읽음
- thick_mode + lib_dir 설정 시 `oracledb.init_oracle_client()` 시도
- DataFrame HTML preview 저장
- SQL 원문(.sql), CSV(.csv) 아티팩트 저장

## 스케줄 동작
- APScheduler 사용
- 앱 시작 시 `schedule_enabled=true` 블록 등록
- 5필드 cron 지원 (`minute hour day month day_of_week`)
- 예: `0 7 * * *` (매일 오전 7시)

## 샘플 데이터
초기 실행 시 자동 생성:
- 카테고리 2개
- 리포트 페이지 2개
- markdown 1개
- python 1개
- sql 1개

## 주의사항
- 이번 단계는 관리자 운영 포털 중심
- 사용자용 조회 포털은 placeholder만 구현
- 로그인/권한관리/배포/React/Docker는 범위 외
