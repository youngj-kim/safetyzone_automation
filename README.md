# Safety Zone Change Monitoring System

경찰청 전국 보호구역 Open API를 수집하여 원본·정제 스냅샷을 보존하고, 신규·삭제·속성 변경·
geometry 변경을 감지하는 Python MVP입니다. 기존 표준노드링크 PostGIS를 그대로 사용하며,
NGII 도로중심선 전국통판 0.5m 단순화본을 보호구역-도로 후보 비교의 보조 기준선으로
검증합니다. 이 저장소는 PostgreSQL이나 Docker 컨테이너를 새로 만들지 않습니다.

## 기존 서버 계약

- 기존 프로젝트: `D:\standard-node-link-postgis`
- 컨테이너: `mobility_postgis`
- 데이터베이스: `mobility_db`
- 호스트 접속: `localhost:5433`
- 표준 링크: `mobility.std_link`, EPSG:5179
- 표준 노드: `mobility.std_node`, EPSG:5179
- 금지: 기존 `raw.raw_std_*`, `mobility.std_*`, 뷰, 볼륨의 삭제·재적재·변경

현재 migration은 기존 객체를 건드리지 않고 다음 보호구역 전용 객체만 `IF NOT EXISTS`로
추가합니다.

- `raw.police_zone_api_run`: API 호출 실행 메타데이터
- `raw.police_zone_item_snapshot`: 모든 원본 item JSON/WKT와 payload hash
- `analysis.zone_snapshot`: 실행별 정제 폴리곤 스냅샷, EPSG:5179
- `analysis.zone_current`: 최신 활성 보호구역
- `analysis.zone_facility_point_snapshot`: 실행별 시설 Point 스냅샷, EPSG:5179
- `analysis.zone_facility_point_current`: 최신 활성 시설 Point
- `analysis.zone_facility_point_change_event`: 시설 Point 변경 이력
- `analysis.v_zone_group_current`: 대표관리번호 기준 Polygon·시설 통합 뷰
- `analysis.zone_change_event`: 변경 이력
- `ops.pipeline_run`: 파이프라인 실행 및 집계
- `ops.notification_log`: 알림 성공·실패 이력

## 변경 판정

- `zone_id`: 경찰청 `ptznMngNo` 기반 SHA-256. 누락 시 시설·주소 안정 필드로 대체
- `attr_hash`: geometry를 제외한 정규화 속성 hash
- `geom_hash`: 중첩 Polygon을 `UnaryUnion`으로 합친 정규 geometry hash
- `data_hash`: `attr_hash + geom_hash`
- 변경 유형: `NEW`, `ATTRIBUTE_CHANGED`, `GEOMETRY_CHANGED`,
  `GEOMETRY_ATTRIBUTE_CHANGED`, `UNCHANGED`, `DELETED`
- Point 변경 유형: `NEW`, `POINT_CHANGED`, `ATTRIBUTE_CHANGED`,
  `POINT_ATTRIBUTE_CHANGED`, `UNCHANGED`, `DELETED`, `MISSING`

Point 단독 레코드와 GeometryCollection 내부 Point는 시설 위치로 분리 저장하고,
`rprsPtznMngNo` 기준 통합 보호구역 그룹에 연결합니다. API 원본
EPSG:5181 geometry는 PostGIS 적재 시 `ST_Transform(..., 5179)`로 변환합니다.
GeometryCollection 안의 중첩 Polygon은 합집합으로 해소하며 보정 근거는 `geometry_qc`에
저장합니다.

## 도로 후보 기준 데이터

보호구역과 도로 후보를 비교할 때는 기존 표준노드링크를 기본 비교군으로 사용하고,
NGII 도로중심선은 생활도로·이면도로 보완 가능성을 검증하는 보조 기준선으로 사용합니다.

- 표준노드링크: `mobility.std_link`, EPSG:5179
- NGII 도로중심선 원본 정규화본: `mobility.ngii_road_centerline`, EPSG:5179
- NGII 도로중심선 단순화본: `mobility.ngii_road_centerline_simplified`, 0.5m

NGII 도로중심선은 전국통판을 PostGIS에 적재했지만, 품질 비교와 보호구역 후보 검증은
서울 지역부터 진행합니다. 도로명주소 도로구간과 실폭도로는 이번 단계의 경로탐색/선형
후보 검증 범위에서 제외했습니다.

## 최초 설정

기존 `mobility_postgis` 컨테이너가 실행 중이어야 합니다. 이 저장소에서 `docker compose`를
실행하지 않습니다.

