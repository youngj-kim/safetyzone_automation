# 수치지형도 도로중심선 전국통판 등록 절차

이 절차는 수치지형도 도로중심선 원천파일을 전국 단일 레이어로 병합하고, EPSG:5179 기준으로 단순화한 뒤 기존 `mobility_db` PostGIS에 등록한다. 기존 `mobility.std_link` 표준노드링크 테이블은 변경하지 않는다.

## 산출 테이블

| 테이블 | 용도 |
|---|---|
| `raw.ngii_road_centerline_raw` | 원천 도로중심선 병합본 |
| `raw.ngii_road_centerline_source_manifest` | 적재한 파일 목록, 크기, 수정시각 |
| `mobility.ngii_road_centerline` | 전국통판 정규화본, EPSG:5179 |
| `mobility.ngii_road_centerline_simplified` | 단순화본, 기본 허용오차 1m |

## 준비물

- GDAL `ogr2ogr`
- PostgreSQL client `psql`
- `.env`의 `DATABASE_URL`
- 수치지형도 도로중심선 SHP/GPKG/GeoJSON 파일 묶음

원천 파일은 한 폴더 아래에 시도/시군구/도엽 단위로 나뉘어 있어도 된다. 스크립트가 하위 폴더를 재귀적으로 검색한다.

## 실행

PowerShell에서 프로젝트 루트 기준으로 실행한다.

```powershell
.\scripts\import_ngii_road_centerline.ps1 `
  -SourceRoot "D:\data\ngii_road_centerline" `
  -FilePattern "*.shp" `
  -SimplifyToleranceM 1.0
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

정상 기준은 `empty_count=0`, `invalid_count=0`, `min_srid=max_srid=5179`이다. 단순화 후 총 연장이 크게 줄면 `-SimplifyToleranceM` 값을 낮춰 다시 적재한다.

## QGIS 확인

QGIS에서는 `mobility.ngii_road_centerline_simplified`를 먼저 열어 전국 표시 속도를 확인하고, 세부 검수나 보호구역 후보 분석이 필요할 때 `mobility.ngii_road_centerline` 원본 정규화본을 함께 띄운다.

기존 보호구역 레이어와 비교할 때는 다음 순서가 편하다.

1. `analysis.zone_current`
2. `mobility.ngii_road_centerline_simplified`
3. 필요 시 `mobility.std_link`

표준노드링크 미구축 생활도로/골목 구간 보완 여부를 볼 때 수치지형도 도로중심선 레이어가 보조 기준선 역할을 한다.
