import pytest

from safety_zone_monitor.pipeline import _validate_response_coverage


def test_response_coverage_accepts_every_requested_district() -> None:
    _validate_response_coverage(
        [{"sggCd": "11110"}, {"sggCd": "11140"}], ("11110", "11140")
    )


def test_response_coverage_blocks_partial_mass_deletion() -> None:
    with pytest.raises(RuntimeError, match="11140"):
        _validate_response_coverage([{"sggCd": "11110"}], ("11110", "11140"))


def test_response_coverage_allows_declared_empty_districts() -> None:
    _validate_response_coverage(
        [{"sggCd": "11110"}],
        ("11110", "28125"),
        empty_result_sgg_codes={"28125"},
    )
