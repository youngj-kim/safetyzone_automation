# 문서 허브

이 문서는 보호구역 자동 모니터링 프로젝트에서 어떤 문서를 먼저 봐야 하는지 정리한 중앙
인덱스다. 채팅방이 역할별로 분리되어 있어도, 문서 탐색은 여기서 시작한다.

관리 주체는 **1번 자동화 설계 대화방**이다. DB 구축 및 운영 대화방에서는 이 문서 전체를
관리하지 않고, DB 관련 문서 입구만 참조한다.

## 1. 먼저 볼 문서

| 상황 | 먼저 볼 문서 |
|---|---|
| 전체 구조를 빠르게 다시 잡을 때 | `README.md` |
| 현재 진행 상태를 확인할 때 | `docs/mvp_project_status.md` |
| 보호구역 프로젝트 시작 이후 주요 일자별 기록을 볼 때 | `docs/project_history.md` |
| 1번방에서 커밋/푸시/대시보드 배포 인수인계를 받을 때 | `docs/automation_room_handoff.md` |
| Supabase 온라인 운영 전환 범위를 확인할 때 | `docs/cloud_operations_migration_plan.md` |
| Supabase 용량 정리와 월간 로컬 원본 보관 정책을 볼 때 | `docs/supabase_snapshot_retention_and_monthly_archive.md` |
| 오전 9시대 청크 분산 자동 실행을 확인할 때 | `docs/daily_automation.md` |
| 배포된 대시보드와 전국 기준선 범위를 확인할 때 | `docs/project_scope_nationwide_dashboard_20260723.md` |
| safetyzone이 표준노드링크 DB를 어떻게 쓰는지 볼 때 | `docs/standard_node_link_db_contract.md` |
| DB 컨테이너, PostGIS, 백업/복원, 서버 이전을 볼 때 | `D:\standard-node-link-postgis\docs\db_operations_runbook.md` |
| 보호구역 DB 테이블 의미를 볼 때 | `docs/database_table_guide.md` |

## 2. 채팅방별 문서 입구

| 채팅방 역할 | 관련 문서 |
|---|---|
| 1번 자동화 설계 | `docs/document_hub.md`, `README.md`, `docs/mvp_project_status.md`, `docs/project_history.md`, `docs/automation_room_handoff.md` |
| DB 구축 및 운영 | `docs/standard_node_link_db_contract.md`, `D:\standard-node-link-postgis\docs\db_operations_runbook.md` |
| 5번 NGII 도로중심선 PostGIS | `docs/ngii_road_centerline_postgis.md` |
| 보호구역 수집/변경 감지 자동화 | `README.md`, `docs/database_table_guide.md`, `docs/change_event_verification.md` |
| 자동 실행/스케줄링 | `docs/daily_automation.md`, `.github/workflows/daily-monitor.yml` |
| 알림 | `docs/telegram_notification_setup.md` |
| 전국 전환 | `docs/nationwide_rollout.md`, `docs/nationwide_baseline_rollout_policy_20260723.md`, `docs/project_scope_nationwide_dashboard_20260723.md`, `docs/seoul_rollout_validation_20260707.md` |
| 7번 Supabase 운영 전환 | `docs/cloud_operations_migration_plan.md`, `docs/daily_automation.md`, `docs/automation_room_handoff.md` |
| 대시보드 배포 | `README.md`, `docs/automation_room_handoff.md`, `.github/workflows/pages.yml` |
| 링크 매칭 검토 | `docs/standard_link_matching_design.md`, `docs/standard_link_matching_v23_review_policy.md` |
| QGIS 검토 | `docs/qgis_style_guide_for_link_matching.md` |

## 3. DB 관련 문서 구분

DB 관련 문서는 두 저장소에 나뉘어 있다.

