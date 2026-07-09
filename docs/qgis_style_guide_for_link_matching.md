# QGIS 표준링크 매칭 검수 스타일 가이드

작성일: 2026-07-09

이 문서는 `analysis.v_zone_link_match_candidate_v2`, `analysis.v_zone_link_match_excluded_v2`, `analysis.v_zone_link_match_coverage_v2`를 QGIS에서 검수할 때 사용할 스타일 파일을 정리한다.

## 스타일 파일

| 대상 레이어 | 스타일 파일 | 분류 필드 |
| --- | --- | --- |
| `analysis.v_zone_link_match_candidate_v2` | `qgis_styles/zone_link_candidate_v2_by_match_rule.qml` | `match_rule_code` |
| `analysis.v_zone_link_match_candidate_v2` | `qgis_styles/zone_link_candidate_v2_by_structure.qml` | `link_structure_category` |
| `analysis.v_zone_link_match_excluded_v2` | `qgis_styles/zone_link_candidate_v2_by_structure.qml` | `link_structure_category` |
| `analysis.v_zone_link_match_excluded_v2` | `qgis_styles/zone_link_excluded_v2_by_exclusion_code.qml` | `exclusion_code` |
| `analysis.v_zone_link_match_coverage_v2` | `qgis_styles/zone_link_coverage_v2_by_status.qml` | `coverage_status` |

## 적용 방법

QGIS에서 레이어를 추가한 뒤 다음 순서로 적용한다.

1. 레이어 우클릭
2. `속성`
3. `심볼`
4. 하단 `스타일`
5. `스타일 불러오기`
6. 해당 `.qml` 파일 선택

## 후보 링크 매칭 규칙 색상

| 규칙 | 표시명 | 의미 |
| --- | --- | --- |
| `A_STRONG_OVERLAP` | A1 강한 직접중첩 | 보호구역 폴리곤과 링크가 충분히 직접 중첩 |
| `A_SHORT_INSIDE` | A2 짧은 내부포함 | 짧은 링크가 보호구역 폴리곤 내부에 명확히 포함 |
| `A_NEAR_PARALLEL_CORRIDOR` | A3 근접 평행 보정 | 좁은 폴리곤 주변에서 같은 축으로 평행 |
| `A_JUNCTION_COMPONENT` | A4 교차로 컴포넌트 | 회전교차로, 교차로 연결 컴포넌트 |
| `B_POTENTIAL_GRADE_SEPARATED` | B 입체도로 의심 | 고가/상부도로 가능성이 있어 검토 필요 |
| `B_WEAK_OVERLAP` | B 약한 중첩 | 약한 직접 중첩 |
| `C_NEAR_CONNECTED_OR_SAME_ROAD` | C 근접 연결/동일도로 | seed와 연결된 근접 후보 |
| `D_EXTENDED_NODE_CONNECTED` | D 확장 연결 검토 | 넓은 범위의 연결 후보 |

## 표준링크 구조 검토 스타일

`zone_link_candidate_v2_by_structure.qml`은 표준노드링크 구축기준의 `Road_Type`, `Connect`, `Multi_Link` 속성을 검수하기 위한 보조 스타일이다. 매칭 등급 자체를 바꾸지는 않고, 고가/지하/교량/터널/연결로처럼 2D 공간중첩만으로 오탐이 생길 수 있는 링크를 빠르게 찾기 위한 용도다.

| 표시 | `link_structure_category` | 판정 의미 |
| --- | --- | --- |
| 빨강 실선 | `NORMAL_ROAD` | 일반도로 |
| 노랑 파선 | `ELEVATED_ROAD_REVIEW` | 고가차도 검토 |
| 파랑 파선 | `UNDERPASS_REVIEW` | 지하차도 검토 |
| 보라 점선 | `BRIDGE_REVIEW` | 교량 검토 |
| 검정 점선 | `TUNNEL_REVIEW` | 터널 검토 |
| 주황 실선 | `RAMP_CONNECTOR_REVIEW` | 연결로/램프 검토 |
| 회색 파선 | `STRUCTURE_REVIEW` | 기타 구조 검토 |

검수할 때는 다음 컬럼을 함께 확인한다.

- `road_type`, `road_type_name`
- `connect`, `connect_name`
- `multi_link`, `multi_link_name`
- `structure_review_flag`
- `candidate_grade`
- `match_rule_code`

## 표준노드링크 코드 해석

`지능형교통체계 표준 노드·링크 구축기준`의 링크 속성 코드표 기준이다.

| 필드 | 코드 | 의미 |
| --- | --- | --- |
| `road_type` | `000` | 일반도로 |
| `road_type` | `001` | 고가차도 |
| `road_type` | `002` | 지하차도 |
| `road_type` | `003` | 교량 |
| `road_type` | `004` | 터널 |
| `connect` | `0` | 연결로 없음 |
| `connect` | `1` | 연결로 있음 |
| `multi_link` | `0` | 독립구간 |
| `multi_link` | `1` | 중용구간 |

## 추천 검수 순서

1. `match_rule_code` 스타일로 A1/A2/A3/A4/B/C/D의 기본 매칭 품질을 본다.
2. 같은 레이어에 `link_structure_category` 스타일을 적용해 지하차도/고가차도/터널/교량/연결로 후보를 본다.
3. `UNDERPASS_REVIEW`, `TUNNEL_REVIEW`는 보호구역 접근도로가 아닌 입체도로일 가능성이 높으므로 우선 검토한다.
4. `ELEVATED_ROAD_REVIEW`, `BRIDGE_REVIEW`는 자동 제외하지 않는다. 북부간선도로처럼 실제 대상도로가 구조물 링크인 경우가 있기 때문이다.
5. `RAMP_CONNECTOR_REVIEW`는 회전교차로/교차로 컴포넌트인지, 단순 램프 오탐인지 구분한다.
6. `analysis.v_zone_link_match_excluded_v2`에도 같은 구조 스타일을 적용해 “제외했지만 구조적으로 다시 볼 필요가 있는 후보”를 확인한다.
