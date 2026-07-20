# NGII 도로중심선 서울/경기 PostGIS 등록 및 단순화 절차

기준일: 2026-07-20

이 절차는 국토지리정보원(NGII) 연속수치지형도 도로중심선 원천파일 중 서울/경기 범위만 병합하고, EPSG:5179 기준으로 단순화한 뒤 기존 `mobility_db` PostGIS에 등록한다. 기존 `mobility.std_link` 표준노드링크 테이블은 변경하지 않는다.

## 오늘 결정사항

| 결정사항 | 이유 | 다음 작업 |
|---|---|---|
| 도로 후보 보강 데이터는 우선 NGII 도로중심선만 사용한다 | 도로명주소 도로구간은 경로탐색 네트워크로 부적합하고, 실폭도로는 면형 데이터라 이번 단계 목적과 다르다 | 서울/경기 도로중심선만 PostGIS에 적재하고 품질을 검증한다 |
| 전국 통판은 보류하고 서울/경기만 사용한다 | 전국 병합만으로도 시간이 오래 걸리고, 현재 테스트베드는 서울/경기로 충분하다 | 서울/경기 병합본을 원본으로 보존하고 이후 필요 시 확장한다 |
| 원본 병합본은 보존하고 단순화본을 별도로 만든다 | 단순화가 짧은 링크, 접속부, 보호구역 주변 도로를 훼손할 수 있다 | 원본과 단순화본을 별도 테이블 또는 레이어로 관리한다 |
| 단순화는 먼저 QGIS에서 육안 검수하고 PostGIS 처리 기준으로 재현한다 | tolerance별 형상 훼손을 눈으로 비교하기 쉽고, 운영 단계에서는 재현 가능한 SQL 기준이 필요하다 | 0.3m, 0.5m, 1.0m 후보를 비교한 뒤 active tolerance를 정한다 |

## 산출 테이블

| 테이블 | 용도 |
|---|---|
| `raw.ngii_road_centerline_raw` | 서울/경기 원천 도로중심선 병합본 |
| `raw.ngii_road_centerline_source_manifest` | 적재한 파일 목록, 크기, 수정시각 |
| `mobility.ngii_road_centerline` | 서울/경기 정규화본, EPSG:5179 |
| `mobility.ngii_road_centerline_simplified` | 단순화본, 기본 후보 허용오차 0.5m |

필요하면 tolerance 후보별 테이블을 일시적으로 둔다.

| 후보 테이블 | 용도 |
|---|---|
| `mobility.ngii_road_centerline_simplified_03m` | 보수적 단순화 후보 |
| `mobility.ngii_road_centerline_simplified_05m` | 기본 단순화 후보 |
| `mobility.ngii_road_centerline_simplified_10m` | 성능 개선 후보, 검증 필요 |

## 준비물

- GDAL `ogr2ogr`
- PostgreSQL client `psql`
- `.env`의 `DATABASE_URL`
- 서울/경기 수치지형도 도로중심선 SHP/GPKG/GeoJSON 파일 묶음

원천 파일은 한 폴더 아래에 시도/시군구/도엽 단위로 나뉘어 있어도 된다. 스크립트가 하위 폴더를 재귀적으로 검색한다. 원본 대용량 파일과 GPKG 결과물은 Git에 올리지 않는다.

QGIS 중간 산출물은 가능하면 GeoPackage로 저장한다.

```text
road_centerline_seoul_gyeonggi_original.gpkg
road_centerline_seoul_gyeonggi_simplified_03m.gpkg
road_centerline_seoul_gyeonggi_simplified_05m.gpkg
road_centerline_seoul_gyeonggi_simplified_10m.gpkg
```

## 실행

PowerShell에서 프로젝트 루트 기준으로 실행한다.

```powershell
.\scripts\import_ngii_road_centerline.ps1 `
  -SourceRoot "D:\data\ngii_road_centerline_seoul_gyeonggi" `
  -FilePattern "*.shp" `
  -SimplifyToleranceM 0.5
