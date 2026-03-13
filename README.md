# 스케줄형 리포트 관리자/조회 포털 (4단계 운영형)

이 프로젝트는 **관리자(/admin)** 가 리포트를 빠르게 생성/복제/실행/스케줄링하고,
**사용자(/view)** 는 저장된 스냅샷만 읽는 조회 전용 포털입니다.

## 1) 관리자/사용자 역할 차이
- 관리자 `/admin/*`
  - 페이지/블록 생성, 템플릿 생성, 복제, 파라미터 실행, 시험 실행, 스케줄, 스냅샷/로그/정리
- 사용자 `/view/*`
  - 저장된 `PageSnapshot` 조회만 수행
  - 코드 수정/실행/스케줄 기능 없음

## 2) 페이지 스냅샷 개념
- `PageSnapshot`: 페이지 1회 실행 공식 결과
- `BlockSnapshot`: 해당 실행본의 블록별 결과
- `SnapshotAttachment`: 블록 스냅샷 첨부

사용자 포털은 블록 최신 조합이 아니라 **선택된 스냅샷 한 건** 기준으로 화면을 구성합니다.

## 3) 4단계 핵심 운영 기능
- 페이지 템플릿 생성 (`/admin/pages/new`, `samples/page_templates/*.json`)
- 페이지 복제 (`/admin/pages/{id}`에서 복제)
- 블록 복제 (`/admin/blocks`, `/admin/blocks/{id}/edit`)
- 블록 파라미터 실행
  - `params_schema_json`
  - `default_params_json`
  - 수동 실행/시험 실행에서 run params 입력
- 페이지 전체 실행 공통 파라미터
  - 페이지 실행 시 JSON 입력
  - 스냅샷 `run_params_json`에 저장
- 시험 실행(PreviewRun)
  - 블록 편집 화면에서 임시 실행 결과 확인
  - 정식 스냅샷과 분리
- JSON/cron 검증
- 실패 강조 대시보드 + 실패 스냅샷 점검
- 유지보수 화면(`/admin/maintenance`)
  - 페이지별 최근 N개 스냅샷 유지
  - temp 정리

## 4) SQL bind / Python params 규칙
### Python
`main(env)` 또는 `result/RESULT_HTML` 규격 유지.
실행 파라미터는 `env["params"]`로 전달됩니다.

### SQL
SQL named bind 지원:
```sql
SELECT :target_month AS target_month, :site_id AS site_id FROM dual
```
실행 시 파라미터 병합 우선순위:
1. 실행 입력 params
2. `default_params_json`
3. `config_json.default_params` (있을 때)

## 5) Windows CMD 실행
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

## 6) URL
- 관리자 홈: `http://127.0.0.1:8000/admin`
- 사용자 홈: `http://127.0.0.1:8000/view`
- 사용자 페이지: `/view/{category_slug}/{page_slug}`
- 사용자 스냅샷 선택: `?snapshot_id=123` 또는 `?snapshot_date=YYYY-MM-DD`

## 7) 페이지 템플릿 사용법
1. `/admin/pages/new` 이동
2. 템플릿 선택 (`daily_sales_report`, `production_status_report`, `markdown_notice_page`)
3. 제목/slug 보정 후 생성
4. 페이지 상세에서 실행/수정

## 8) 페이지/블록 복제 방법
- 페이지 복제: `/admin/pages/{id}` → 복제 버튼
  - 제목 `- 복사본`
  - slug 자동 충돌 회피
  - 페이지/블록 스케줄 기본 OFF
- 블록 복제: `/admin/blocks/{id}/edit` 또는 목록
  - params schema/default/config/code 포함 복사

## 9) 시험 실행(Preview)
- `/admin/blocks/{id}/edit`
- `run_params_json` 입력 후 **시험 실행**
- 화면 하단 최근 Preview 결과 확인
- Preview는 정식 스냅샷 publish에 포함되지 않음

## 10) 실패 확인/재실행 흐름
1. `/admin` 대시보드 실패 영역 확인
2. `/admin/snapshots/{id}` 이동
3. 실패 블록 traceback/오류 상세 확인
4. 페이지 재실행으로 새 스냅샷 생성

## 11) 보관 정책/정리
- `/admin/maintenance`
- 페이지별 유지 스냅샷 수(`keep_per_page`)
- temp 폴더 정리 기준 일수(`temp_days`)

## 12) 환경변수 (CMD)
```cmd
set ORACLE_USER=your_user
set ORACLE_PASSWORD=your_password
python -m app.main
```

## 13) 주의사항
- 사용자 화면에서 관리자 기능 노출/실행 금지
- 로그인/권한관리, React, Docker, 외부 실알림 연동은 범위 외
