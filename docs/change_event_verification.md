# Change event verification guide

이 문서는 보호구역 모니터링 자동화가 단순히 `SUCCESS`로 끝났는지뿐 아니라, 변경 감지 결과가 정상인지 확인하는 운영 절차입니다.

## 확인 목적

현재 MVP에서 확인해야 하는 핵심은 세 가지입니다.

1. 최신 실행이 성공했는가
2. 폴리곤, 포인트, 통합 그룹 데이터가 0건이 아닌가
3. 같은 조건으로 다시 실행했을 때 가짜 변경 이벤트가 생기지 않는가

## 사용할 SQL

pgAdmin에서 다음 파일의 SQL을 사용합니다.

```text
sql/operational_monitoring_checks.sql
```

파일 안의 각 섹션은 독립적으로 실행할 수 있습니다. pgAdmin 결과창이 헷갈릴 수 있으므로, 섹션 하나씩 선택해서 실행하는 것을 권장합니다.

## 1. 최신 실행 상태 확인

`Latest run health` 섹션을 실행합니다.

종로구 단일 테스트 기준 정상 예시는 다음과 비슷합니다.

```text
polygon_count                  42
point_count                    51
group_count                    40
latest_pipeline_status         SUCCESS
latest_pipeline_sgg_codes      {11110}
```

건수는 API 원본 변경에 따라 달라질 수 있습니다. 다만 `0`이 나오면 먼저 확인이 필요합니다.

## 2. 과거 실패와 최신 실패 구분

`Recent pipeline history` 섹션을 실행합니다.

초기 구축 중에는 GitHub Actions runner, PowerShell 실행 정책, Docker/PostGIS 기동 문제 때문에 `FAILED` 기록이 남을 수 있습니다. 중요한 것은 최신 실행입니다.

판정 기준은 다음과 같습니다.

- 최신 row가 `SUCCESS`: 현재 운영 상태 정상
- 최신 row가 `FAILED`: `error_message` 확인 필요
- 과거 row에만 `FAILED` 존재: 과거 설정 실패 이력일 가능성이 큼

## 3. 변경 이벤트 확인

`Latest successful run diff summary` 섹션을 실행합니다.

첫 실행 또는 DB 초기화 직후에는 `NEW` 이벤트가 많이 나오는 것이 정상입니다.

반대로 같은 `SGG_CODES` 범위로 바로 한 번 더 실행했다면, 원본 API 데이터가 바뀌지 않는 한 이벤트가 없어야 정상입니다.

## 4. 멱등성 확인

`Idempotency check for the latest successful run` 섹션을 실행합니다.

같은 조건으로 재실행한 뒤 기대값은 다음입니다.

```text
idempotency_status = PASS
polygon_event_count = 0
point_event_count = 0
polygon_count = polygon_unchanged_count
facility_point_count = point_unchanged_count
```

`CHECK`가 나오면 무조건 장애라는 뜻은 아닙니다. 실제 원본 데이터가 변경되었거나, 실행 범위가 바뀌었거나, 이전 실행이 초기 적재였을 수 있습니다.

## 5. 공간 품질 확인

`Geometry and group linkage quality check` 섹션을 실행합니다.

정상 기대값은 다음과 같습니다.

```text
invalid_polygons              0
invalid_points                0
point_groups_without_polygon  0
```

`point_groups_without_polygon`은 포인트만 있고 대표 폴리곤이 없는 그룹 수입니다. API 원본 특성상 나올 가능성은 있지만, 현재 종로구 검증에서는 0이 정상 기준입니다.

## 추천 운영 루틴

수동 검증 시에는 다음 순서가 가장 깔끔합니다.

1. GitHub Actions에서 `Daily safety-zone monitor` 실행
2. workflow가 `SUCCESS`인지 확인
3. pgAdmin에서 `Latest run health` 실행
4. 같은 조건으로 한 번 더 실행
5. pgAdmin에서 `Idempotency check` 실행
6. `PASS`면 변경 감지 MVP 정상으로 판단

이 단계가 안정되면 다음은 `SGG_CODES`를 1개 구에서 3개 구로 늘려 확장 검증을 진행합니다.
