param(
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,

    [string]$FilePattern = "*.shp",
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$WorkDir = "build\ngii_road_centerline",
    [string]$RawSchema = "raw",
    [string]$RawTable = "ngii_road_centerline_raw",
    [string]$TargetSchema = "mobility",
    [string]$TargetTable = "ngii_road_centerline",
    [string]$SimplifiedTable = "ngii_road_centerline_simplified",
    [int]$TargetSrid = 5179,
    [double]$SimplifyToleranceM = 1.0,
    [string]$SourceEncoding = "CP949",
    [string]$SourceReleaseDate = "2025-08-01"
)

$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

function Read-DotEnvValue {
    param([string]$Key)
    if (-not (Test-Path ".env")) {
        return $null
    }
    foreach ($line in Get-Content ".env") {
        $trimmed = $line.Trim()
        if ($trimmed -and -not $trimmed.StartsWith("#") -and $trimmed.StartsWith("$Key=")) {
            return $trimmed.Substring($Key.Length + 1).Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command '$Name'. Install GDAL/PostgreSQL client tools and add them to PATH."
    }
}

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    $DatabaseUrl = Read-DotEnvValue -Key "DATABASE_URL"
}
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    throw "Missing DATABASE_URL. Set it in the environment, .env, or pass -DatabaseUrl."
}

Require-Command "ogr2ogr"
Require-Command "psql"

& psql $DatabaseUrl -v "ON_ERROR_STOP=1" -c "CREATE SCHEMA IF NOT EXISTS $RawSchema; CREATE SCHEMA IF NOT EXISTS $TargetSchema;"
if ($LASTEXITCODE -ne 0) {
    throw "Could not create or verify target PostGIS schemas."
}

$sourcePath = Resolve-Path $SourceRoot
$workPath = Join-Path (Get-Location) $WorkDir
$sqlPath = Join-Path $workPath "register_ngii_road_centerline.sql"

New-Item -ItemType Directory -Force -Path $workPath | Out-Null

$files = Get-ChildItem -Path $sourcePath -Recurse -File -Filter $FilePattern |
    Where-Object { $_.Extension -match '^\.(shp|gpkg|geojson|json)$' } |
    Sort-Object FullName

if ($files.Count -eq 0) {
    throw "No vector files matched '$FilePattern' under '$sourcePath'."
}

$manifestPath = Join-Path $workPath "source_manifest.csv"
$files |
    Select-Object FullName, Length, LastWriteTimeUtc |
    Export-Csv -Path $manifestPath -NoTypeInformation -Encoding UTF8

Write-Host "Loading $($files.Count) road-centerline source file(s) directly into PostGIS $RawSchema.$RawTable ..."

