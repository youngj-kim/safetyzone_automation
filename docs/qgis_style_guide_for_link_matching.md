# QGIS 표준링크 매칭 검수 스타일 적용 가이드

작성일: 2026-07-09

이 문서는 `analysis.v_zone_link_match_candidate_v2`, `analysis.v_zone_link_match_excluded_v2`, `analysis.v_zone_link_match_coverage_v2`를 QGIS에서 검수할 때 사용할 스타일 파일을 정리한다.

## 스타일 파일

| 대상 레이어 | 스타일 파일 | 분류 필드 |
| --- | --- | --- |
| `analysis.v_zone_link_match_candidate_v2` | `qgis_styles/zone_link_candidate_v2_by_match_rule.qml` | `match_rule_code` |
| `analysis.v_zone_link_match_excluded_v2` | `qgis_styles/zone_link_excluded_v2_by_exclusion_code.qml` | `exclusion_code` |
| `analysis.v_zone_link_match_coverage_v2` | `qgis_styles/zone_link_coverage_v2_by_status.qml` | `coverage_status` |

## 적용 방법

QGIS에서 레이어를 추가한 뒤:

1. 레이어 우클릭
2. `속성`
3. `심볼`
4. 하단 `스타일`
5. `스타일 불러오기`
6. 해당 `.qml` 파일 선택

## 후보 링크 색상 의미

| 규칙 | 표시명 | 색상 | 의미 |
| --- | --- | --- | --- |
| `A_STRONG_OVERLAP` | A1 강한 직접중첩 | 빨강 실선 | 폴리곤과 링크가 충분히 직접 중첩 |
| `A_SHORT_INSIDE` | A2 짧은 내부포함 | 주황 실선 | 짧지만 폴리곤 내부에 명확히 포함 |
| `A_NEAR_PARALLEL_CORRIDOR` | A3 근접 평행 보정 | 파랑 실선 | 좁은 폴리곤 주변에서 같은 도로축으로 평행 |
| `A_JUNCTION_COMPONENT` | A4 교차로 컴포넌트 | 보라 실선 | 회전교차로/교차로 연결 컴포넌트 |
| `B_POTENTIAL_GRADE_SEPARATED` | B 입체도로 의심 | 노랑 점선 | 고가/상부도로 가능성이 있어 검토 필요 |
| `B_WEAK_OVERLAP` | B 약한 중첩 | 갈색 점선 | 약한 직접 중첩 |
| `C_NEAR_CONNECTED_OR_SAME_ROAD` | C 근접 연결/동일도로 | 청록 점선 | seed와 연결된 근접 후보 |
| `D_EXTENDED_NODE_CONNECTED` | D 확장 연결 검토 | 회색 점선 | 낮은 신뢰도 검토 후보 |

## 제외 링크 색상 의미

| 규칙 | 표시명 | 의미 |
| --- | --- | --- |
| `TINY_ADJACENCY` | 제외: 미세 인접 | 너무 짧게 인접한 과매칭 후보 |
| `TOUCH_OR_GRAZE` | 제외: 스침/접촉 | 폴리곤 가장자리만 스치는 후보 |
| `NO_AB_SEED` | 제외: A/B seed 없음 | 같은 그룹에 기준 링크가 없음 |
| `EXTENDED_BUT_NOT_NODE_CONNECTED` | 제외: 확장거리이나 노드 연결 부족 | 거리 내에 있으나 seed와 연결성 부족 |

## 추천 검수 순서

1. `A_STRONG_OVERLAP`만 켜서 기본 A 품질 확인
2. `A_SHORT_INSIDE` 켜서 짧은 내부 링크가 맞게 승격됐는지 확인
3. `A_NEAR_PARALLEL_CORRIDOR` 켜서 좁은 폴리곤 보정이 과하지 않은지 확인
4. `A_JUNCTION_COMPONENT` 켜서 회전교차로/교차로부 묶음이 자연스러운지 확인
5. `B_POTENTIAL_GRADE_SEPARATED` 켜서 상부도로 의심 링크가 A에서 빠졌는지 확인
6. 제외 레이어의 `TINY_ADJACENCY`, `TOUCH_OR_GRAZE`를 켜서 빠져야 할 후보가 잘 빠졌는지 확인