| 저장소 | 문서 | 역할 |
|---|---|---|
| `D:\Project\3_safetyzone_monitoring_system` | `docs/standard_node_link_db_contract.md` | safetyzone automation이 외부 DB를 어떻게 읽는지 정의 |
| `D:\Project\3_safetyzone_monitoring_system` | `docs/cloud_operations_migration_plan.md` | 보호구역 API 수집/대시보드 운영 DB의 Supabase 전환 정책 |
| `D:\Project\3_safetyzone_monitoring_system` | `docs/supabase_snapshot_retention_and_monthly_archive.md` | Supabase snapshot payload 정리와 월간 로컬 원본 보관 정책 |
| `D:\standard-node-link-postgis` | `docs\db_operations_runbook.md` | 표준노드링크 DB 자체의 운영 정본 |

판단 기준:

- safetyzone 실행 전 DB 의존성을 확인한다면 `standard_node_link_db_contract.md`
- 보호구역 API 수집 운영 DB를 확인한다면 `cloud_operations_migration_plan.md`
- Docker/PostgreSQL/PostGIS 자체를 점검한다면 `db_operations_runbook.md`
- 백업, 복원, 서버 이전을 한다면 `db_operations_runbook.md`
- safetyzone이 변경해도 되는 스키마를 확인한다면 `standard_node_link_db_contract.md`

2026-07-31 기준 운영 구분:

- 보호구역 API 수집, 변경 감지, 알림, 대시보드용 운영 DB는 Supabase Free + GitHub Actions + GitHub Pages로 운영한다.
- 표준노드링크, NGII 도로중심선, 보호구역-도로 매칭 검수 자산은 로컬 PostGIS 운영 범위로 유지한다.
- 일일 자동 실행은 전국 단일 실행이 아니라 09:00~10:40 KST 사이 20분 간격의 6개 청크 schedule로 분산한다.
- 변경 감지에 성공한 실행만 전체 `dashboard/data`를 갱신하고, 실패 또는 무변경 실행은 모니터링 이력용 `overview.json`만 갱신한다.
- Supabase는 current/change event 중심으로 유지하고, raw/snapshot 전체 장기 보관은 월 1회 로컬 아카이브에서 담당한다.

## 4. 주요 문서 목록

### 프로젝트 개요

- `README.md`: 프로젝트 개요, 기존 DB 계약, 실행 순서
- `docs/mvp_project_status.md`: 현재 MVP 진행 상태
- `docs/project_history.md`: 보호구역 프로젝트 시작 이후 주요 일자별 히스토리
- `docs/document_hub.md`: 문서 탐색 중앙 입구
- `docs/automation_room_handoff.md`: 1번방 커밋, 푸시, GitHub Pages 배포 인수인계
- `docs/cloud_operations_migration_plan.md`: Supabase 온라인 운영 전환 계획과 검증 결과
- `docs/supabase_snapshot_retention_and_monthly_archive.md`: Supabase 용량 정리와 월간 로컬 원본 보관 정책
- `docs/m0_inventory_report.md`: 기존 표준노드링크 환경 감사 결과
- `표준노드링크_보호구역_자동화_Codex_인수인계_20260706.docx`: 인수인계 문서

### DB와 운영

- `docs/standard_node_link_db_contract.md`: safetyzone 관점의 표준노드링크/로컬 도로망 DB 계약
- `docs/cloud_operations_migration_plan.md`: 보호구역 운영 DB의 Supabase 전환 정책
- `docs/supabase_snapshot_retention_and_monthly_archive.md`: Supabase snapshot payload 정리와 월간 로컬 원본 아카이브 설계
- `docs/ngii_road_centerline_postgis.md`: NGII 도로중심선 전국통판 PostGIS 등록 및 서울 검증 절차
- `D:\standard-node-link-postgis\docs\db_operations_runbook.md`: DB 운영 점검 런북
- `docs/database_table_guide.md`: 보호구역 모니터링 테이블 설명
- `sql/qc_monitoring_schema.sql`: 보호구역 스키마 QC SQL
- `sql/operational_monitoring_checks.sql`: 운영 상태 점검 SQL

### 자동화와 검증

