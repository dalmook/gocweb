# 코드 등록형 리포트 포털 (MVP 1차)

FastAPI + Jinja2 + SQLite 기반으로, 카테고리/페이지/블록을 등록하고 Python 또는 SQL 블록을 실행해 결과(HTML/Text)와 첨부파일을 저장/조회하는 로컬 Windows용 1차 버전입니다.

## 1) 요구 환경
- Windows 10/11
- Python 3.11+
- (선택) Oracle Instant Client (SQL 블록 Oracle 접속 시)

## 2) 프로젝트 구조
```
app/
  main.py
  db.py
  models.py
  schemas.py
  services/
    runner_python.py
    runner_sql.py
    scheduler.py
    renderers.py
    storage.py
    executor.py
  routers/
    home.py
    categories.py
    pages.py
    blocks.py
    runs.py
    attachments.py
  templates/
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

## 3) Windows CMD 기준 설치/실행
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

접속 URL:
- http://127.0.0.1:8000

## 4) 초기 DB 생성
- 앱 시작 시 `data\app.db`가 없으면 자동 생성됩니다.
- 테이블도 자동 생성됩니다.

## 5) 샘플 데이터
- 앱 첫 실행 시 샘플 데이터 1세트 자동 생성:
  - 카테고리: 영업
  - 페이지: 일일 출하 현황
  - 블록: markdown / python / sql

## 6) 환경변수 (.env)
`.env.example`의 주요 항목:
- `APP_HOST` / `APP_PORT`: 서버 바인딩 정보
- `ORACLE_USER` / `ORACLE_PASSWORD`: SQL 블록 Oracle 계정
- `DEFAULT_PYTHON_TIMEOUT_SEC`: Python 블록 기본 타임아웃(초)

> 참고: 기본 코드에서는 OS 환경변수를 직접 읽습니다. CMD에서 아래처럼 설정 가능합니다.
```cmd
set ORACLE_USER=your_user
set ORACLE_PASSWORD=your_password
python -m app.main
```

## 7) 주요 화면/기능
1. 메인 화면: 카테고리 목록, 페이지 개수, 최근 실행
2. 카테고리 화면: 생성/수정/삭제, 하위 페이지 목록
3. 페이지 화면: 페이지 정보, 블록 목록, 페이지 전체 실행
4. 블록 편집: python/sql/markdown, 코드/JSON, cron 설정, 수동 실행
5. 실행 결과 화면: 상태/요약/HTML/오류/첨부 다운로드
6. 페이지 결과 화면: 블록 순서 렌더링, 최신 성공 결과 우선 표시

## 8) Python 블록 등록 규격
러너는 아래 우선순위로 결과를 인식합니다.
1. `main(env)` 반환 dict
2. 전역 `result` dict
3. 전역 `RESULT_HTML`

인식 키:
- `summary`
- `artifact_type`
- `content_html`
- `content_text`
- `attachments`

호환 규칙:
- `{'html': '<...>'}`만 반환해도 `content_html`로 자동 매핑
- 실행 예외 발생 시 traceback 저장
- subprocess 기반 실행(기본 타임아웃 300초)

## 9) SQL 블록 등록 규격
`block_type=sql` 블록은 `source_code_text` SQL을 실행합니다.

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
- 환경변수에서 계정 정보 로드
- 결과를 pandas DataFrame으로 받아 미리보기 HTML 저장
- `artifacts`에 SQL 원문(`query.sql`) + CSV(`result.csv`) 저장
- 첨부파일 다운로드 가능

## 10) 스케줄러 (APScheduler)
- 앱 시작 시 `schedule_enabled=true` 블록을 읽어 등록
- 5필드 cron 문자열 지원 (`minute hour day month day_of_week`)
- 예: 매일 오전 7시 → `0 7 * * *`
- 스케줄 실행은 블록 단위로 수행

## 11) Oracle Instant Client 안내
- `thick_mode=true` 사용 시 Instant Client 설치 필요
- `oracle_client_lib_dir`에 설치 경로 지정 (예: `C:\instantclient`)
- 환경에 따라 PATH 추가가 필요할 수 있습니다.

## 12) 주의사항
- 1차 MVP 범위: 인증/권한/배포/멀티유저/버전관리 제외
- `content_html`은 내부 신뢰 코드 결과 기준으로 raw 렌더링(`|safe`)됩니다.
- SQL 실행은 대상 DB 권한/성능에 주의하세요.

## 13) 빠른 테스트
1. 앱 실행 후 샘플 페이지 진입
2. Python 블록 수동 실행
3. 실행 결과/페이지 결과 화면 확인
4. SQL 블록은 Oracle 정보 입력 후 실행
