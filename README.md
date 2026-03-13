# 스케줄형 리포트 관리자/조회 포털 (3단계: 페이지 공식 스냅샷)

이 프로젝트는 관리자(/admin)가 리포트를 실행/스케줄링하고,
사용자(/view)는 **페이지 단위 공식 스냅샷**을 읽기 전용으로 조회하는 시스템입니다.

## 1. 역할 분리
- **관리자 `/admin/*`**
  - 카테고리/페이지/블록 등록 및 수정
  - 수동 실행, 스케줄 관리
  - 실행 로그/스냅샷 관리
- **사용자 `/view/*`**
  - 저장된 스냅샷 조회 전용
  - 실행/수정/스케줄 기능 없음
  - 내부 코드/설정/traceback 전체 노출 금지

## 2. 페이지 스냅샷 개념
기존 블록별 RunHistory 로그와 별도로, 사용자 공식 조회용 구조를 추가했습니다.

- `PageSnapshot`: 페이지 1회 실행 결과 묶음
- `BlockSnapshot`: 해당 스냅샷의 블록별 결과
- `SnapshotAttachment`: 블록 스냅샷 첨부

왜 필요한가?
- 사용자 화면에서 블록 결과를 시점별로 섞어보지 않고,
  **동일 실행 시점의 일관된 페이지 결과**를 보장하기 위해서입니다.

## 3. 실행 저장 정책
- 페이지 전체 실행(관리자/스케줄러) 시 `PageSnapshot` 1건 생성
- 활성 python/sql 블록을 sort_order 순으로 실행
- 실패해도 다음 블록 계속 실행
- 결과를 `BlockSnapshot`으로 저장
- 상태 계산:
  - 전부 success: `success`
  - success+failed 혼재: `partial_failed`
  - 전부 failed: `failed`

`RunHistory`는 내부 기술 로그 용도로 유지됩니다.

## 4. 사용자 조회 방식 (/view)
지원 URL:
- `/view`
- `/view/{category_slug}`
- `/view/{category_slug}/{page_slug}`
- `/view/{category_slug}/{page_slug}?snapshot_id=123`
- `/view/{category_slug}/{page_slug}?snapshot_date=2026-03-13`
- `/view/{category_slug}/{page_slug}/print?snapshot_id=123`

조회 규칙:
- 기본: 최신 published 스냅샷
- 특정 snapshot_id/date 선택 가능
- 블록 렌더링은 선택 스냅샷의 `BlockSnapshot`만 사용
- 스냅샷이 없으면 임시 fallback(기존 RunHistory 기반)으로 표시

## 5. 스냅샷 비교(변경 여부)
페이지 상세에서 선택한 스냅샷 기준으로 직전 스냅샷과 비교합니다.
- 기준: summary hash, content hash, 첨부 개수
- 결과: `변경 있음` / `동일` / `이전 결과 없음`

## 6. 인쇄/활용 기능
- 사용자 페이지 인쇄용 URL 제공 (`/print`)
- 블록 카드에 내용 복사 버튼 제공(content_text 기준)
- 첨부 다운로드 버튼 제공
- 긴 HTML 표는 가로 스크롤

## 7. 페이지 단위 스케줄 권장 이유
- 사용자 공식 결과는 페이지 스냅샷 단위로 제공되므로,
  페이지 단위 스케줄이 결과 일관성/추적성에 유리합니다.
- 블록 단위 스케줄은 하위 호환으로 유지하지만 사용자 조회 기준은 스냅샷입니다.

## 8. Windows CMD 실행
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

## 9. URL
- 관리자: `http://127.0.0.1:8000/admin`
- 사용자 홈: `http://127.0.0.1:8000/view`

## 10. 환경변수
- `APP_HOST`, `APP_PORT`
- `ORACLE_USER`, `ORACLE_PASSWORD`
- `DEFAULT_PYTHON_TIMEOUT_SEC`

CMD 예시:
```cmd
set ORACLE_USER=your_user
set ORACLE_PASSWORD=your_password
python -m app.main
```

## 11. Python/SQL 블록 규격
Python 러너 인식 순서:
1. `main(env)` 반환 dict
2. 전역 `result` dict
3. 전역 `RESULT_HTML`

`{'html': ...}`는 `content_html`로 자동 매핑.

SQL 블록:
- `source_code_text`를 SQL 원문으로 사용
- 환경변수 user/pw 사용
- 결과 HTML 저장 + SQL/CSV 첨부 저장

## 12. 주의사항
- 사용자 화면에서 코드 실행/수정/스케줄 기능은 제공하지 않습니다.
- 로그인/권한/React/Docker는 범위 외입니다.
