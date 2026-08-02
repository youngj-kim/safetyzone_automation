param(
    [string]$ArchiveMonth = (Get-Date -Format "yyyy-MM"),
    [string]$ArchiveDatabaseUrl = $env:MONTHLY_ARCHIVE_DATABASE_URL,
    [string]$ServiceKey = $env:OPEN_API_SERVICE_KEY,
    [string]$SggCodesFile = "config/sgg_codes_nationwide.txt",
    [string]$OutputRoot = "exports\monthly_raw_archive",
    [switch]$ReplaceArchiveData,
    [switch]$AllowRemoteDatabase
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
        throw "Missing required command '$Name'. Install PostgreSQL client tools and add them to PATH."
    }
}

function Test-RemoteDatabaseUrl {
    param([string]$DatabaseUrl)
    $remotePatterns = @(
        "supabase.com",
        "amazonaws.com",
        "azure.com",
        "googleapis.com",
        "neon.tech",
        "render.com"
    )
    foreach ($pattern in $remotePatterns) {
        if ($DatabaseUrl -like "*$pattern*") {
            return $true
        }
    }
    return $false
}

function Invoke-Checked {
    param(
        [string]$Description,
        [scriptblock]$Command
    )
    Write-Host ""
    Write-Host "==> $Description"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

if ([string]::IsNullOrWhiteSpace($ArchiveDatabaseUrl)) {
    $ArchiveDatabaseUrl = Read-DotEnvValue -Key "MONTHLY_ARCHIVE_DATABASE_URL"
}
if ([string]::IsNullOrWhiteSpace($ServiceKey)) {
    $ServiceKey = Read-DotEnvValue -Key "OPEN_API_SERVICE_KEY"
}
if ([string]::IsNullOrWhiteSpace($ArchiveDatabaseUrl)) {
    throw "Missing MONTHLY_ARCHIVE_DATABASE_URL. Set it in the environment, .env, or pass -ArchiveDatabaseUrl."
}
if ([string]::IsNullOrWhiteSpace($ServiceKey)) {
    throw "Missing OPEN_API_SERVICE_KEY. Set it in the environment, .env, or pass -ServiceKey."
}
if (-not (Test-Path $SggCodesFile)) {
    throw "SGG codes file not found: $SggCodesFile"
}
if ((Test-RemoteDatabaseUrl -DatabaseUrl $ArchiveDatabaseUrl) -and -not $AllowRemoteDatabase) {
    throw "Archive target looks like a remote/cloud database. Use a local archive DB, or pass -AllowRemoteDatabase intentionally."
}

Require-Command "pg_dump"
Require-Command "psql"

$pythonPath = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    $pythonPath = "python"
}

$archiveDir = Join-Path $OutputRoot $ArchiveMonth
$summaryPath = Join-Path $archiveDir "summary.json"
$dumpPath = Join-Path $archiveDir "safetyzone_raw_snapshot.dump"
$readmePath = Join-Path $archiveDir "README.md"
$logPath = Join-Path $archiveDir "archive.log"
New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null

$oldDatabaseUrl = $env:DATABASE_URL
$oldServiceKey = $env:OPEN_API_SERVICE_KEY
$oldSggCodesFile = $env:SGG_CODES_FILE
$oldDbMode = $env:SAFETYZONE_DB_MODE
$oldLogLevel = $env:LOG_LEVEL

try {
    $env:DATABASE_URL = $ArchiveDatabaseUrl
    $env:OPEN_API_SERVICE_KEY = $ServiceKey
    $env:SGG_CODES_FILE = $SggCodesFile
    $env:SAFETYZONE_DB_MODE = "cloud"
    if ([string]::IsNullOrWhiteSpace($env:LOG_LEVEL)) {
        $env:LOG_LEVEL = "INFO"
    }

    Start-Transcript -Path $logPath -Force | Out-Null

    Invoke-Checked "Initialize archive operational schema" {
        & $pythonPath -m safety_zone_monitor init-ops-db
    }

    $existingRows = & psql $ArchiveDatabaseUrl -At -v "ON_ERROR_STOP=1" -c "SELECT count(*) FROM ops.pipeline_run;"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect archive database row count."
    }
    $existingRows = [int]$existingRows
    if ($existingRows -gt 0) {
        if (-not $ReplaceArchiveData) {
            throw "Archive database already has $existingRows pipeline run row(s). Re-run with -ReplaceArchiveData to refresh this archive DB."
        }
        Invoke-Checked "Clear existing archive operational data" {
            & psql $ArchiveDatabaseUrl -v "ON_ERROR_STOP=1" -c @"
TRUNCATE TABLE
    analysis.zone_facility_point_absence,
    analysis.zone_facility_point_change_event,
    analysis.zone_facility_point_current,
    analysis.zone_facility_point_snapshot,
    ops.notification_log,
    analysis.zone_change_event,
    analysis.zone_current,
    analysis.zone_snapshot,
    raw.police_zone_item_snapshot,
    raw.police_zone_api_run,
    ops.pipeline_run
RESTART IDENTITY CASCADE;
"@
        }
    }

    Invoke-Checked "Run nationwide monthly baseline archive collection" {
        & $pythonPath -m safety_zone_monitor run --baseline --summary-json $summaryPath
    }

    Invoke-Checked "Create monthly archive dump" {
        & pg_dump $ArchiveDatabaseUrl `
            --schema=ops `
            --schema=raw `
            --schema=analysis `
            --format=custom `
            --file=$dumpPath
    }

    $summary = Get-Content $summaryPath -Raw | ConvertFrom-Json
    $generatedAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss KST")
    $readme = @"
# Safety Zone Monthly Raw Archive $ArchiveMonth

Generated at: $generatedAt

Run ID: $($summary.run_id)
Fetched records: $($summary.fetched_count)
Polygon records: $($summary.polygon_count)
Facility point records: $($summary.facility_point_count)

Files:

- summary.json: monthly baseline collection summary
- safetyzone_raw_snapshot.dump: PostgreSQL custom-format dump for ops/raw/analysis archive schemas
- archive.log: local execution log

Restore example:

````powershell
createdb safetyzone_archive_restore
pg_restore --dbname=safetyzone_archive_restore --clean --if-exists safetyzone_raw_snapshot.dump
````
"@
    Set-Content -Path $readmePath -Value $readme -Encoding UTF8

    Write-Host ""
    Write-Host "Monthly archive completed."
    Write-Host "Archive directory: $archiveDir"
    Write-Host "Dump file: $dumpPath"
}
finally {
    try {
        Stop-Transcript | Out-Null
    }
    catch {
    }
    $env:DATABASE_URL = $oldDatabaseUrl
    $env:OPEN_API_SERVICE_KEY = $oldServiceKey
    $env:SGG_CODES_FILE = $oldSggCodesFile
    $env:SAFETYZONE_DB_MODE = $oldDbMode
    $env:LOG_LEVEL = $oldLogLevel
}
