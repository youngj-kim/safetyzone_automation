# 보호구역 Supabase 온라인 운영 전환 계획

작성일: 2026-07-30  
담당 방: 7번 보호구역 Supabase 온라인 운영 전환

## 1. 전환 목표

이 문서는 기존 `safetyzone_automation` 저장소를 유지하면서 보호구역 모니터링 운영 DB와 자동 실행 환경을 온라인으로 전환하기 위한 실행 계획이다. 목표 운영 조합은 다음과 같다.

- DB: Supabase Free PostgreSQL/PostGIS
- 실행 환경: GitHub Actions hosted runner, `ubuntu-latest`
- 대시보드 배포: GitHub Pages
- 저장소: 기존 GitHub repo 유지, 새 repo 생성 없음
- 로컬 Docker/PostGIS: 개발, 검증, 백업, 표준노드링크/NGII 매칭 검수용으로 유지

온라인 운영은 보호구역 API 수집, 변경 감지, 모니터링 이력, 대시보드 export 데이터 생성에 한정한다.

## 2. 현재 저장소 구조 요약

현재 주요 구조는 다음과 같다.

| 경로 | 역할 | 온라인 전환 관련 판단 |
|---|---|---|
| `.github/workflows/daily-monitor.yml` | 매일 09:00 KST 보호구역 수집/검증/export/commit | self-hosted Windows runner에서 `ubuntu-latest`로 전환 대상 |
| `.github/workflows/pages.yml` | `dashboard/**` 변경 시 GitHub Pages 배포 | 이미 `ubuntu-latest` 기반. 유지하되 필요 시 Pages 설정만 점검 |
| `src/safety_zone_monitor/` | API 수집, 정규화, DB 반영, diff, export CLI | 온라인 운영 핵심 코드 |
| `src/safety_zone_monitor/migrations/` | 운영/분석/매칭 테이블 migration | Supabase 적용 범위를 분리해야 함 |
| `dashboard/` | 정적 대시보드와 `dashboard/data` export 결과 | GitHub Pages 배포 대상 |
| `config/sgg_codes_nationwide.txt` | 전국 시군구 수집 범위 | GitHub Actions variable 또는 workflow 입력에서 사용 |
| `config/sgg_chunks/` | 전국 수집 수동 chunk 실행용 | rate limit 대응용으로 유지 |
| `docs/` | 운영/설계/검수 문서 | 본 문서 추가 |
| `qgis_styles/`, `sql/link_match_*`, NGII 문서/이미지 | 표준노드링크/NGII 검수 보조 | 온라인 운영 제외 |

기존 `daily-monitor.yml`은 `runs-on: [self-hosted, windows, x64]`였고, `DATABASE_URL`이 로컬 `localhost:5433`의 `mobility_db`를 가리킨다는 전제 때문에 self-hosted runner에 묶여 있었다. Supabase 전환 코드에서는 `SAFETYZONE_DB_MODE=cloud`를 사용해 보호구역 운영 migration만 적용하고, `mobility.std_link` 필수 검사를 건너뛰도록 분리한다.

2026-07-30 현재 1번방 결정에 따라 매일 09:00 KST 예약 실행은 일단 중단 상태로 유지한다. 따라서 hosted runner 전환 후에도 `workflow_dispatch` 수동 실행으로 먼저 검증하고, schedule 재개는 별도 의사결정 후 진행한다.

## 3. Supabase 이전 범위

Supabase로 이전하는 대상은 보호구역 운영에 필요한 최소 DB 객체다.

### 3.1 포함 대상