```powershell
Copy-Item .env.example .env
# .env에 공공데이터 Decoding Key와 기존 mobility_db 비밀번호 입력
```

```dotenv
OPEN_API_SERVICE_KEY=실제_Decoding_Key
DATABASE_URL=postgresql://postgres:실제비밀번호@localhost:5433/mobility_db
SGG_CODES=11110
```

비밀번호에 `@`, `:`, `/`, `#` 같은 문자가 있으면 URL 인코딩해야 합니다. `.env`는 Git에서
제외됩니다.

## 안전한 실행 순서

PowerShell 실행 정책과 무관하게 가상환경 Python을 직접 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor audit-db
.\.venv\Scripts\python.exe -m safety_zone_monitor init-db
.\.venv\Scripts\python.exe -m safety_zone_monitor run
.\.venv\Scripts\python.exe -m safety_zone_monitor quality-report
```

1. `audit-db`는 읽기 전용으로 기존 스키마, 필수 객체, 표준 링크/노드 geometry를 검사합니다.
2. `init-db`는 보호구역용 `raw/analysis/ops` 객체만 추가합니다.
3. 첫 `run`은 현재 모니터링 범위의 Polygon을 `NEW`로 저장합니다.
4. 같은 데이터로 재실행하면 `UNCHANGED`여야 합니다.

어느 시군구든 페이지 수집이 불완전하면 DB 반영을 시작하지 않습니다. API가
`ERR_03: 0건`을 반환한 시군구는 빈 지역으로 기록하고 삭제 판정 범위에서 제외해 대량
`DELETED` 오인을 막습니다. 삭제 판정은 현재 실행의 `SGG_CODES` 또는 `SGG_CODES_FILE`
범위에만 적용됩니다.

## 전국 수집 전환

공식 법정동 코드 CSV를 내려받은 뒤 현재 유효한 시군구 코드를 생성합니다.

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor build-sgg-codes `
  --source "다운로드한_법정동코드.csv" `
  --output config\sgg_codes_nationwide.txt
```

이후 `.env` 또는 실행 환경에 다음 값을 지정합니다.

```dotenv
SGG_CODES_FILE=config/sgg_codes_nationwide.txt
```

전국 최초 실행은 변경 이벤트와 알림을 만들지 않는 기준선 모드로 적재한 뒤 `quality-report`를
확인하고 운영 자동화 범위로 전환합니다.

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor run --baseline
```

전국 전체를 한 번에 실행하면 공공 API 429 rate limit에 걸릴 수 있으므로, 현재는
`config/sgg_chunks/nationwide_chunk_01.txt`부터 `nationwide_chunk_06.txt`까지 청크 단위
실행을 병행합니다. GitHub Actions 수동 실행에서는 repository variable을 바꾸지 않고
`sgg_codes_file` 입력값에 청크 파일 경로를 넣어 실행합니다.

## 대시보드와 지도

운영 DB의 최신 상태와 변경 이력을 정적 대시보드가 읽을 수 있는 JSON/GeoJSON으로 내보냅니다.

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor export-dashboard `
  --output dashboard\data `
  --event-limit 500 `
  --baseline-date 2026-07-25
```

신규/변경/삭제 이벤트만 후속 작업에 활용하려면 작업용 GeoJSON을 별도로 추출합니다. 기본값은
`NEW`, 변경 계열, `DELETED`만 포함하고 `MISSING`은 제외합니다.

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor export-change-extracts `
  --output exports\change_extracts `
  --limit 10000 `
  --baseline-date 2026-07-25
```

전국 현재 객체는 단일 대용량 GeoJSON으로 배포하지 않고 시도 단위로 분할합니다.
대시보드는 첫 화면에서 서울 현재 객체만 로드하고, 시도 선택 시
`dashboard/data/current_zones/{sido}.geojson`와
`dashboard/data/current_points/{sido}.geojson`를 가져옵니다. 최근 변경 이벤트는 전국 단위로
유지하며, 시도별 변경 건수는 `change_summary_by_sido.json`으로 표시합니다. 전국 현재 객체 검색은
`dashboard/data/current_search/{sido}.json`을 사용하되 검색어 입력 시점에만 지연 로드합니다.

로컬에서 확인할 때는 저장소 루트에서 정적 파일 서버를 실행한 뒤 브라우저에서
`http://localhost:8084/dashboard/`를 엽니다.

```powershell
.\.venv\Scripts\python.exe -m http.server 8084
```

