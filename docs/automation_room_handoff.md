# 1번방 배포 인수인계

이 문서는 이 방에서 진행한 개발 내용을 1번방에서 커밋, 푸시, 웹 배포할 때 확인하는 고정 인수인계 문서입니다.

## 사용 방법

사용자가 1번방에 다음처럼 요청하면 됩니다.

```text
docs/automation_room_handoff.md 확인해서 지금까지 개발진행한거 커밋/푸시하고 웹 배포까지 진행해줘.
```

1번방에서는 먼저 `git status --short`로 실제 변경 목록을 확인한 뒤, 아래의 포함/제외 기준에 맞춰 커밋합니다.

## 최신 작업 요약

- 대시보드에서 보호구역 종류를 구분 표시하도록 수정했습니다.
- 보호구역 종류는 API의 `facility_type_code` 기준으로 표시합니다.
- 현재 Polygon/Point는 종류별 색상으로 표시하고, 신규/변경/삭제 검토 레이어는 변경 상태 색상을 유지하되 카드와 팝업에 보호구역 종류를 함께 표시합니다.
- 현재 레이어는 `어린이`, `노인`, `장애인`, `기타`로 나눠 선택할 수 있습니다.
- `최근 변경` 탭은 변경 상태 기준으로 필터링합니다.
- `현재 객체` 탭은 전체 현재 객체를 보호구역 종류와 검색어 기준으로 필터링합니다.
- 지도 범례에 `어린이`, `노인`, `장애인`, `신규`, `변경`, `삭제(검토)` 항목을 함께 표시합니다.
- 노인보호구역과 변경, 장애인보호구역과 신규가 혼동되지 않도록 보호구역 종류 팔레트를 재지정했습니다.
- 모니터링 이력의 실패 run은 숨기지 않고, 카드에 실패 사유를 표시합니다.
- 대시보드 export에 포함되는 실패 메시지는 `serviceKey`, `token` 등 민감 쿼리 파라미터를 마스킹합니다.
- 대시보드 데이터 export에 `facility_type_code`가 포함되도록 DB export 쿼리를 수정했습니다.
- 대시보드 정적 데이터는 2026-07-07 기준선 정책을 적용해 재생성했습니다.

## 보호구역 종류 매핑

- `1`: 어린이보호구역, 파랑 `#2563eb`
- `2`: 노인보호구역, 자주색 `#be185d`
- `3`: 장애인보호구역, 청록색 `#0891b2`
- 그 외 값: 기타/미분류

## 커밋 대상

다음 파일들의 변경은 커밋 대상입니다.

- `dashboard/index.html`
- `dashboard/app.js`
- `dashboard/styles.css`
- `src/safety_zone_monitor/db.py`
- `dashboard/data/change_events.json`
- `dashboard/data/change_points.geojson`
- `dashboard/data/change_zones.geojson`
- `dashboard/data/current_points.geojson`
- `dashboard/data/current_zones.geojson`
- `dashboard/data/run_history.json`
- `dashboard/data/summary.json`
- `dashboard/data/timelines.json`
- `docs/automation_room_handoff.md`

상황에 따라 함께 커밋될 수 있는 기존 변경:

- `src/safety_zone_monitor/api.py`
- `src/safety_zone_monitor/pipeline.py`
- `src/safety_zone_monitor/cli.py`
- `src/safety_zone_monitor/migrations/013_facility_point_absence_tracking.sql`
- `config/sgg_codes_nationwide.txt`
- 관련 문서 파일

## 커밋 제외 대상

다음은 커밋하지 않습니다.

- `.env`
- `.actions-runner/`
- `.venv/`
- `.pytest_cache/`
- `.ruff_cache/`
- `tmp/`
- `config/law_dong_codes_full.zip`
- `config/law_dong_codes_full/`

특히 `.env`에는 로컬 실행용 설정과 민감 정보가 포함될 수 있으므로 절대 커밋하지 않습니다.

## 검증 완료

이 방에서 다음 검증을 완료했습니다.

```powershell
node --check dashboard\app.js
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m safety_zone_monitor export-dashboard --output dashboard\data --event-limit 500 --baseline-date 2026-07-07
```

검증 결과:

- `node --check dashboard\app.js` 통과
- `ruff check` 통과
- `pytest` 27개 통과
- 대시보드 데이터 export 완료
- 로컬 `http://localhost:8084/dashboard/` 응답 확인

## 배포 확인

커밋/푸시 후 GitHub Pages 배포가 완료되면 아래 URL에서 확인합니다.

- `https://safetyzone.yjkim.dev`

배포 후 브라우저 캐시 때문에 이전 JS/CSS가 보일 수 있으므로, `dashboard/index.html`의 cache version이 최신인지 확인합니다.

현재 기대 버전:

- `styles.css?v=20260723-13`
- `app.js?v=20260723-13`

## 전국 기준선 상태

- 전국 수집용 `config/sgg_codes_nationwide.txt`는 생성되어 있습니다.
- GitHub Actions repository variable은 `SGG_CODES_FILE=config/sgg_codes_nationwide.txt`로 설정되어 있습니다.
- 전국 기준선 DB 등록은 아직 완료되지 않았습니다.
- 공공 API 429 rate limit 때문에 재시도가 필요합니다.
- 전국 통판 등록 시에는 2026-07-07 기준 API에 이미 존재했던 시설을 `신규`로 취급하지 않는 정책을 유지합니다.

## 남은 작업

- API 제한이 풀린 뒤 전국 기준선 수집을 재시도합니다.
- 전국 기준선 등록 후 dashboard data를 다시 export하고 배포합니다.
- 필요 시 Kakao 지도/Roadview 적용은 별도 법적/약관 검토 후 진행합니다.

## 1번방 작업 순서

1. `git status --short`로 변경 목록을 확인합니다.
2. 위 커밋 대상과 제외 대상을 비교합니다.
3. 제외 대상이 add되지 않도록 주의해서 staging합니다.
4. 테스트가 필요하면 검증 명령을 한 번 더 실행합니다.
5. 커밋합니다.
6. `main`에 push합니다.
7. GitHub Pages 배포 완료 후 `https://safetyzone.yjkim.dev`에서 반영 여부를 확인합니다.