| 스키마 | 객체 | 용도 |
|---|---|---|
| `ops` | `pipeline_run` | 매 실행의 성공/실패, 수집 범위, 수집/변경/오류 집계 |
| `ops` | `notification_log` | Slack/Telegram 알림 성공/실패 이력 |
| `raw` | `police_zone_api_run` | API 호출 실행 메타데이터 |
| `raw` | `police_zone_item_snapshot` | API 원본 item JSON/WKT와 payload hash |
| `analysis` | `zone_snapshot` | 실행별 보호구역 polygon 정규화 snapshot |
| `analysis` | `zone_current` | 최신 활성 보호구역 polygon |
| `analysis` | `zone_change_event` | polygon 신규/속성변경/geometry변경/삭제 이력 |
| `analysis` | `zone_facility_point_snapshot` | 실행별 facility point snapshot |
| `analysis` | `zone_facility_point_current` | 최신 facility point |
| `analysis` | `zone_facility_point_change_event` | point 신규/속성변경/위치변경/삭제/MISSING 이력 |
| `analysis` | `zone_facility_point_absence` | point 부재 추적 |
| `analysis` | `v_zone_group_current` 등 보호구역 운영 view | 대시보드 export와 품질 점검에 필요한 view |

적용 migration 기준으로는 `001_initial.sql`부터 `006_facility_point_change_events.sql`, `012_facility_point_deleted_events.sql`, `013_facility_point_absence_tracking.sql`이 온라인 운영의 기본 후보이다. 단, 실제 Supabase 적용 전에는 각 migration 내부의 view와 참조 관계를 점검해 `mobility.*` 의존이 없는 운영 subset으로 분리한다.

현재 코드의 운영 migration subset은 다음과 같다.

- `001_initial.sql`
- `002_inactive_metrics.sql`
- `003_make_transformed_geometry_valid.sql`
- `004_geometry_qc.sql`
- `005_facility_points_and_zone_groups.sql`
- `006_facility_point_change_events.sql`
- `012_facility_point_deleted_events.sql`
- `013_facility_point_absence_tracking.sql`

### 3.2 제외 대상

다음 객체와 데이터는 Supabase 온라인 운영 대상으로 이전하지 않는다.

| 범위 | 제외 이유 |
|---|---|
| `raw.raw_std_link_*`, `raw.raw_std_node_*`, `raw.raw_std_multilink_*` | 표준노드링크 원본 대용량 데이터. 온라인 운영 범위 아님 |
| `mobility.std_link`, `mobility.std_node`, `mobility.std_multilink` | 도로망 매칭 검수용 로컬 DB 계약. Supabase Free 운영 대상 아님 |
| `mobility.ngii_road_centerline`, `mobility.ngii_road_centerline_simplified` | NGII 도로중심선 검수용 보조 데이터. 온라인 운영 제외 |
| `analysis.zone_link_match_candidate*`, `analysis.zone_link_match_excluded*` | 표준노드링크 매칭 후보/제외/검수 DB. 로컬 유지 |
| `analysis.v_zone_link_match_*` | `mobility.std_link`에 의존하는 매칭 view. 로컬 유지 |
| QGIS 스타일, round review 이미지/문서 | 검수 산출물. 온라인 수집/대시보드 운영 DB 제외 |

운영 원칙은 명확하다. 보호구역 API 원본, 정규화 결과, 변경 이력, 모니터링 이력, 대시보드 export용 최신 데이터만 온라인으로 옮긴다. 도로망 매칭과 검수 DB는 기존 로컬 PostGIS에 남긴다.

## 4. 데이터 반영 정책

현재 결정사항을 온라인 운영에서도 유지한다.

- 수집 성공 + 변경 감지 시에만 대시보드의 변경 데이터와 현재 객체 export를 갱신한다.
- 변경이 없는 성공 실행도 모니터링 이력은 대시보드에 표시한다.
- 수집 실패 또는 품질 검증 실패 시 변경 데이터와 현재 객체 export는 갱신하지 않는다.
- 실패 이력은 `ops.pipeline_run`에 남기고, 대시보드의 모니터링 이력에는 실패 사유가 보이도록 한다.
- API가 특정 시군구에 0건을 반환한 경우, 그것만으로 기존 데이터를 대량 삭제로 해석하지 않는다.
- `.env`, API key, `DATABASE_URL`, Supabase DB password, webhook/token 값은 커밋하지 않는다.

## 5. Supabase 프로젝트 생성 후 설정 목록

Supabase 콘솔에서 새 프로젝트를 만든 뒤 다음을 설정한다.

### 5.1 Supabase 콘솔

1. Organization/Project 생성
2. Region 선택: 한국 사용자가 중심이면 가까운 region 선택
3. Database password 생성 및 별도 비밀 저장소에 보관
4. Database connection string 확인
5. SQL Editor에서 PostGIS 활성화

