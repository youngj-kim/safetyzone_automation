# Standard link matching candidate design

이 문서는 보호구역 polygon과 표준노드링크 `mobility.std_link`를 매칭하기 위한 1차 후보 생성 기준입니다.

## 목표

목표는 보호구역 변경 감지 결과를 기존 표준링크 테이블에 바로 반영하는 것이 아닙니다.

초기 목표는 다음입니다.

```text
보호구역 polygon
↔ 표준링크
공간관계 기반 후보 생성
↔ 등급 부여
↔ QGIS/SQL 검토
```

즉, 운영 테이블인 `mobility.std_link`는 변경하지 않고 별도 후보 테이블에만 결과를 저장합니다.

## 입력 데이터

보호구역:

```text
analysis.zone_current
```

표준링크:

```text
mobility.std_link
```

확인된 표준링크 주요 컬럼:

```text
link_id
road_name
road_rank
road_type
length_m
geom
```

두 geometry는 모두 EPSG:5179 기준입니다.

## 후보 등급

| 등급 | 조건 | 의미 | 기본 검토 상태 |
| --- | --- | --- | --- |
| A | polygon과 link가 교차하고, 교차 길이가 충분함 | 강한 직접 교차 후보 | `AUTO_CANDIDATE` |
| B | polygon과 link가 교차하지만, 교차 길이가 짧음 | 경계 스침 또는 약한 교차 후보 | `NEEDS_REVIEW` |
| C | 직접 교차하지 않지만 거리 5m 이하 | 좌표 오차 보정 후보 | `NEEDS_REVIEW` |
| D | 거리 5m 초과 20m 이하 | 병행도로/경계 오차 검토 후보 | `NEEDS_REVIEW` |
| 제외 | 거리 20m 초과 | 기본 후보에서 제외 | 저장 안 함 |

## A/B 세부 기준

직접 교차 후보는 교차 길이와 링크 길이 대비 교차 비율을 함께 봅니다.

```text
intersection_length_m = ST_Length(ST_Intersection(zone.geom, link.geom)의 line 성분)
intersection_ratio = intersection_length_m / link_length_m
```

등급 기준:

```text
A:
  intersects = true
  AND (
    intersection_length_m >= 10
    OR intersection_ratio >= 0.3
  )

B:
  intersects = true
  AND A 조건을 만족하지 않음
```

이 기준은 초기값입니다. QGIS 검토 결과에 따라 10m, 0.3 기준은 조정할 수 있습니다.

## C/D 기준

교차하지 않는 후보는 최단거리 기준으로 나눕니다.

```text
C:
  intersects = false
  AND distance_m <= 5

D:
  intersects = false
  AND 5 < distance_m <= 20
```

## 후보 저장 테이블

1차 MVP 테이블:

```text
analysis.zone_link_match_candidate
```

주요 컬럼:

```text
zone_id
zone_group_id
source_manage_no
facility_name
sgg_code
link_id
candidate_grade
review_status
distance_m
intersection_length_m
link_length_m
intersection_ratio
match_reason
created_run_id
created_at
```

## QGIS 검토 view

QGIS에서는 후보 테이블만 보면 geometry가 부족하므로 view를 사용합니다.

```text
analysis.v_zone_link_match_candidate
```

이 view는 후보 테이블을 `analysis.zone_current`, `mobility.std_link`와 조인해서 보호구역 geometry와 링크 geometry를 함께 보여줍니다.

## 운영 반영 원칙

초기 단계에서는 어떤 후보도 `mobility.std_link`에 직접 반영하지 않습니다.

예상 흐름:

```text
analysis.zone_link_match_candidate
→ QGIS/SQL 검토
→ accepted 후보 선정
→ 추후 별도 반영 로직으로 운영 테이블 업데이트
```

향후 반영 기준 후보:

```text
A: 자동 반영 후보
B/C/D: 검토 후 반영 후보
```

단, 실제 자동 반영 여부는 충분한 샘플 검토 후 결정합니다.

## CLI

후보 생성:

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor build-link-candidates
```

현재 `.env`의 `SGG_CODES` 또는 `SGG_CODES_FILE` 범위에 대해서만 후보를 생성합니다.

서울 25개구 기준이면:

```dotenv
SGG_CODES_FILE=config/sgg_codes.seoul.txt
```

## 검증 쿼리

등급별 후보 수:

```sql
select candidate_grade, review_status, count(*)
from analysis.zone_link_match_candidate
group by candidate_grade, review_status
order by candidate_grade, review_status;
```

QGIS 확인 대상:

```text
analysis.v_zone_link_match_candidate
```
