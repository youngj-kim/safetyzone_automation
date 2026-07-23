import uuid

from safety_zone_monitor.db import RunSummary
from safety_zone_monitor.diff import DiffResult, detect_point_changes
from safety_zone_monitor.normalize import normalize_facility_points
from safety_zone_monitor.notify import format_summary
from tests.test_normalize import sample_item


def test_point_only_change_is_in_notification_summary() -> None:
    point = normalize_facility_points(
        sample_item(fturGeomVl="POINT (1 2)", trgtFcltNm="Point-only facility")
    )[0]
    summary = RunSummary(
        run_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        fetched_count=1,
        polygon_count=0,
        facility_point_count=1,
        point_only_record_count=1,
        skipped_non_polygon_count=0,
        skipped_inactive_count=0,
        diff=DiffResult((), ()),
        point_diff=detect_point_changes([point], {}),
    )

    message = format_summary(summary)
    assert summary.has_changes is True
    assert summary.change_count == 1
    assert "[시설 Point]" in message
    assert "삭제 0 / 누락 0" in message
    assert "Point NEW: Point-only facility (11110)" in message
