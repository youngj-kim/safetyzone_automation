# 표준링크 매칭 v2.3 검토 버킷 적용 기준

작성일: 2026-07-10

이 문서는 2026-07-09~2026-07-10 QGIS 육안검수 케이스를 반영해, 기존 A/B/C/D 후보 등급 위에 한 단계 더 보수적인 검토 버킷을 얹는 기준을 정리한다.

핵심 판단은 다음과 같다.

- 기존 A/B/C/D는 후보 산출 등급이다.
- 실제 자동 업데이트에 바로 사용할 등급은 별도로 분리해야 한다.
- 입체도로, 고가도로, 지하차도, 교량, 터널, 연결로 주변은 2D 공간중첩만으로 자동반영하지 않는다.
- 표준링크가 길어서 보호구역 밖까지 표시되는 것은 오류가 아닐 수 있다.
- 표준링크가 없는 보호구역 또는 채택후보가 없는 보호구역도 정상 상태일 수 있다.

## 새 검토 버킷

### 후보 링크 뷰

대상 뷰:

```text
analysis.v_zone_link_match_candidate_review_v23
```

주요 컬럼:

| 컬럼 | 의미 |
| --- | --- |
| `v23_review_bucket` | v2.3 검토 버킷 |
| `manual_review_reason` | 해당 버킷으로 분류한 이유 |
| `auto_apply_eligible` | 향후 자동 업데이트에 바로 사용할 수 있는지 여부 |

버킷:

| 버킷 | 의미 | 처리 |
| --- | --- | --- |
| `AUTO_APPLY_CANDIDATE` | 일반도로이며 강한 직접중첩 또는 짧은 링크 내부포함 | 자동반영 후보 |
| `MANUAL_REVIEW_STRUCTURE` | 고가/지하차도/교량/터널/연결로 또는 입체도로 의심 | 자동반영 금지, 수동검토 |
| `MANUAL_REVIEW_A_NEAR_OR_JUNCTION` | A 등급이지만 근접평행/교차부 로직으로 잡힌 후보 | 수동검토 |
| `MANUAL_REVIEW_WEAK_OVERLAP` | 약한중첩 후보 | 수동검토 |
| `MANUAL_REVIEW_CONNECTED` | C/D 연결 후보 | 수동검토 |
| `MANUAL_REVIEW_OTHER` | 기타 애매한 후보 | 수동검토 |

### 제외 링크 뷰

대상 뷰:

```text
analysis.v_zone_link_match_excluded_review_v23
```

버킷:

| 버킷 | 의미 | 처리 |
| --- | --- | --- |
| `EXCLUDED_VALID` | 스침, 외곽도로, 무관축 등 정상 제외 | 제외 유지 |
| `POSSIBLE_FALSE_NEGATIVE_CONTINUOUS_CORRIDOR` | 연속 보호구역 도로축인데 seed 부재로 제외됐을 가능성 | 누락 의심 검토 |
| `MANUAL_REVIEW_STRUCTURE_EXCLUDED` | 입체도로 주변 제외 후보 | 수동검토 |
| `NO_SEED_REVIEW` | A/B seed 없음 | 보통 정상 무채택 후보이나 필요시 검토 |
| `EXCLUDED_REVIEW_OTHER` | 기타 제외 검토 | 수동검토 |

### 보호구역 단위 요약 뷰

대상 뷰:

```text
analysis.v_zone_link_match_coverage_review_v23
```

버킷:

| 버킷 | 의미 |
| --- | --- |
| `AUTO_APPLY_READY` | 자동반영 후보가 하나 이상 있음 |
| `POSSIBLE_FALSE_NEGATIVE_REVIEW` | 제외됐지만 실제 포함되어야 할 가능성이 있음 |
| `STRUCTURE_MANUAL_REVIEW` | 입체도로/구조물 관련 검토 필요 |
| `MANUAL_REVIEW_ONLY` | 자동반영 후보는 없고 검토후보만 있음 |
| `VALID_NO_STANDARD_LINK_CANDIDATE` | 20m 내 표준링크 후보 없음, 정상일 수 있음 |
| `VALID_NO_ACCEPTED_CANDIDATE` | 주변 후보는 있으나 채택후보 없음, 정상일 수 있음 |

## QGIS 검수 순서

