# Supabase DB Health Check Queries

기준일: 2026-08-02

## 목적

이 문서는 Supabase SQL Editor에서 보호구역 모니터링 운영 DB의 상태를 빠르게 확인하기 위한 점검 쿼리를 모은다.

점검 대상은 온라인 운영 범위인 보호구역 API 수집, 변경 감지, 알림, 대시보드 데이터이며, 표준노드링크/NGII/매칭 검수 로컬 DB는 포함하지 않는다.

## 먼저 볼 쿼리

운영 상태를 빠르게 확인할 때는 아래 순서로 본다.

1. 전체 테이블 용량
2. 현재 보호구역 Polygon/Point 건수
3. 최근 모니터링 실행 이력
4. 스냅샷 테이블 잔여 건수

## 1. 전체 테이블 용량

Supabase Free 500MB 제한을 넘지 않는지 확인한다.

```sql
select
  schemaname || '.' || relname as table_name,
  pg_size_pretty(pg_total_relation_size(relid)) as total_size,
  pg_size_pretty(pg_relation_size(relid)) as table_size,
  pg_size_pretty(pg_indexes_size(relid)) as index_size,
  n_live_tup as estimated_rows
from pg_stat_user_tables
where schemaname in ('raw', 'analysis', 'ops')
order by pg_total_relation_size(relid) desc;
```

정상 기준:

- `analysis.zone_current`, `analysis.zone_facility_point_current`, change event 테이블이 주 용량을 차지한다.
- `raw.police_zone_item_snapshot`, `analysis.zone_snapshot`, `analysis.zone_facility_point_snapshot`은 정리 후 작게 유지된다.
- 총 용량은 Supabase Free 기준인 500MB 아래를 유지한다.

## 2. 현재 보호구역 Polygon/Point 건수

대시보드의 현재 지표와 DB 기준 현재 객체 수가 맞는지 확인한다.

```sql
select 'polygon_current' as target, count(*) as rows
from analysis.zone_current
union all
select 'point_current' as target, count(*) as rows
from analysis.zone_facility_point_current;
```

## 3. 변경 이벤트 건수

신규, 속성변경, 도형변경, 삭제 검토 등 이벤트가 어떤 비중으로 쌓여 있는지 확인한다.

```sql
select
  'polygon' as target,
  change_type,
  count(*) as rows
from analysis.zone_change_event
group by change_type
union all
select
  'point' as target,
  change_type,
  count(*) as rows
from analysis.zone_facility_point_change_event
group by change_type
order by target, change_type;
```

## 4. 최근 모니터링 실행 이력

매일 6개 chunk 실행이 성공했는지, 실패 사유가 남았는지 확인한다.

```sql
select
  run_id,
  started_at,
  finished_at,
  status,
  sgg_count,
  polygon_count,
  point_count,
  error_message
from ops.pipeline_run
order by started_at desc
limit 20;
```

확인 포인트:

- schedule이 켜진 운영 상태에서는 09:00~10:40 KST 사이 6개 chunk 실행이 남아야 한다.
- API 429, 네트워크 오류, 품질검사 실패가 있으면 `status='FAILED'`와 `error_message`를 먼저 확인한다.
- 실패 실행은 대시보드 모니터링 이력에는 남기되, current/change event 업데이트 기준으로 쓰지 않는다.

## 5. 최근 변경 발생일별 건수

대시보드의 발생일 필터와 지역별 변경 카운트가 DB와 맞는지 확인한다.

```sql
select
  (detected_at at time zone 'Asia/Seoul')::date as detected_date,
  'polygon' as target,
  change_type,
  count(*) as rows
from analysis.zone_change_event
group by detected_date, change_type
union all
select
  (detected_at at time zone 'Asia/Seoul')::date as detected_date,
  'point' as target,
  change_type,
  count(*) as rows
from analysis.zone_facility_point_change_event
group by detected_date, change_type
order by detected_date desc, target, change_type;
```

## 6. 스냅샷 테이블 잔여 건수

Supabase 용량 정리 정책이 잘 적용되고 있는지 확인한다.

```sql
select 'raw.police_zone_item_snapshot' as table_name, count(*) as rows
from raw.police_zone_item_snapshot
union all
select 'analysis.zone_snapshot' as table_name, count(*) as rows
from analysis.zone_snapshot
union all
select 'analysis.zone_facility_point_snapshot' as table_name, count(*) as rows
from analysis.zone_facility_point_snapshot;
```

정상 기준:

- `raw.police_zone_item_snapshot`은 일일 정리 후 0건 또는 매우 적은 건수로 유지된다.
- `analysis.zone_snapshot`과 `analysis.zone_facility_point_snapshot`은 변경 이벤트 재현에 필요한 최소 snapshot만 남는다.
- 원본 전체 보존은 Supabase가 아니라 월간 로컬 아카이브에서 담당한다.

## 7. 시군구별 현재 객체 수

특정 시군구 데이터가 비정상적으로 많거나 적은지 확인한다.

```sql
select
  sgg_code,
  count(*) filter (where source_type = 'polygon') as polygon_count,
  count(*) filter (where source_type = 'point') as point_count,
  count(*) as total_count
from (
  select sgg_code, 'polygon' as source_type
  from analysis.zone_current
  union all
  select sgg_code, 'point' as source_type
  from analysis.zone_facility_point_current
) t
group by sgg_code
order by total_count desc;
```

## 8. 최근 신규/변경/삭제 상세

가장 최근 이벤트 100건을 빠르게 확인한다.

```sql
select
  'polygon' as target,
  detected_at,
  change_type,
  zone_id as object_id,
  facility_name,
  sgg_code
from analysis.zone_change_event
union all
select
  'point' as target,
  detected_at,
  change_type,
  facility_id as object_id,
  facility_name,
  sgg_code
from analysis.zone_facility_point_change_event
order by detected_at desc
limit 100;
```

## 9. 오늘 실행 결과만 확인

오늘 실행된 chunk가 모두 성공했는지 볼 때 사용한다.

```sql
select
  run_id,
  started_at at time zone 'Asia/Seoul' as started_kst,
  finished_at at time zone 'Asia/Seoul' as finished_kst,
  status,
  sgg_count,
  polygon_count,
  point_count,
  error_message
from ops.pipeline_run
where (started_at at time zone 'Asia/Seoul')::date = current_date
order by started_at;
```

## 10. 변경 감지된 실행만 확인

알림이 왔거나 대시보드 전체 export가 있었던 실행을 확인한다.

```sql
select
  p.run_id,
  p.started_at at time zone 'Asia/Seoul' as started_kst,
  p.status,
  count(distinct z.change_event_id) as polygon_events,
  count(distinct fp.change_event_id) as point_events
from ops.pipeline_run p
left join analysis.zone_change_event z
  on z.run_id = p.run_id
left join analysis.zone_facility_point_change_event fp
  on fp.run_id = p.run_id
group by p.run_id, p.started_at, p.status
having count(distinct z.change_event_id) > 0
    or count(distinct fp.change_event_id) > 0
order by p.started_at desc
limit 20;
```

## 관련 문서

- `docs/cloud_operations_migration_plan.md`
- `docs/daily_automation.md`
- `docs/supabase_snapshot_retention_and_monthly_archive.md`
- `docs/database_table_guide.md`
