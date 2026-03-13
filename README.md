# 스케줄형 리포트 관리자/조회 포털 (Windows CMD)

FastAPI + Jinja2 + SQLite 기반 포털입니다.
- 관리자: `/admin` (CRUD, 스케줄, 실행, 스냅샷/유지보수)
- 사용자: `/view` (published snapshot 조회 전용)

## 핵심 변경사항 (이번 버전)

### 1) 삭제 정책: **삭제보다 보관(archive) 우선**
- Category / ReportPage / ReportBlock에 `is_archived`, `archived_at` 추가.
- 참조 이력(run_histories, snapshots, block_snapshots)이 있으면 하드삭제 대신 보관 처리.
- 참조가 없는 경우에만 하드삭제 가능.
- 목적: 운영 이력 보존 + FK 무결성 유지 + `run_histories.page_id/block_id` NULL 업데이트 방지.

### 2) 페이지 스케줄 UX 개선
페이지 스케줄을 cron 직접 입력 대신 선택식으로 설정:
- 사용 안 함
- 매일 (시간)
- 매주 (요일 + 시간)
- 매월 (일자 + 시간)
- 사용자정의(cron)

내부 저장:
- `schedule_cron` 유지
- `schedule_kind`, `schedule_meta_json` 추가

예시:
- 매일 07:30 → `30 7 * * *`
- 매주 월/금 08:00 → `0 8 * * 1,5`
- 매월 1일 06:45 → `45 6 1 * *`

### 3) 관리자 UI/UX 개선
- `/admin/pages`: 검색/필터, 스케줄 라벨, 최근 실행/게시 시각, 빠른 액션.
- `/admin/pages/{id}`: 페이지 정보 카드, 스케줄 빌더, 블록 카드형 목록.
- `/admin/blocks`: 검색/필터(타입/페이지/카테고리/활성/보관), 상태 배지, 빠른 액션.
- 보관 항목 기본 숨김 + “보관 포함 보기” 제공.

### 4) 사용자 포털 `/view` 개선
- 좌측 사이드바 + 검색 + 카테고리/리포트 트리.
- 현재 리포트 강조, 검색 결과 바로 이동.
- 홈/카테고리/상세 모두 포털형 레이아웃 적용.
- 상세에서 공식 게시본 배지, snapshot 선택, 카드형 결과, 첨부 다운로드 강조.
- `/view`는 published snapshot만 조회.

---

## 실행 방법 (Windows CMD)
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

관리자: `http://127.0.0.1:8000/admin`
사용자: `http://127.0.0.1:8000/view`

## 빠른 점검(테스트) 순서
```cmd
python -m compileall app
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
브라우저에서 `/admin`, `/admin/pages`, `/admin/blocks`, `/view` 점검.

## 운영 이력 보존 이유
- 실행 이력/스냅샷은 감사(Audit) 및 장애 분석의 기준 데이터입니다.
- 엔티티 삭제로 이력이 훼손되면 장애 재현과 결과 추적이 불가능해집니다.
- 따라서 운영 객체는 보관 중심 정책으로 관리합니다.
