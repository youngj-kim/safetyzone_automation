# 표준노드링크 DB 의존성 계약

이 문서는 safetyzone automation이 외부 표준노드링크 PostGIS DB를 사용할 때 지켜야 하는
접속, 읽기, 변경 범위 계약이다. DB 컨테이너 생성, 표준노드링크 적재, 백업/복원, 서버 이전의
정본 문서는 `D:\standard-node-link-postgis\docs\db_operations_runbook.md`에 둔다.

## 1. 역할 분리

| 저장소 | 역할 |
|---|---|
| `D:\standard-node-link-postgis` | 표준노드링크/PostGIS 원천 DB 구축 및 운영 |
| `D:\Project\3_safetyzone_monitoring_system` | 보호구역 수집, 변경 감지, 표준노드링크 읽기 기반 자동화 |

이 저장소는 PostgreSQL/PostGIS 컨테이너를 새로 만들지 않는다. 기존 `mobility_postgis` 컨테이너와
`mobility_db` 데이터베이스를 외부 의존성으로 사용한다.

## 2. 외부 DB 접속 계약

| 항목 | 값 |
|---|---|
| Docker 컨테이너 | `mobility_postgis` |
| 데이터베이스 | `mobility_db` |
| 호스트 접속 | `localhost:5433` |
| 애플리케이션 접속 설정 | `.env`의 `DATABASE_URL` |

`.env` 예시:

```dotenv
DATABASE_URL=postgresql://postgres:실제비밀번호@localhost:5433/mobility_db
```

비밀번호에 `@`, `:`, `/`, `#` 같은 문자가 있으면 URL 인코딩해야 한다.

## 3. 표준노드링크 읽기 대상

| 객체 | 용도 | geometry 계약 |
|---|---|---|
| `mobility.std_link` | 보호구역-링크 매칭 대상 | MultiLineString, EPSG:5179 |
| `mobility.std_node` | 링크 시작/종료 노드 검증 대상 | Point, EPSG:5179 |
| `mobility.std_multilink` | 멀티링크 보조 정보 | geometry 없음 또는 별도 구조 |
| `mobility.v_multilink_summary` | 멀티링크 요약 조회 | View |
| `mobility.v_std_link_multilink_summary` | 표준링크-멀티링크 요약 조회 | View |

기준 감사 결과:

| 객체 | 기준 건수 |
|---|---:|
| `mobility.std_link` | 1,555,150 |
| `mobility.std_node` | 1,178,457 |
| `mobility.std_multilink` | 18,916 |

## 4. 변경 금지 대상

safetyzone automation은 아래 객체를 변경하지 않는다.

- `raw.raw_std_*`
- `mobility.std_*`
- `mobility.v_*`
- Docker volume
- 표준노드링크 원본 파일

금지 작업:

- `DROP`
- `TRUNCATE`
- `DELETE`
- 표준노드링크 테이블 재적재
- 표준노드링크 테이블 구조 변경
- 표준노드링크 geometry/SRID 변경

표준노드링크 DB 자체의 변경, 재적재, 백업, 복원, 서버 이전은
`D:\standard-node-link-postgis` 쪽 운영 절차에서만 수행한다.

## 5. safetyzone이 추가하는 객체

safetyzone automation은 기존 표준노드링크 객체를 변경하지 않고 다음 스키마에 필요한 객체만
추가한다.

| 스키마 | 역할 |
|---|---|
| `raw` | 보호구역 API 원본과 수집 실행 기록 |
| `analysis` | 보호구역 정제 geometry, 현재 상태, 변경 이력 |
| `ops` | 파이프라인 실행 결과와 알림 이력 |

주요 객체:

- `raw.police_zone_api_run`
- `raw.police_zone_item_snapshot`
- `analysis.zone_snapshot`
- `analysis.zone_current`
- `analysis.zone_facility_point_snapshot`
- `analysis.zone_facility_point_current`
- `analysis.zone_facility_point_change_event`
- `analysis.v_zone_group_current`
- `analysis.zone_change_event`
- `ops.pipeline_run`
- `ops.notification_log`

## 6. 실행 전 확인

실행 위치: Windows PowerShell

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor audit-db
```

`audit-db`는 읽기 전용으로 다음을 확인한다.

- `raw`, `mobility`, `analysis`, `ops` 스키마 상태
- 표준노드링크 필수 객체 존재 여부
- `mobility.std_link`, `mobility.std_node` geometry type/SRID
- 선택적으로 표준노드링크 주요 테이블 건수

운영 실행 순서:

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor audit-db
.\.venv\Scripts\python.exe -m safety_zone_monitor init-db
.\.venv\Scripts\python.exe -m safety_zone_monitor run
.\.venv\Scripts\python.exe -m safety_zone_monitor quality-report
```

## 7. pgAdmin 확인 SQL

실행 위치: pgAdmin Query Tool

현재 접속 DB 확인:

```sql
SELECT current_database() AS current_database,
       current_user AS current_user,
       inet_server_port() AS server_port;
```

PostGIS 확장 확인:

```sql
SELECT extname, extversion
FROM pg_extension
ORDER BY extname;
```

표준노드링크 객체 확인:

```sql
SELECT object_name,
       to_regclass(object_name) IS NOT NULL AS exists
FROM (
    VALUES
        ('raw.raw_std_link_20260612'),
        ('raw.raw_std_node_20260612'),
        ('raw.raw_std_multilink_20260612'),
        ('mobility.std_link'),
        ('mobility.std_node'),
        ('mobility.std_multilink'),
        ('mobility.v_multilink_summary'),
        ('mobility.v_std_link_multilink_summary')
) AS objects(object_name);
```

geometry 계약 확인:

```sql
SELECT f_table_schema,
       f_table_name,
       f_geometry_column,
       type,
       srid
FROM public.geometry_columns
WHERE (f_table_schema, f_table_name) IN (
    ('mobility', 'std_link'),
    ('mobility', 'std_node')
)
ORDER BY f_table_schema, f_table_name;
```

건수 확인:

```sql
SELECT 'mobility.std_link' AS object_name, COUNT(*) AS row_count
FROM mobility.std_link
UNION ALL
SELECT 'mobility.std_node', COUNT(*)
FROM mobility.std_node
UNION ALL
SELECT 'mobility.std_multilink', COUNT(*)
FROM mobility.std_multilink;
```

## 8. 장애 시 확인 순서

1. `D:\standard-node-link-postgis\docs\db_operations_runbook.md`에서 Docker/PostGIS 운영 상태를 확인한다.
2. `mobility_postgis` 컨테이너가 실행 중인지 확인한다.
3. `localhost:5433/mobility_db`에 pgAdmin으로 접속되는지 확인한다.
4. 이 문서의 pgAdmin 확인 SQL을 실행한다.
5. `audit-db`를 실행해 safetyzone 관점의 외부 DB 계약을 확인한다.

DB 자체가 손상되었거나 백업/복원이 필요하면 safetyzone repo에서 처리하지 않고
`D:\standard-node-link-postgis`의 운영 절차를 따른다.
