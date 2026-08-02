# Supabase Snapshot Retention and Monthly Local Archive

기준일: 2026-08-02

## 목적

Supabase Free 운영 DB는 보호구역 모니터링을 계속 돌리기 위한 최소 운영 저장소로 사용한다.
전체 원본 스냅샷의 장기 보관은 로컬 PostGIS 또는 로컬 압축 파일 아카이브에서 담당한다.

## 결정사항

Supabase에는 다음 데이터를 장기 유지한다.

- `analysis.zone_current`
- `analysis.zone_facility_point_current`
- `analysis.zone_change_event`
- `analysis.zone_facility_point_change_event`
- `analysis.zone_facility_point_absence`
- `ops.pipeline_run`
- `ops.notification_log`
- `raw.police_zone_api_run`

Supabase에서 다음 payload성 테이블은 정리 대상이다.

- `raw.police_zone_item_snapshot`
- `analysis.zone_snapshot`
- `analysis.zone_facility_point_snapshot`

## 이유

변경 감지는 현재 상태와 이번 수집 결과를 비교해 수행한다. 변경 이력은 change event 테이블의
`old_snapshot`, `new_snapshot`, hash, detected time에 남는다. 따라서 매일 전국 전체 raw/snapshot을
Supabase에 계속 쌓을 필요는 없다.

반대로 대시보드의 최근 도형 변경 표시는 `analysis.zone_snapshot`의 geometry를 참조하므로, 변경이
발생한 객체의 snapshot은 유지한다. 무변경 객체의 snapshot은 운영상 가치보다 용량 부담이 크다.

## 일일 정리 정책

`daily-monitor.yml`은 수집, 품질검사, dashboard export/commit 이후 다음 명령을 실행한다.

```bash
python -m safety_zone_monitor prune-snapshots --run-id "$run_id"
python -m safety_zone_monitor prune-snapshots --retention-days "$SNAPSHOT_RETENTION_DAYS" --baseline-date 2026-07-25
```

기본 `SNAPSHOT_RETENTION_DAYS`는 35일이다.

정리 명령은 다음을 보존한다.

- current 테이블
- change event 테이블
- pipeline run 이력
- notification log
- 변경 이벤트가 발생한 객체의 snapshot

정리 명령은 다음을 삭제한다.

- 대상 run의 raw API item payload
- 대상 run의 변경 없는 Polygon snapshot
- 대상 run의 변경 없는 Point snapshot
- retention 기간을 지난 성공 run의 동일 payload
- `--baseline-date` 이전 또는 당일의 대량 `NEW` 기준선 이벤트 snapshot payload

실패 run은 자동 정리 대상에서 제외한다.

## 용량 점검

Supabase 운영 DB 용량은 다음 명령으로 확인한다.

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor storage-report
```

삭제 전 후보 건수만 보려면 다음처럼 실행한다.

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor prune-snapshots --retention-days 35 --dry-run
```

`prune-snapshots`는 행을 삭제하지만 PostgreSQL relation 파일 크기는 즉시 줄지 않을 수 있다.
Supabase 용량을 실제로 낮춰야 하는 경우 정리 후 다음 명령을 수동 실행한다.

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor compact-snapshots
```

이 명령은 `raw.police_zone_item_snapshot`, `analysis.zone_snapshot`,
`analysis.zone_facility_point_snapshot`에 `VACUUM FULL, ANALYZE`를 수행한다. 실행 중 해당 테이블에
잠금이 걸릴 수 있으므로 일일 수집 시간대와 겹치지 않게 수동으로 실행한다.

## 월간 로컬 원본 아카이브

전체 원본 스냅샷은 Supabase에서 장기 보관하지 않는다. 월 1회 로컬 PC에서 별도 실행해 로컬
PostGIS 또는 압축 파일로 보관한다.

권장 방식은 로컬 PostGIS를 대상으로 전국 기준선 모드 수집을 실행하는 것이다.

```powershell
$env:DATABASE_URL="postgresql://로컬_DB_연결문자열"
$env:OPEN_API_SERVICE_KEY="공공데이터_API_KEY"
$env:SGG_CODES_FILE="config/sgg_codes_nationwide.txt"
.\.venv\Scripts\python.exe -m safety_zone_monitor run --baseline --summary-json exports\monthly_raw_archive\YYYY-MM\summary.json
```

실행 후 로컬 DB에서 `raw.police_zone_item_snapshot`, `analysis.zone_snapshot`,
`analysis.zone_facility_point_snapshot`을 월 단위 dump 또는 압축 파일로 백업한다.

예시:

```powershell
pg_dump "$env:DATABASE_URL" `
  --schema=raw `
  --schema=analysis `
  --table=raw.police_zone_item_snapshot `
  --table=analysis.zone_snapshot `
  --table=analysis.zone_facility_point_snapshot `
  --file=exports\monthly_raw_archive\YYYY-MM\safetyzone_raw_snapshot.dump `
  --format=custom
```

## 다음 작업

- 월간 로컬 아카이브 실행용 PowerShell 스크립트 작성
- `exports/monthly_raw_archive/`를 git 추적 제외 상태로 유지
- 첫 월간 아카이브 실행 후 파일 크기와 복원 절차 확인

## 2026-08-02 Implementation Update

Monthly local archive execution is now scripted.

- `scripts/archive_monthly_snapshot.ps1`: collects a nationwide monthly baseline into a separate local archive DB and writes a PostgreSQL custom-format dump.
- `scripts/register_monthly_archive_task.ps1`: registers the archive script with Windows Task Scheduler after manual runs are stable.
- `docs/monthly_archive_runbook.md`: documents manual execution, restore checks, and scheduling.

Use `MONTHLY_ARCHIVE_DATABASE_URL` for the local archive database. Keep it separate from the daily Supabase `DATABASE_URL`.