1. `analysis.v_zone_link_match_coverage_review_v23`를 먼저 본다.
2. `v23_coverage_bucket` 스타일을 적용해 보호구역 단위 상태를 훑는다.
3. `POSSIBLE_FALSE_NEGATIVE_REVIEW`, `STRUCTURE_MANUAL_REVIEW`, `MANUAL_REVIEW_ONLY` 순서로 확인한다.
4. 링크 단위 상세 확인은 아래 두 뷰를 사용한다.

```text
analysis.v_zone_link_match_candidate_review_v23
analysis.v_zone_link_match_excluded_review_v23
```

5. 자동 업데이트 후보는 반드시 `auto_apply_eligible = true`인 것만 사용한다.

## 이번 단계에서 의도적으로 하지 않는 것

- 기존 A/B/C/D 후보 산출 로직을 삭제하지 않는다.
- 입체도로 후보를 자동 제외하지 않는다. 대신 자동반영만 막고 수동검토로 보낸다.
- `NO_CANDIDATE_WITHIN_20M`, `NO_ACCEPTED_CANDIDATE`를 오류로 단정하지 않는다.
- 표준링크 원본 테이블에 바로 업데이트하지 않는다.

## 다음 실험 포인트

1. `AUTO_APPLY_CANDIDATE`가 실제로 안전한지 확인한다.
2. `MANUAL_REVIEW_A_NEAR_OR_JUNCTION` 중 자동반영 가능한 하위조건을 더 찾는다.
3. `POSSIBLE_FALSE_NEGATIVE_CONTINUOUS_CORRIDOR`가 과검출되는지 확인한다.
4. 입체도로 주변에서 표준링크 속성만으로 어느 정도까지 거를 수 있는지 확인한다.
5. 장기적으로는 링크 전체가 아니라 보호구역과 겹치는 구간만 잘라 쓰는 segment/clipping 모델을 검토한다.

## 2026-07-10 최초 적용 결과

로컬 `mobility_db`에 v2.3 뷰를 적용한 뒤 최초 집계한 결과는 다음과 같다.

### 후보 링크 버킷

| `v23_review_bucket` | 건수 | 해석 |
| --- | ---: | --- |
| `AUTO_APPLY_CANDIDATE` | 8,047 | 현재 기준에서 자동반영 후보로 볼 수 있는 링크 |
| `MANUAL_REVIEW_A_NEAR_OR_JUNCTION` | 3,512 | A 등급이지만 근접평행/교차부라 수동검토 우선 |
| `MANUAL_REVIEW_CONNECTED` | 1,629 | C/D 연결 후보 |
| `MANUAL_REVIEW_STRUCTURE` | 120 | 고가/지하차도/교량/터널/연결로 등 구조물 검토 후보 |
| `MANUAL_REVIEW_WEAK_OVERLAP` | 204 | 약한중첩 검토 후보 |

### 제외 링크 버킷

| `v23_review_bucket` | 건수 | 해석 |
| --- | ---: | --- |
| `EXCLUDED_VALID` | 6,230 | 정상 제외로 우선 볼 수 있는 후보 |
| `MANUAL_REVIEW_STRUCTURE_EXCLUDED` | 169 | 구조물 주변 제외 후보 |
| `NO_SEED_REVIEW` | 1,512 | seed 부재로 제외된 후보 |
| `POSSIBLE_FALSE_NEGATIVE_CONTINUOUS_CORRIDOR` | 17 | 제외됐지만 연속 도로축 누락 가능성이 있는 후보 |

### 보호구역 단위 버킷

| `v23_coverage_bucket` | 건수 | 검수 우선순위 |
| --- | ---: | --- |
| `AUTO_APPLY_READY` | 877 | 낮음. 샘플 검수 후 자동반영 후보로 유지 |
| `MANUAL_REVIEW_ONLY` | 125 | 중간. 자동반영 후보 없이 검토후보만 존재 |
| `POSSIBLE_FALSE_NEGATIVE_REVIEW` | 16 | 높음. 제외됐지만 포함 가능성 있음 |
| `STRUCTURE_MANUAL_REVIEW` | 31 | 높음. 입체도로/구조물 주변 |
| `VALID_NO_ACCEPTED_CANDIDATE` | 263 | 낮음. 정상 무채택 상태인지 표본 확인 |
| `VALID_NO_STANDARD_LINK_CANDIDATE` | 232 | 낮음. 표준링크 미존재 가능성 |

다음 QGIS 검수는 `POSSIBLE_FALSE_NEGATIVE_REVIEW`와 `STRUCTURE_MANUAL_REVIEW`부터 보는 것이 가장 효율적이다.