- `docs/daily_automation.md`: Supabase 기반 보호구역 수집 자동 실행, 청크 schedule, 실패/무변경 이력 갱신 정책
- `docs/windows_scheduler_github_dispatch.md`: 과거 Windows 스케줄러 기반 GitHub workflow dispatch 참고 문서
- `docs/change_event_verification.md`: 변경 이벤트 검증
- `docs/e2e_test_20260706.md`: 종로구 E2E 테스트 결과
- `docs/seoul_rollout_validation_20260707.md`: 서울 전환 검증
- `docs/nationwide_rollout.md`: 전국 수집 전환 절차
- `docs/nationwide_baseline_rollout_policy_20260723.md`: 전국 기준선 적재 정책
- `docs/project_scope_nationwide_dashboard_20260723.md`: 전국 대시보드 공개 범위와 기준선 정책

### 대시보드와 배포

- `dashboard/`: GitHub Pages에 배포되는 정적 대시보드
- `.github/workflows/pages.yml`: `dashboard/`를 `https://safetyzone.yjkim.dev`로 배포
- `.github/workflows/daily-monitor.yml`: 보호구역 수집, 변경 감지, dashboard data export, 모니터링 이력 commit
- `dashboard/data/*.json`, `dashboard/data/change_*.geojson`, `dashboard/data/current_zones/*.geojson`, `dashboard/data/current_points/*.geojson`, `dashboard/data/current_search/*.json`: 공개 정적 대시보드 데이터
- `dashboard/config.js`: 배포 시 `KAKAO_JS_KEY`로 생성되는 로컬/런타임 설정 파일. 커밋하지 않음

### 보호구역 모델

- `docs/facility_point_group_model.md`: 시설 포인트와 통합 보호구역 그룹 모델

### 링크 매칭과 QGIS

- `docs/standard_link_matching_design.md`: 표준링크 매칭 설계
- `docs/standard_link_matching_round1_review.md`: 1차 검토
- `docs/standard_link_matching_round2_casebook.md`: 2차 사례집
- `docs/standard_link_matching_live_review_20260710.md`: 라이브 검토 기록
- `docs/standard_link_matching_v23_review_policy.md`: v2.3 검토 정책
- `docs/qgis_style_guide_for_link_matching.md`: QGIS 스타일 가이드

### 알림

- `docs/telegram_notification_setup.md`: Telegram 알림 설정

## 5. 평소 사용법

일반 점검은 다음 순서로 본다.

1. `docs/document_hub.md`
2. `README.md`
3. 현재 작업 주제의 전용 문서
4. 필요한 경우 SQL 파일 또는 DB 운영 런북

Supabase 온라인 운영 점검은 다음 순서로 본다.

1. `docs/cloud_operations_migration_plan.md`
2. `docs/daily_automation.md`
3. `docs/supabase_snapshot_retention_and_monthly_archive.md`
4. `.github/workflows/daily-monitor.yml`
5. `docs/automation_room_handoff.md`

DB 장애나 서버 이전은 다음 순서로 본다.

1. `docs/standard_node_link_db_contract.md`
2. `D:\standard-node-link-postgis\docs\db_operations_runbook.md`
3. `docs/m0_inventory_report.md`

링크 매칭 검토는 다음 순서로 본다.

1. `docs/standard_link_matching_design.md`
2. `docs/standard_link_matching_v23_review_policy.md`
3. `docs/standard_link_matching_round2_casebook.md`
4. `docs/qgis_style_guide_for_link_matching.md`

NGII 도로중심선 PostGIS 작업은 다음 순서로 본다.

1. `docs/ngii_road_centerline_postgis.md`
2. `docs/standard_node_link_db_contract.md`
3. `D:\standard-node-link-postgis\docs\db_operations_runbook.md`

대시보드 배포 작업은 다음 순서로 본다.

1. `docs/automation_room_handoff.md`
2. `README.md`의 대시보드와 지도 섹션
3. `.github/workflows/pages.yml`
4. `https://safetyzone.yjkim.dev`