```sql
create extension if not exists postgis;
```

6. 운영 migration subset 적용
7. `raw`, `analysis`, `ops` 스키마와 필수 테이블/view 생성 확인
8. GitHub Actions 접속 방식 선택

Supabase 연결 문자열은 GitHub Actions secret에만 저장한다. 일반적으로 hosted runner에서는 connection pooler 또는 direct connection 중 하나를 사용한다. Free tier에서는 연결 수가 제한되므로, 매일 1회 batch 성격의 작업은 짧게 연결하고 종료하는 현재 구조를 유지한다.

### 5.2 GitHub Secrets

Settings -> Secrets and variables -> Actions -> Repository secrets에 다음을 설정한다.

| 이름 | 필수 여부 | 설명 |
|---|---:|---|
| `OPEN_API_SERVICE_KEY` | 필수 | 공공데이터포털 Decoding key |
| `DATABASE_URL` | 필수 | Supabase PostgreSQL 연결 문자열 |
| `SLACK_WEBHOOK_URL` | 선택 | 변경 알림용 |
| `TELEGRAM_BOT_TOKEN` | 선택 | 변경 알림용 |
| `TELEGRAM_CHAT_ID` | 선택 | 변경 알림용 |
| `KAKAO_JS_KEY` | 선택 | GitHub Pages 대시보드 Kakao 지도/Roadview |

### 5.3 GitHub Variables

| 이름 | 권장값 | 설명 |
|---|---|---|
| `SGG_CODES_FILE` | `config/sgg_codes_nationwide.txt` | 기본 전국 수집 범위 |
| `SGG_CODES` | 비움 | 파일 기반 수집을 기본으로 할 경우 중복 방지 |

workflow에는 `SAFETYZONE_DB_MODE=cloud`가 고정되어 있으므로 GitHub variable로 따로 지정하지 않아도 된다.

수동 chunk 실행 시에는 repository variable을 바꾸지 않고 workflow dispatch 입력 `sgg_codes_file`에 `config/sgg_chunks/nationwide_chunk_01.txt` 같은 경로를 넣는다.

초기 기준선 적재는 workflow dispatch 입력 `baseline_load=true`로 실행한다. 이 모드는 `run --baseline`을 사용해 current/snapshot은 채우되 변경 이벤트와 알림은 만들지 않는다. 기준선 적재도 대시보드의 현재 객체 파일은 갱신해야 하므로 `dashboard/data` 전체 export/commit을 수행한다.

## 6. GitHub Actions 전환 작업 계획

### 6.1 workflow 목표 형태

`daily-monitor.yml`의 운영 job은 다음 방향으로 바꾼다.

- `runs-on: ubuntu-latest`
- `workflow_dispatch` 수동 실행 유지, schedule은 아직 비활성
- 초기 적재용 `baseline_load` 입력 지원
- 기본 shell은 bash
- Python은 `actions/setup-python`으로 3.11 또는 3.12 고정
- `python -m pip install .` 실행
- Supabase `DATABASE_URL` secret 사용
- `init-ops-db`로 운영 DB 객체 준비
- `audit-ops-db`로 운영 수집 전용 DB audit 수행
- `run --summary-json run_summary.json` 실행
- `quality-report` 실행
- 변경 감지 시 `dashboard/data` 전체 export/commit
- 변경이 없거나 실패 이력을 반영해야 하는 경우 `overview.json` 중심 export/commit 유지

### 6.2 코드 수정 필요사항

현재 코드 기준으로 hosted runner 전환 전에 다음 수정이 필요하다.

1. 운영 DB audit 분리
   - 현재 `audit-db`와 `run_pipeline`은 `mobility.std_link`, `mobility.std_node` 존재를 요구한다.
   - Supabase 운영 경로에서는 `raw/analysis/ops` 보호구역 객체와 PostGIS만 확인하는 `audit-ops-db` 또는 옵션을 추가한다.

