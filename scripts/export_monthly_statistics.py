"""Reconstruct monthly national counts from disjoint successful collection scopes."""

import argparse
import calendar
import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

from safety_zone_monitor.config import load_dotenv

KST = ZoneInfo("Asia/Seoul")
RUN_QUERY = """
SELECT pipeline_run_id::text AS run_id, started_at, finished_at, status,
       monitored_sgg_codes, fetched_count, polygon_count, facility_point_count
FROM ops.pipeline_run ORDER BY started_at
"""


def timestamp(value):
    return datetime.fromisoformat(value) if isinstance(value, str) else value


def reconstruct_months(rows, expected_codes, *, now=None):
    now = now or datetime.now(UTC)
    expected = set(expected_codes)
    if not rows or not expected:
        raise ValueError("Run history and expected district scope must be non-empty")
    grouped = defaultdict(list)
    for row in rows:
        moment = timestamp(row["finished_at"] or row["started_at"])
        if moment <= now:
            grouped[moment.astimezone(KST).strftime("%Y-%m")].append(row)
    months = []
    for month, records in sorted(grouped.items(), reverse=True):
        successful = sorted(
            (r for r in records if r["status"] == "SUCCESS" and r["finished_at"]),
            key=lambda r: timestamp(r["finished_at"]),
            reverse=True,
        )
        selected, covered = [], set()
        for row in successful:
            codes = set(row["monitored_sgg_codes"])
            if codes and codes <= expected and not codes & covered:
                selected.append(row)
                covered.update(codes)
        if covered != expected:
            # A full nationwide run is safer than combining overlapping scopes.
            full = next(
                (r for r in successful if set(r["monitored_sgg_codes"]) == expected),
                None,
            )
            if full:
                selected, covered = [full], set(expected)
        complete = covered == expected
        observations = [timestamp(r["finished_at"]) for r in selected]
        current = month == now.astimezone(KST).strftime("%Y-%m")
        year, number = map(int, month.split("-"))
        last_day = calendar.monthrange(year, number)[1]
        months.append({
            "month": month,
            "period_end": now.astimezone(KST).date().isoformat()
            if current else f"{month}-{last_day:02d}",
            "status": "MONTH_TO_DATE" if current and complete
            else "RECONSTRUCTED" if complete else "INCOMPLETE_SCOPE",
            "coverage_complete": complete,
            "covered_sgg_count": len(covered),
            "expected_sgg_count": len(expected),
            "observation_start": min(observations).isoformat() if observations else None,
            "generated_at": max(observations).isoformat() if observations else None,
            "source_run_ids": [r["run_id"] for r in selected],
            "fetched_count": sum(r["fetched_count"] for r in selected) if complete else None,
            "polygon_count": sum(r["polygon_count"] for r in selected) if complete else None,
            "facility_point_count": sum(r["facility_point_count"] for r in selected)
            if complete else None,
            "successful_runs": sum(r["status"] == "SUCCESS" for r in records),
            "failed_runs": sum(r["status"] == "FAILED" for r in records),
            "running_runs": sum(r["status"] == "RUNNING" for r in records),
        })
    if not months:
        raise ValueError("No historical runs at or before the requested timestamp")
    return {
        "generated_at": now.isoformat(),
        "timezone": "Asia/Seoul",
        "source": "ops.pipeline_run",
        "method": "latest_non_overlapping_successful_scopes_per_month",
        "definition": (
            "월별 마지막 성공 청크를 중복 없이 조합한 수집 건수. "
            "월말 동시 스냅샷이나 원본 백업 완료를 뜻하지 않음."
        ),
        "months": months,
    }


def read_runs():
    load_dotenv()
    with psycopg.connect(
        os.environ["DATABASE_URL"], connect_timeout=15, row_factory=dict_row
    ) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '60s'")
        rows = connection.execute(RUN_QUERY).fetchall()
        connection.rollback()
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="dashboard/data/monthly_statistics.json")
    parser.add_argument("--scope-file", default="config/sgg_codes_nationwide.txt")
    args = parser.parse_args()
    codes = [
        line.strip() for line in Path(args.scope_file).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    result = reconstruct_months(read_runs(), codes)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    print(json.dumps({"months": len(result["months"]), "output": str(target)}))


if __name__ == "__main__":
    main()
