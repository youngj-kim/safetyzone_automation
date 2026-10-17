import importlib.util
from datetime import UTC, datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/export_monthly_statistics.py"
spec = importlib.util.spec_from_file_location("monthly_statistics", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def run(identifier, codes, count, date="2026-09-30T00:00:00+00:00", status="SUCCESS"):
    return {
        "run_id": identifier, "started_at": date, "finished_at": date, "status": status,
        "monitored_sgg_codes": codes, "fetched_count": count,
        "polygon_count": count, "facility_point_count": count,
    }


def months(rows, codes=("A", "B")):
    return module.reconstruct_months(
        rows, codes, now=datetime(2026, 10, 17, tzinfo=UTC)
    )["months"]


def test_latest_disjoint_scopes_do_not_double_count_repeated_runs():
    result = months([
        run("old", ["A", "B"], 100, "2026-09-01T00:00:00+00:00"),
        run("a-old", ["A"], 9, "2026-09-20T00:00:00+00:00"),
        run("a", ["A"], 10), run("b", ["B"], 20),
        run("failed", ["A", "B"], 999, status="FAILED"),
    ])[0]
    assert result["polygon_count"] == 30
    assert set(result["source_run_ids"]) == {"a", "b"}
    assert result["successful_runs"] == 4
    assert result["failed_runs"] == 1


def test_partial_new_scope_falls_back_to_complete_national_run():
    result = months([
        run("full", ["A", "B"], 30, "2026-09-20T00:00:00+00:00"),
        run("partial", ["A"], 11),
    ])[0]
    assert result["source_run_ids"] == ["full"]
    assert result["polygon_count"] == 30


def test_missing_districts_do_not_produce_fake_national_total():
    result = months([run("partial", ["A"], 10)])[0]
    assert result["status"] == "INCOMPLETE_SCOPE"
    assert result["polygon_count"] is None
    assert result["covered_sgg_count"] == 1


def test_korean_month_boundary_and_current_month_status():
    result = months([run("boundary", ["A", "B"], 10, "2026-09-30T15:01:00+00:00")])[0]
    assert result["month"] == "2026-10"
    assert result["status"] == "MONTH_TO_DATE"
    assert result["period_end"] == "2026-10-17"
