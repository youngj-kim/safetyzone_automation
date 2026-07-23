# 시설 포인트·통합 보호구역 그룹 모델

## 왜 분리했는가

경찰청 API의 `fturGeomVl`은 한 레코드 안에 보호구역 Polygon과 시설 Point를 함께
담기도 하고, Point만 담기도 한다. 종로구 표본 51건은 다음과 같다.

| 원본 형태 | 레코드 수 | 처리 결과 |
|---|---:|---|
| GeometryCollection | 42 | Polygon은 보호구역으로, Point는 시설 위치로 각각 저장 |
| MultiPoint | 9 | 시설 Point로 저장하고 대표 보호구역 그룹에 연결 |

Point 전용 9건은 삭제 대상이 아니다. 예를 들어 `서울농학교` Point는
`rprsPtznMngNo=111101011447`을 통해 `서울맹학교` 보호구역 그룹에 속한다.

## 세 가지 현재 상태 객체

### `analysis.zone_current`

- 원본 관리번호(`ptznMngNo`)별 현재 보호구역 Polygon
- 기존 NEW/변경/삭제 감지의 기준
- `zone_group_id`는 `rprsPtznMngNo`를 우선 사용하고, 없으면 `ptznMngNo`를 사용
- 도형: `MultiPolygon`, EPSG:5179

### `analysis.zone_facility_point_current`

- 원본에 포함된 모든 현재 시설 Point
- Point 전용 레코드와 GeometryCollection 내부 Point를 모두 보존
- 한 시설에 Point가 여러 개면 `(facility_id, point_ordinal)`로 구분
- `attr_hash`, `point_hash`, `data_hash`로 시설 속성과 위치의 안정성을 확인
- 도형: `Point`, EPSG:5179

과거 실행 결과는 `analysis.zone_facility_point_snapshot`에 실행별로 누적된다.

### `analysis.zone_facility_point_change_event`

시설 Point의 현재 상태를 직전 실행과 비교해 실제 변경만 저장한다.

| 변경 유형 | 의미 |
|---|---|
| `NEW` | 처음 확인된 시설 Point |
| `POINT_CHANGED` | 시설 위치만 변경 |
| `ATTRIBUTE_CHANGED` | 시설명·주소·그룹 등 속성만 변경 |
| `POINT_ATTRIBUTE_CHANGED` | 위치와 속성이 함께 변경 |
| `DELETED` | 같은 그룹의 Polygon 삭제와 함께 사라진 Point |
| `MISSING` | Polygon 삭제 근거 없이 이번 수집 범위에서 사라진 검토 대상 |

`UNCHANGED`는 이벤트 행을 만들지 않고 `ops.pipeline_run.point_unchanged_count`에만
집계한다. Polygon 또는 Point 중 하나라도 변경되면 통합 알림 대상이 된다.

### `analysis.v_zone_group_current`

- `zone_group_id`별 Polygon과 시설 Point를 묶은 조회용 뷰
- `geom`: 그룹에 속한 Polygon을 합친 통합 보호구역
- `facility_points`: 그룹에 속한 시설 Point 모음
- `polygon_record_count`: 그룹에 합쳐진 Polygon 원본 수
- `facility_count`: 그룹에 연결된 시설 수
- `facility_names`: 연결된 시설명 목록

이 뷰는 원본을 덮어쓰지 않는다. 원본 단위 분석은 `zone_current`, 시설 위치는
`zone_facility_point_current`, 업무상 통합 단위는 `v_zone_group_current`에서 각각 확인한다.

## 종로구 재검증 결과

2026-07-06 직전 성공 원본 51건을 새 모델로 재처리했다.

| 검증 항목 | 결과 |
|---|---:|
| 현재 보호구역 Polygon | 42 |
| 현재 시설 Point | 51 |
| Point 전용 원본 레코드 | 9 |
| 통합 보호구역 그룹 | 40 |
| Polygon 없는 고아 Point 그룹 | 0 |
| 유효한 EPSG:5179 Point | 51/51 |
| 유효한 통합 Polygon 그룹 | 40/40 |
| 기존 Polygon 변경 이벤트 | 0 (재처리 전후 동일) |

통합 사례인 `111101011432` 그룹은 Polygon 원본 3건과 시설 5곳을 포함한다.
따라서 원본 42개 Polygon이 40개 업무상 보호구역 그룹으로 정리되는 것이 정상이다.

## QGIS에서 확인하는 순서

1. `analysis.v_zone_group_current`를 `geom` 컬럼으로 추가한다.
2. 그룹 Polygon을 반투명 면으로 표시하고 `representative_name`을 라벨로 사용한다.
3. `analysis.zone_facility_point_current`를 추가한다.
4. Point 라벨은 `facility_name`, 그룹 연결키는 `zone_group_id`로 확인한다.
5. 원본 경계를 비교할 때만 `analysis.zone_current`를 함께 켠다.

통합 뷰에는 Polygon용 `geom`과 Point 묶음용 `facility_points`가 함께 있다. QGIS에서
레이어를 추가할 때 통합 면은 `geom`을 선택한다. 개별 시설 위치를 보고 싶을 때는
`zone_facility_point_current.geom`을 사용하는 것이 가장 단순하다.

## 점검 SQL

```sql
SELECT zone_group_id, representative_name,
       polygon_record_count, facility_count, facility_names
FROM analysis.v_zone_group_current
ORDER BY facility_count DESC, zone_group_id;
```

```sql
SELECT facility_name, source_manage_no, zone_group_id, geom
FROM analysis.zone_facility_point_current
ORDER BY zone_group_id, facility_name;
```

```sql
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE ST_SRID(geom) = 5179) AS srid_5179,
    COUNT(*) FILTER (WHERE ST_IsValid(geom) AND NOT ST_IsEmpty(geom)) AS valid
FROM analysis.zone_facility_point_current;
```

## 다음 단계와 경계

이번 단계는 Point 보존과 그룹 모델까지다. 표준노드링크와의 자동 매칭은 아직 수행하지
않는다. 다음 단계에서는 `v_zone_group_current.geom`을 보호구역 업무 단위로 사용하고,
`zone_facility_point_current.geom`을 시설 기준점으로 보조 활용해 `mobility.std_link` 후보를
선정한다.