대시보드는 GitHub Pages로 배포되며 현재 운영 URL은
`https://safetyzone.yjkim.dev`입니다. 현재 Polygon/Point, 변경 Polygon/Point 레이어를
표시하고 시설명·관리번호·시군구·변경 유형으로 최근 이벤트를 필터링합니다. 같은 관리번호의
반복 감지 이력은 `timelines.json`으로 묶어 팝업과 최근 변경 목록에 표시합니다.

대시보드는 `KR / EN` 뷰 전환을 제공합니다. EN 모드의 시설명은 공식 영문명이 아니라
규칙 기반 로마자 표기와 시설 유형 접미사 번역을 조합한 표시명이며, 검증을 위해 한글 원문을
함께 표시합니다.

지도는 OSM을 기본으로 사용하고, 배포 환경에 `KAKAO_JS_KEY`가 있으면 Kakao 지도 전환과
Roadview 확인을 사용할 수 있습니다. 모바일에서는 하단 현황판을 접고 펼칠 수 있으며,
객체 선택 또는 Roadview 진입 시 지도 확인 영역을 확보하도록 현황판이 자동으로 접힙니다.
표준노드링크와 NGII 링크 매칭 결과는 이후 같은 지도 구조에 별도 레이어로 추가합니다.

`--baseline-date`까지 본 서버 API에 이미 존재하던 `NEW` 이벤트는 대시보드의 `신규`에서 제외하고
`현재`로만 표시합니다.

일일 자동화는 변경이 감지된 성공 실행에서만 변경 목록, 현재 객체, 지도 레이어용
`dashboard/data`를 재생성해 커밋합니다. 수집 실패나 품질 검증 실패 시에는 변경 데이터는
갱신하지 않습니다. 다만 대시보드의 `모니터링 이력`은 성공, 실패 여부를 확인할 수 있도록
`dashboard/data/overview.json`만 별도로 갱신합니다.

## 알림

변경 이벤트가 있을 때만 Slack 또는 Telegram으로 알립니다. 알림 성공·실패는
`ops.notification_log`에 남습니다. 채널을 설정하지 않으면 변경은 저장하고 경고 로그만 남깁니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

## GitHub Actions

보호구역 API 수집과 대시보드용 운영 DB는 Supabase PostgreSQL/PostGIS로 전환하고,
워크플로는 GitHub-hosted runner(`ubuntu-latest`)에서 수동 실행하도록 구성했습니다.
표준노드링크, NGII, 매칭 검수 DB는 기존 로컬 PostGIS 운영 범위로 남깁니다.

- Secrets: `OPEN_API_SERVICE_KEY`, `DATABASE_URL`
- Repository variable: 기본은 `SGG_CODES_FILE=config/sgg_codes_nationwide.txt`
- 청크 수동 실행 입력값: `sgg_codes_file=config/sgg_chunks/nationwide_chunk_01.txt` 등
- 수동 실행 입력값: 일반 운영은 `prepare_db=false`, 초기 DB 준비가 필요할 때만 `prepare_db=true`
- 선택 Secrets: `SLACK_WEBHOOK_URL` 또는 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Pages 선택 Secret: `KAKAO_JS_KEY`

2026-07-31 기준 `chunk_01` 일반 변경감지는 Supabase에서 성공했습니다. 예약 수집은 아직 중단하고,
남은 청크를 수동 검증한 뒤 GitHub-hosted runner 기반 09:00 KST schedule 재활성화 여부를 결정합니다.
표준노드링크 매칭은 다음 마일스톤에서 `mobility.std_link.geom`을 대상으로 증분 구현합니다.

## 추가 문서

- [문서 허브](docs/document_hub.md)
- [MVP 프로젝트 상태](docs/mvp_project_status.md)
- [1번방 커밋/배포 인수인계](docs/automation_room_handoff.md)
- [DB 테이블 이해 가이드](docs/database_table_guide.md)
- [표준노드링크 DB 의존성 계약](docs/standard_node_link_db_contract.md)
- [NGII 도로중심선 PostGIS 등록 및 서울 검증 절차](docs/ngii_road_centerline_postgis.md)
- [M0 기존 환경 감사](docs/m0_inventory_report.md)
- [종로구 E2E 테스트 결과](docs/e2e_test_20260706.md)
- [시설 포인트·통합 보호구역 그룹 모델](docs/facility_point_group_model.md)
- [전국 수집 전환 절차](docs/nationwide_rollout.md)
- [전국 기준선 적재 정책](docs/nationwide_baseline_rollout_policy_20260723.md)
- [전국 대시보드 공개 범위](docs/project_scope_nationwide_dashboard_20260723.md)
- [보호구역 수동 실행 및 자동실행 전환 준비](docs/daily_automation.md)
