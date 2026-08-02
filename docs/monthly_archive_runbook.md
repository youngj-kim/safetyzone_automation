# Monthly Raw Archive Runbook

Baseline date: 2026-08-02

## Purpose

The daily online service uses Supabase Free as a lightweight operational database. It keeps
current safety-zone objects, change events, monitoring runs, and notifications.

The monthly raw archive is separate. It stores a full nationwide API snapshot in a local
PostgreSQL/PostGIS database and exports it as a `pg_dump` file for long-term evidence and
reproducibility.

## Recommended Target

Use a separate local database:

```text
safetyzone_archive
```

Do not point the monthly archive script at Supabase. The script blocks common cloud database
hosts by default to reduce accidental storage growth in the online DB.

## Required Local Setup

- PostgreSQL/PostGIS local database, for example `safetyzone_archive`
- PostgreSQL client tools on `PATH`: `psql`, `pg_dump`
- Python virtual environment for this repository
- `.env` or shell variables with:

```powershell
MONTHLY_ARCHIVE_DATABASE_URL=postgresql://postgres:password@localhost:5433/safetyzone_archive
OPEN_API_SERVICE_KEY=your_public_data_api_key
```

`MONTHLY_ARCHIVE_DATABASE_URL` is intentionally separate from `DATABASE_URL` so the monthly
archive does not accidentally use Supabase.

## Manual Run

Run this first for the first one or two months.

```powershell
.\scripts\archive_monthly_snapshot.ps1 -ArchiveMonth 2026-08
```

If the archive DB already contains an older test/archive run and you want to refresh it:

```powershell
.\scripts\archive_monthly_snapshot.ps1 -ArchiveMonth 2026-08 -ReplaceArchiveData
```

The output is written under:

```text
exports/monthly_raw_archive/YYYY-MM/
```

Expected files:

- `summary.json`
- `safetyzone_raw_snapshot.dump`
- `README.md`
- `archive.log`

The script also updates the public aggregate index:

```text
dashboard/data/monthly_archives.json
```

This file contains counts and run metadata only. It does not include raw API payloads or database
credentials.

`exports/` is ignored by git and should remain local.

## What The Script Does

1. Reads `MONTHLY_ARCHIVE_DATABASE_URL` and `OPEN_API_SERVICE_KEY`.
2. Verifies `psql` and `pg_dump`.
3. Initializes the operational schemas with `init-ops-db`.
4. Runs nationwide collection in baseline mode.
5. Writes `summary.json`.
6. Dumps local `ops`, `raw`, and `analysis` schemas with `pg_dump --format=custom`.
7. Writes a small README beside the dump.
8. Updates `dashboard/data/monthly_archives.json` for the monthly stats page.

The script sets `SAFETYZONE_DB_MODE=cloud` internally because the archive database contains
only the protection-zone operational subset, not the local standard-node/NGII road network.

## Restore Check

Use a separate restore database when testing.

```powershell
createdb safetyzone_archive_restore
pg_restore --dbname=safetyzone_archive_restore --clean --if-exists exports\monthly_raw_archive\2026-08\safetyzone_raw_snapshot.dump
```

Then inspect counts with `psql` or the project CLI.

## Windows Task Scheduler

After manual runs are stable, register a monthly task:

```powershell
.\scripts\register_monthly_archive_task.ps1 -DayOfMonth 1 -At "11:00"
```

The registered task passes `-ReplaceArchiveData` by default. This keeps `safetyzone_archive` as a
monthly working DB and prevents rows from multiple months being mixed in one dump. Use
`-KeepExistingArchiveData` only for a deliberately separate archive DB.

This creates a Windows scheduled task named:

```text
SafetyZone Monthly Raw Archive
```

Recommended timing is after the daily online chunks have finished, for example the first day of
each month at 11:00 KST.

## Operating Policy

- Daily GitHub Actions + Supabase: operational monitoring and dashboard.
- Monthly local archive: full raw snapshot preservation.
- Standard node link, NGII road centerline, and matching review datasets stay local and are not
  part of the Supabase archive policy.

## Failure Handling

If API 429 occurs, do not retry repeatedly on the same day. Keep the failed `archive.log`, then
rerun the next day with the same `ArchiveMonth` and `-ReplaceArchiveData`.

If `pg_dump` fails, keep the local archive DB as-is and rerun only after checking disk space and
PostgreSQL client availability.

## Dashboard Publication

The monthly stats page is:

```text
dashboard/monthly.html
```

After a successful monthly archive, commit and push `dashboard/data/monthly_archives.json` so
GitHub Pages can show the new monthly statistics. The raw dump remains under `exports/` and is not
committed.