2. migration subset 분리
   - 기존 `Repository.migrate()`는 모든 migration을 순서대로 적용했다.
   - `007`부터 `011`까지는 표준노드링크 매칭 관련 객체와 `mobility.std_link` 의존 view가 포함된다.
   - Supabase 운영용 migration은 `001-006`, `012-013`만 적용한다.

3. pipeline 실행 전 로컬 도로망 계약 검사 제거 또는 모드화
   - `run_pipeline()`의 `_verify_mobility_contract(repository)` 호출은 `SAFETYZONE_DB_MODE=cloud`에서 건너뛴다.
   - 로컬 매칭/검수 명령인 `build-link-candidates*`에서는 기존 검사를 유지한다.

4. 대시보드 export 쿼리 점검
   - `export_dashboard_data()`가 매칭 후보 view 또는 `mobility.*` 객체를 참조하지 않는지 확인한다.
   - 참조가 있다면 온라인 운영 export에서는 보호구역 current/change/monitoring 데이터만 사용하도록 분리한다.

5. 테스트 추가
   - 운영 migration 목록이 `mobility.*`, `zone_link_match_*`, `ngii_*`를 포함하지 않는지 확인하는 테스트
   - Supabase 운영 모드에서 `run_pipeline`이 `mobility.std_link` 검사를 요구하지 않는지 확인하는 테스트
   - `daily-monitor.yml`이 `ubuntu-latest`와 `actions/setup-python`을 쓰는지 확인하는 workflow 테스트

### 6.3 전환 순서

1. 본 문서 확정
2. 운영 migration subset 설계 및 코드 반영
3. Supabase 프로젝트 생성, PostGIS 활성화
4. Supabase에 운영 migration 적용
5. GitHub secrets/variables 설정
6. `daily-monitor.yml`을 `ubuntu-latest`로 전환
7. workflow dispatch로 작은 범위 `SGG_CODES=11110` 또는 chunk 파일 검증
8. Supabase DB row count와 `ops.pipeline_run` 성공 이력 확인
9. `export-dashboard` 결과가 로컬과 동일한 구조로 생성되는지 확인
10. GitHub Pages 배포 확인
11. 전국 chunk 수동 실행으로 초기 baseline 또는 운영 데이터 이관
12. self-hosted Windows runner 의존 제거
13. 1번방 결정 후 매일 09:00 KST schedule 재개 여부 확인

## 7. 검증 체크리스트

### 7.1 Supabase DB

- `select postgis_full_version();` 성공
- `raw`, `analysis`, `ops` 스키마 존재
- 운영 테이블과 view 존재
- `mobility` 스키마 또는 표준노드링크/NGII 테이블 생성 없음
- `ops.pipeline_run`에 성공/실패 이력 기록
- 실패 메시지에 API key 등 민감 query parameter가 노출되지 않음

### 7.2 GitHub Actions

- runner가 `ubuntu-latest`
- Python 버전 고정
- `.env` 파일 사용 없음
- secrets/variables만 사용
- notification test가 DB를 변경하지 않음
- 수집 실패 시 변경 데이터 commit 없음
- 변경 없음 성공 시 `dashboard/data/overview.json` 갱신 가능
- 변경 감지 성공 시 `dashboard/data` 갱신 commit

### 7.3 대시보드

- GitHub Pages 배포 성공
- 최신 모니터링 이력에 성공/실패 모두 표시
- 변경 감지 없는 성공 실행도 이력에 표시
- 수집 실패 후 변경 목록/현재 객체가 이전 성공 상태를 유지
- Kakao key가 없을 때도 기본 지도 표시가 가능

## 8. 남은 결정/확인 사항

2026-07-31 기준 확인된 사항:

- Supabase project ref: `cqnipjvbwgkineoqnvji`
- GitHub Actions 연결 문자열은 Supabase Session pooler `:5432`를 사용한다.
- 보호구역 운영 migration은 필요 시 `prepare_db=true` 수동 입력에서만 실행한다.
- 일반 cloud 수집은 migration을 반복하지 않고 `audit-ops-db`로 운영 DB 계약만 확인한다.
- 초기 운영 기준선은 로컬 운영 DB subset을 Supabase로 복사하는 방식으로 확정했다.
- `chunk_01` 일반 변경감지는 Supabase에서 성공했고, `NEW` 폭증 없이 품질검사까지 통과했다.
- 변경 없음/실패 이력 갱신은 전체 dashboard export가 아니라 `overview.json` 경량 export만 사용한다.

