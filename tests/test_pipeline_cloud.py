from __future__ import annotations

import uuid
from types import SimpleNamespace

from safety_zone_monitor.config import Settings
from safety_zone_monitor.normalize import NormalizationResult
from safety_zone_monitor.pipeline import run_pipeline


def test_cloud_pipeline_audits_without_running_migrations(monkeypatch) -> None:
    calls: list[str] = []

    class FakeRepository:
        def __init__(self, database_url: str) -> None:
            assert database_url == "postgresql://example"

        def audit_operational_contract(self) -> dict[str, object]:
            calls.append("audit")
            return {"required_objects": {"ops.pipeline_run": True}}

        def migrate(self, *, operational_only: bool = False) -> None:
            calls.append(f"migrate:{operational_only}")

        def create_run(self, sgg_codes, api_url):
            calls.append("create_run")
            return uuid.uuid4()

        def apply_run(self, **kwargs):
            calls.append("apply_run")
            return SimpleNamespace(
                has_changes=False,
                change_count=0,
                point_change_count=0,
                diff=SimpleNamespace(changes=[]),
                point_diff=SimpleNamespace(changes=[]),
                run_id=kwargs["run_id"],
            )

        def mark_failed(self, run_id, exc) -> None:
            calls.append("mark_failed")

    class FakeApiClient:
        empty_result_sgg_codes: set[str] = set()

        def __init__(self, **kwargs) -> None:
            pass

        def fetch_all(self, sgg_codes):
            calls.append("fetch_all")
            return [{"sggCd": "11110"}]

    monkeypatch.setattr("safety_zone_monitor.pipeline.Repository", FakeRepository)
    monkeypatch.setattr("safety_zone_monitor.pipeline.SafetyZoneApiClient", FakeApiClient)
    monkeypatch.setattr(
        "safety_zone_monitor.pipeline.normalize_records",
        lambda raw_items: NormalizationResult(
            zones=[],
            facility_points=[],
            skipped_non_polygon_count=0,
            skipped_inactive_count=0,
            point_only_record_count=0,
        ),
    )

    settings = Settings(
        service_key="service-key",
        database_url="postgresql://example",
        sgg_codes=("11110",),
        db_mode="cloud",
    )

    run_pipeline(settings)

    assert "audit" in calls
    assert "migrate:True" not in calls
    assert "migrate:False" not in calls
    assert "apply_run" in calls
