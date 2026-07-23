from safety_zone_monitor.diff import (
    ExistingFacilityPoint,
    PointChangeType,
    detect_point_changes,
)
from safety_zone_monitor.normalize import FacilityPointRecord, normalize_facility_points
from tests.test_normalize import sample_item


def point_record(**updates: str) -> FacilityPointRecord:
    values = {"fturGeomVl": "POINT (1 2)", **updates}
    records = normalize_facility_points(sample_item(**values))
    assert len(records) == 1
    return records[0]


def existing(record: FacilityPointRecord) -> ExistingFacilityPoint:
    return ExistingFacilityPoint(
        facility_id=record.facility_id,
        point_ordinal=record.point_ordinal,
        attr_hash=record.attr_hash,
        point_hash=record.point_hash,
        data_hash=record.data_hash,
        snapshot=record.snapshot(),
    )


def test_detects_all_point_change_states() -> None:
    unchanged = point_record(ptznMngNo="A")
    attr_before = point_record(ptznMngNo="B", trgtFcltNm="Before")
    attr_after = point_record(ptznMngNo="B", trgtFcltNm="After")
    point_before = point_record(ptznMngNo="C")
    point_after = point_record(ptznMngNo="C", fturGeomVl="POINT (3 4)")
    both_before = point_record(ptznMngNo="D", trgtFcltNm="Before")
    both_after = point_record(
        ptznMngNo="D", trgtFcltNm="After", fturGeomVl="POINT (5 6)"
    )
    new = point_record(ptznMngNo="E")
    missing = point_record(ptznMngNo="F")

    current = {
        (record.facility_id, record.point_ordinal): existing(record)
        for record in (
            unchanged,
            attr_before,
            point_before,
            both_before,
            missing,
        )
    }
    result = detect_point_changes(
        [unchanged, attr_after, point_after, both_after, new], current
    )

    assert result.count(PointChangeType.NEW) == 1
    assert result.count(PointChangeType.ATTRIBUTE_CHANGED) == 1
    assert result.count(PointChangeType.POINT_CHANGED) == 1
    assert result.count(PointChangeType.POINT_ATTRIBUTE_CHANGED) == 1
    assert result.count(PointChangeType.UNCHANGED) == 1
    assert result.count(PointChangeType.MISSING) == 1


def test_missing_point_is_deleted_when_zone_group_was_deleted() -> None:
    deleted = point_record(ptznMngNo="F", rprsPtznMngNo="GROUP-1")
    current = {(deleted.facility_id, deleted.point_ordinal): existing(deleted)}

    result = detect_point_changes([], current, deleted_zone_group_ids={"GROUP-1"})

    assert result.count(PointChangeType.DELETED) == 1
    assert result.count(PointChangeType.MISSING) == 0
