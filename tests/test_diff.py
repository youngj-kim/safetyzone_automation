from safety_zone_monitor.diff import ChangeType, ExistingZone, detect_changes
from safety_zone_monitor.normalize import ZoneRecord, normalize_item
from tests.test_normalize import sample_item


def existing(record: ZoneRecord) -> ExistingZone:
    return ExistingZone(
        zone_id=record.zone_id,
        attr_hash=record.attr_hash,
        geom_hash=record.geom_hash,
        data_hash=record.data_hash,
        snapshot=record.snapshot(),
    )


def test_detects_separate_attribute_geometry_and_deleted_states() -> None:
    unchanged = normalize_item(sample_item(ptznMngNo="A"))
    attr_before = normalize_item(sample_item(ptznMngNo="B", trgtFcltNm="Before"))
    attr_after = normalize_item(sample_item(ptznMngNo="B", trgtFcltNm="After"))
    geom_before = normalize_item(sample_item(ptznMngNo="C"))
    geom_after = normalize_item(
        sample_item(ptznMngNo="C", fturGeomVl="POLYGON ((0 0, 0 20, 20 20, 20 0, 0 0))")
    )
    both_before = normalize_item(sample_item(ptznMngNo="D", trgtFcltNm="Before"))
    both_after = normalize_item(
        sample_item(
            ptznMngNo="D",
            trgtFcltNm="After",
            fturGeomVl="POLYGON ((0 0, 0 30, 30 30, 30 0, 0 0))",
        )
    )
    new = normalize_item(sample_item(ptznMngNo="E"))
    deleted = normalize_item(sample_item(ptznMngNo="F"))
    records = [
        unchanged,
        attr_before,
        attr_after,
        geom_before,
        geom_after,
        both_before,
        both_after,
        new,
        deleted,
    ]
    assert all(records)

    current = {
        unchanged.zone_id: existing(unchanged),
        attr_before.zone_id: existing(attr_before),
        geom_before.zone_id: existing(geom_before),
        both_before.zone_id: existing(both_before),
        deleted.zone_id: existing(deleted),
    }
    result = detect_changes([unchanged, attr_after, geom_after, both_after, new], current)

    assert result.count(ChangeType.NEW) == 1
    assert result.count(ChangeType.ATTRIBUTE_CHANGED) == 1
    assert result.count(ChangeType.GEOMETRY_CHANGED) == 1
    assert result.count(ChangeType.GEOMETRY_ATTRIBUTE_CHANGED) == 1
    assert result.count(ChangeType.UNCHANGED) == 1
    assert result.count(ChangeType.DELETED) == 1
