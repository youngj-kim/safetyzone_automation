# M0 기존 표준노드링크 환경 감사

기준일: 2026-07-06

## 결론

현재 보호구역 저장소가 별도 PostGIS 컨테이너를 생성하는 설계는 기존 환경과 중복이었다.
보호구역 자동화는 `D:\standard-node-link-postgis`의 `mobility_postgis / mobility_db`에 기능을
추가하는 구조로 재설계한다. 기존 표준노드링크 객체와 데이터 볼륨은 변경하지 않는다.

## 읽기 전용 파일 감사 결과

| 확인 항목 | 문서 기준 | 실제 파일 상태 | 판정 |
|---|---|---|---|
| 프로젝트 루트 | `D:\standard-node-link-postgis` | 존재 | 일치 |
| Dockerfile | pgRouting + PostGIS + GDAL | 존재, 해당 패키지 설치 | 일치 |
| Compose 컨테이너 | `mobility_postgis` | Compose에 명시 | 일치 |
| DB/포트 | `mobility_db`, `5433:5432` | Compose에 명시 | 일치 |
| 영구 데이터 | `postgres_data` | 존재 | 일치 |
| 표준노드링크 원본 | `data/raw/standard_node_link/20260612` | LINK/NODE/MULTILINK/TURNINFO 존재 | 일치 |
| 재현 SQL | `sql` | 폴더는 있으나 SQL 파일 없음 | M1 파일화 필요 |

## DB 감사 결과

Docker named pipe는 Codex 격리 계정에서 접근할 수 없었지만, 호스트 `localhost:5433`에 직접
읽기 전용으로 접속하여 실제 DB를 확인했다.

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor audit-db
```

| 객체 | 실제 결과 |
|---|---:|
| `mobility.std_link` | 1,555,150건, MultiLineString, SRID 5179 |
| `mobility.std_node` | 1,178,457건, Point, SRID 5179 |
| `mobility.std_multilink` | 18,916건 |
| 문서의 raw/mobility 필수 객체와 뷰 | 모두 존재 |
| 초기 `analysis` 객체 | 없음 |
| 초기 `ops` 스키마 | 없음 |

문서와 실제 DB의 핵심 계약은 일치한다.

## 재구성 범위

- 이 저장소의 `docker-compose.yml` 제거
- 기존 `mobility_db` 연결을 `.env`로 주입
- 기존 객체에는 DROP/ALTER를 수행하지 않는 additive migration
- API 원본은 `raw`, 보호구역 스냅샷/변경은 `analysis`, 실행/알림은 `ops`
- 보호구역 geometry를 EPSG:5181에서 EPSG:5179로 변환
- GitHub Actions는 기존 Windows 호스트의 self-hosted runner 사용

## 실행한 읽기 전용 명령

```powershell
Get-ChildItem -Force D:\standard-node-link-postgis
Get-Content D:\standard-node-link-postgis\Dockerfile
Get-Content D:\standard-node-link-postgis\docker-compose.yml  # 비밀번호 마스킹
Get-ChildItem D:\standard-node-link-postgis\data -Depth 4
```

## 보호구역 객체 추가 결과

사용자의 재구성 요청에 따라 기존 표준노드링크 객체를 변경하지 않는 additive migration을 실행했다.

| 스키마 | 생성 객체 | geometry |
|---|---|---|
| `raw` | `police_zone_api_run`, `police_zone_item_snapshot` | 없음 |
| `analysis` | `zone_snapshot`, `zone_current`, `zone_change_event` | MultiPolygon, SRID 5179 |
| `ops` | `pipeline_run`, `notification_log` | 없음 |

생성 후 다시 `audit-db`를 실행했으며 기존 표준 링크·노드·멀티링크 건수와 geometry 계약은
변하지 않았다. 이후 종로구 1개 시군구 E2E 결과는 `e2e_test_20260706.md`에 별도로 기록했다.