```

파일명이 도로중심선만 골라지지 않는 묶음이면 패턴을 좁힌다.

```powershell
.\scripts\import_ngii_road_centerline.ps1 `
  -SourceRoot "D:\data\ngii_topographic_map" `
  -FilePattern "*도로중심선*.shp"
```

수치지형도 레이어 코드명으로 받은 자료라면 해당 코드 패턴을 사용한다.

```powershell
.\scripts\import_ngii_road_centerline.ps1 `
  -SourceRoot "D:\data\ngii_topographic_map" `
  -FilePattern "A002*.shp"
```

## 단순화 기준

기본 후보는 0.5m로 두되, 바로 확정하지 않는다.

| tolerance | 판단 |
|---:|---|
| 0.3m | 보호구역 주변 짧은 이면도로와 접속부 보존을 우선하는 보수적 후보 |
| 0.5m | 기본 후보 |
| 1.0m | 표시 속도와 저장량 개선 후보, 형상 훼손 검증 필요 |

주의할 점:

- 원본 병합본을 덮어쓰지 않는다.
- `ST_SimplifyPreserveTopology`는 개별 geometry 보존에는 유리하지만 네트워크 접속성까지 보장하지 않는다.
- 단순화 전후 endpoint 이동, 짧은 링크 손실, 교차부 변화, 보호구역 주변 후보 변화량을 확인한다.
- 최종 active 테이블 또는 view는 QC 후 선택한다.

## 검증 SQL

```sql
SELECT 'raw' AS layer, COUNT(*) FROM raw.ngii_road_centerline_raw
UNION ALL
SELECT 'normalized', COUNT(*) FROM mobility.ngii_road_centerline
UNION ALL
SELECT 'simplified', COUNT(*) FROM mobility.ngii_road_centerline_simplified;
```

```sql
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE ST_IsEmpty(geom)) AS empty_count,
    COUNT(*) FILTER (WHERE NOT ST_IsValid(geom)) AS invalid_count,
    MIN(ST_SRID(geom)) AS min_srid,
    MAX(ST_SRID(geom)) AS max_srid,
    SUM(original_length_m) AS original_length_m,
    SUM(simplified_length_m) AS simplified_length_m
FROM mobility.ngii_road_centerline_simplified;
```

정상 기준은 `empty_count=0`, `invalid_count=0`, `min_srid=max_srid=5179`이다. 단순화 후 총 연장이 크게 줄거나 보호구역 주변 도로 후보가 사라지면 `-SimplifyToleranceM` 값을 낮춰 다시 적재한다.

## QGIS 확인

QGIS에서는 `mobility.ngii_road_centerline_simplified`를 먼저 열어 서울/경기 표시 속도를 확인하고, 세부 검수나 보호구역 후보 분석이 필요할 때 `mobility.ngii_road_centerline` 원본 정규화본을 함께 띄운다.

기존 보호구역 레이어와 비교할 때는 다음 순서가 편하다.

1. `analysis.zone_current`
2. `mobility.ngii_road_centerline_simplified`
3. 필요 시 `mobility.std_link`

표준노드링크 미구축 생활도로/골목 구간 보완 여부를 볼 때 수치지형도 도로중심선 레이어가 보조 기준선 역할을 한다.

## 이번 단계에서 제외한 데이터

| 데이터 | 판단 |
|---|---|
| 도로명주소 도로구간 | 샘플상 주소체계 선형 성격이 강해 경로탐색 네트워크로 부적합하므로 제외 |
| 도로명주소 실폭도로 | 면형 데이터라 보호구역-도로면 겹침 검증에는 유용하지만, 이번 단계의 선형 네트워크 검증에서는 제외 |
| 전국 도로중심선 통판 | 병합과 검증 비용이 커서 서울/경기 검증 이후 필요 시 확장 |