$first = $true
foreach ($file in $files) {
    $modeArgs = @("-f", "PostgreSQL")
    if (-not $first) {
        $modeArgs += "-append"
    } else {
        $modeArgs += "-overwrite"
    }
    & ogr2ogr @modeArgs `
        "PG:$DatabaseUrl" `
        $file.FullName `
        -nln "$RawSchema.$RawTable" `
        -lco "GEOMETRY_NAME=geom" `
        -lco "FID=source_row_id" `
        -lco "PRECISION=NO" `
        -nlt "MULTILINESTRING" `
        -oo "ENCODING=$SourceEncoding" `
        -t_srs "EPSG:$TargetSrid" `
        -makevalid `
        -skipfailures
    if ($LASTEXITCODE -ne 0) {
        throw "ogr2ogr PostGIS load failed for $($file.FullName)."
    }
    $first = $false
}

$escapedManifestPath = $manifestPath.Replace("'", "''")
$sql = @"
DROP TABLE IF EXISTS $RawSchema.ngii_road_centerline_source_manifest;
CREATE TABLE $RawSchema.ngii_road_centerline_source_manifest (
    source_path text NOT NULL,
    byte_size bigint NOT NULL,
    last_write_time_utc timestamptz NOT NULL,
    source_release_date date NOT NULL DEFAULT DATE '$SourceReleaseDate',
    loaded_at timestamptz NOT NULL DEFAULT now()
);
\copy $RawSchema.ngii_road_centerline_source_manifest (source_path, byte_size, last_write_time_utc) FROM '$escapedManifestPath' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

DROP TABLE IF EXISTS $TargetSchema.$TargetTable;
CREATE TABLE $TargetSchema.$TargetTable AS
WITH source_rows AS (
    SELECT
        source_row_id,
        ST_Multi(
            ST_CollectionExtract(
                ST_MakeValid(ST_Force2D(geom)),
                2
            )
        )::geometry(MultiLineString, $TargetSrid) AS geom,
        to_jsonb(r) - 'geom' AS attrs
    FROM $RawSchema.$RawTable AS r
    WHERE geom IS NOT NULL
),
valid_rows AS (
    SELECT *
    FROM source_rows
    WHERE NOT ST_IsEmpty(geom)
)
SELECT
    row_number() OVER (ORDER BY source_row_id)::bigint AS centerline_id,
    md5(ST_AsEWKB(geom)::text || attrs::text) AS feature_hash,
    source_row_id,
    DATE '$SourceReleaseDate' AS source_release_date,
    ST_Length(geom)::double precision AS length_m,
    attrs,
    geom
FROM valid_rows;

ALTER TABLE $TargetSchema.$TargetTable
    ADD PRIMARY KEY (centerline_id);
CREATE INDEX ${TargetTable}_geom_gix
    ON $TargetSchema.$TargetTable USING gist (geom);
CREATE INDEX ${TargetTable}_hash_idx
    ON $TargetSchema.$TargetTable (feature_hash);

DROP TABLE IF EXISTS $TargetSchema.$SimplifiedTable;
CREATE TABLE $TargetSchema.$SimplifiedTable AS
SELECT
    centerline_id,
    feature_hash,
    source_row_id,
    source_release_date,
    length_m AS original_length_m,
    ST_Length(simplified_geom)::double precision AS simplified_length_m,
    $SimplifyToleranceM::double precision AS simplify_tolerance_m,
    attrs,
    simplified_geom AS geom
FROM (
    SELECT
        centerline_id,
        feature_hash,
        source_row_id,
        source_release_date,
        length_m,
        attrs,
        ST_Multi(
            ST_CollectionExtract(
                ST_RemoveRepeatedPoints(
                    ST_SimplifyPreserveTopology(geom, $SimplifyToleranceM)
                ),
                2
            )
        )::geometry(MultiLineString, $TargetSrid) AS simplified_geom
    FROM $TargetSchema.$TargetTable
) AS simplified
WHERE NOT ST_IsEmpty(simplified_geom);

ALTER TABLE $TargetSchema.$SimplifiedTable
    ADD PRIMARY KEY (centerline_id);
CREATE INDEX ${SimplifiedTable}_geom_gix
    ON $TargetSchema.$SimplifiedTable USING gist (geom);
CREATE INDEX ${SimplifiedTable}_hash_idx
    ON $TargetSchema.$SimplifiedTable (feature_hash);

COMMENT ON TABLE $RawSchema.$RawTable IS
    'Raw merged NGII digital topographic road-centerline layer loaded by scripts/import_ngii_road_centerline.ps1';
COMMENT ON TABLE $TargetSchema.$TargetTable IS
    'Nationwide NGII road-centerline single-sheet table normalized to EPSG:$TargetSrid';
COMMENT ON TABLE $TargetSchema.$SimplifiedTable IS
    'Simplified nationwide NGII road-centerline table for fast safety-zone spatial matching and QGIS review';

ANALYZE $RawSchema.$RawTable;
ANALYZE $TargetSchema.$TargetTable;
ANALYZE $TargetSchema.$SimplifiedTable;

SELECT '$RawSchema.$RawTable' AS table_name, COUNT(*) AS row_count FROM $RawSchema.$RawTable
UNION ALL
SELECT '$TargetSchema.$TargetTable', COUNT(*) FROM $TargetSchema.$TargetTable
UNION ALL
SELECT '$TargetSchema.$SimplifiedTable', COUNT(*) FROM $TargetSchema.$SimplifiedTable;
"@

Set-Content -Path $sqlPath -Value $sql -Encoding UTF8

Write-Host "Creating normalized and simplified PostGIS tables ..."
& psql $DatabaseUrl -v "ON_ERROR_STOP=1" -f $sqlPath
if ($LASTEXITCODE -ne 0) {
    throw "PostGIS registration SQL failed."
}

Write-Host "Done. Registered $TargetSchema.$TargetTable and $TargetSchema.$SimplifiedTable."