남은 사항:

- `chunk_02`~`chunk_06` 일반 변경감지 검증
- 충분히 안정화된 뒤 09:00 KST schedule 재활성화 여부 결정
- Supabase Free 용량과 백업 정책 확인
- self-hosted runner 제거 또는 보관 시점 결정

## 9. 로컬 운영 DB에서 Supabase로 기준선 이관

온라인 수집 경로가 정상임을 확인한 뒤에는 Supabase를 첫 적재 변경감지 상태로 계속 쌓기보다, 기존 로컬 운영 DB의 보호구역 운영 subset을 Supabase 기준선으로 복사한다.

복사 명령은 다음 테이블만 대상으로 한다.

- `ops.pipeline_run`
- `ops.notification_log`
- `raw.police_zone_api_run`
- `raw.police_zone_item_snapshot`
- `analysis.zone_snapshot`
- `analysis.zone_current`
- `analysis.zone_change_event`
- `analysis.zone_facility_point_snapshot`
- `analysis.zone_facility_point_current`
- `analysis.zone_facility_point_change_event`
- `analysis.zone_facility_point_absence`

복사 대상에는 `mobility.*`, `raw.raw_std_*`, `analysis.zone_link_match_*`, NGII 도로중심선 객체를 포함하지 않는다.

실행 전 dry-run:

```powershell
$env:DATABASE_URL="Supabase 연결 문자열"
$env:SOURCE_DATABASE_URL="로컬 mobility_db 연결 문자열"
.\.venv\Scripts\python.exe -m safety_zone_monitor copy-ops-db --dry-run
```

Supabase 운영 테이블을 비우고 로컬 운영 subset으로 교체:

```powershell
$env:DATABASE_URL="Supabase 연결 문자열"
$env:SOURCE_DATABASE_URL="로컬 mobility_db 연결 문자열"
.\.venv\Scripts\python.exe -m safety_zone_monitor copy-ops-db --replace-target
```

이관 후 검증:

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor audit-ops-db
.\.venv\Scripts\python.exe -m safety_zone_monitor quality-report
.\.venv\Scripts\python.exe -m safety_zone_monitor export-dashboard --output dashboard\data --event-limit 500 --baseline-date 2026-07-25
```

이관 검증 후에는 GitHub Actions에서 이미 성공한 chunk 하나를 일반 변경감지 모드로 다시 실행한다. 정상 기준은 `NEW` 폭증이 아니라 기존 기준선과 비교된 `UNCHANGED` 중심 결과다.

2026-07-31에 `chunk_01` 일반 변경감지 검증을 완료했다.

- workflow run: `30598053853`
- `Run daily monitor`: success
- `quality-report`: success
- `Check detected changes`: success
- `Export monitoring history`: success
- `Commit monitoring history`: success
- GitHub Pages 수동 배포: success

검증 중 확인된 운영 보정:

- Supabase pooler 연결에서 read-only 세션 상태가 남을 수 있어 DB 연결 직후 `default_transaction_read_only=off`를 설정한다.
- Supabase 임시 디스크 사용량을 줄이기 위해 변경 없음/실패 이력 갱신 시에는 전체 GeoJSON export를 하지 않고 `overview.json`만 갱신한다.

## 10. 구현 메모

온라인 운영 전환의 핵심은 "보호구역 모니터링 DB"와 "도로망 매칭 검수 DB"를 코드와 migration 수준에서 분리하는 것이다. 현재 저장소는 기능적으로 두 영역이 함께 있으므로, Supabase 전환은 단순히 `DATABASE_URL`만 바꾸면 끝나지 않는다.

우선순위는 다음과 같다.

1. Supabase에서 돌릴 수 있는 운영 migration subset을 만든다.
2. 수집 pipeline에서 `mobility.*` 필수 검사를 운영 모드에서 제거한다.
3. GitHub Actions를 hosted runner 기준으로 바꾼다.
4. 대시보드 export와 Pages 배포는 기존 정적 파일 구조를 유지한다.
