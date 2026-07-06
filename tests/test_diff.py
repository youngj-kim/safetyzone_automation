from safety_zone_monitor.diff import ChangeType, ExistingZone, detect_changes
from safety_zone_monitor.normalize import normalize_item
from tests.test_normalize import sample_item


def test_detects_all_four_states() -> None:
    unchanged = normalize_item(sample_item(ptznMngNo="A"))
    updated = normalize_item(sample_item(ptznMngNo="B", trgtFcltNm="변경 후"))
    new = normalize_item(sample_item(ptznMngNo="C"))
    missing = normalize_item(sample_item(ptznMngNo="D"))
    before_updated = normalize_item(sample_item(ptznMngNo="B", trgtFcltNm="변경 전"))
    assert all([unchanged, updated, new, missing, before_updated])

    current = {
        unchanged.zone_key: ExistingZone(
            unchanged.zone_key, unchanged.data_hash, unchanged.snapshot()
        ),
        updated.zone_key: ExistingZone(
            updated.zone_key, before_updated.data_hash, before_updated.snapshot()
        ),
        missing.zone_key: ExistingZone(missing.zone_key, missing.data_hash, missing.snapshot()),
    }
    result = detect_changes([unchanged, updated, new], current)

    assert result.count(ChangeType.NEW) == 1
    assert result.count(ChangeType.UPDATED) == 1
    assert result.count(ChangeType.UNCHANGED) == 1
    assert result.count(ChangeType.MISSING) == 1
