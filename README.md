# 코드 등록형 리포트 포털 (2단계 확장)

FastAPI + Jinja2 + SQLite 기반의 Windows 로컬 실행용 포털입니다. 카테고리/페이지/블록을 등록하고 Python/SQL/Markdown 블록을 실행하여 결과/첨부파일/이력을 한 화면에서 확인할 수 있습니다.

## 1) 요구 환경
- Windows 10/11
- Python 3.11+
- (선택) Oracle Instant Client (Oracle SQL 실행 시)

## 2) 설치/실행 (Windows CMD)
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

접속 URL: `http://127.0.0.1:8000`

## 3) 환경변수
`.env.example`
- `APP_HOST`, `APP_PORT`
- `ORACLE_USER`, `ORACLE_PASSWORD`
- `DEFAULT_PYTHON_TIMEOUT_SEC`

CMD에서 즉시 설정 예시:
```cmd
set ORACLE_USER=my_user
set ORACLE_PASSWORD=my_password
python -m app.main
```

## 4) 페이지 전체 실행 방식
- 페이지 상단 **페이지 전체 실행** 버튼 클릭 시:
  - 해당 페이지의 활성 블록 중 `python/sql`만 `sort_order` 순서로 실행
  - markdown 블록은 실행 대상 제외
  - 블록별로 개별 `RunHistory` 저장
  - 실패해도 다음 블록 계속 실행
  - 실행 후 `총/성공/실패` 요약 메시지를 페이지 상단에 표시

## 5) 블록 카드 화면 설명
페이지 상세 화면에서 블록이 카드 형태로 표시됩니다.
- 카드 상단: 블록명, 타입 배지, 최신 상태(success/failed/never-run), 마지막 실행시각, 소요시간
- 카드 액션: 실행 / 이력 보기 / 접기-펼치기 / 수정 / 삭제
- 카드 본문:
  - markdown: 렌더링된 설명/가이드
  - python/sql: 최신 선호 결과(성공 우선, 없으면 실패) 출력
  - 오류 발생 시 빨간 에러 박스 표시
  - 첨부파일 목록 및 다운로드 버튼 제공

## 6) 실행 이력 확인 방법
- 좌측 메뉴 **실행 이력** 진입: `/runs`
- 필터: 페이지/블록/상태(success/failed)/limit
- 컬럼: 실행시각, 페이지명, 블록명, run_type, status, duration, summary, 상세
- 상세 화면(`/runs/{id}`): HTML 미리보기, 텍스트, 오류, 첨부, 다시 실행 버튼

## 7) 첨부 다운로드 방식
- 첨부는 블록 카드 및 실행 상세 화면에서 표시
- 다운로드 URL: `/attachments/{attachment_id}/download`
- SQL 블록은 성공 시 기본적으로:
  - `query.sql` (원본 SQL)
  - `result.csv` (결과 CSV)

## 8) Markdown 블록 사용법
- markdown 블록은 보고서 설명/주의사항/운영 메모 용도로 사용
- 제목/목록/강조 등 기본 문법 렌더링 지원

## 9) Python / SQL 결과 표시 규칙
- 결과 선택 우선순위(블록 카드):
  1) 최신 success
  2) 없으면 최신 failed
  3) 없으면 "아직 실행 결과 없음"
- 렌더링 우선순위:
  - `content_html` 우선
  - 없으면 `content_text`를 `<pre>`로 출력
- `summary`는 카드 상단 요약 줄로 표시

## 10) Python 블록 등록 규격
러너는 다음 순서로 결과를 인식합니다.
1. `main(env)` 반환 dict
2. 전역 `result` dict
3. 전역 `RESULT_HTML`

인식 키: `summary`, `artifact_type`, `content_html`, `content_text`, `attachments`

추가 호환:
- `{'html': '<...>'}`만 반환해도 `content_html`로 자동 매핑
- subprocess 격리 실행
- 예외 시 traceback 저장

## 11) SQL 블록 등록 규격
`block_type=sql` + `source_code_text` SQL 실행

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

## 12) 스케줄러
- APScheduler 사용
- 앱 시작 시 `schedule_enabled=true` 블록 자동 등록
- 5필드 cron(`minute hour day month day_of_week`) 지원
- 예: `0 7 * * *` (매일 07:00)

## 13) 샘플 데이터
초기 1회 자동 생성:
- 카테고리 2개(영업/운영)
- 페이지 3개
- markdown/python/sql 블록 샘플 다수

## 14) 주의사항
- 인증/권한/배포/멀티유저는 범위 외
- 내부 관리자 입력 전제로 `content_html`은 신뢰 콘텐츠로 렌더링
- Oracle 접속은 네트워크/권한/Instant Client 설치 상태에 따라 달라집니다.
