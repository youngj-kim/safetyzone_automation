from safety_zone_monitor.db import classify_sgg_coverage, sanitize_error_message


def test_sanitize_error_message_redacts_sensitive_query_params() -> None:
    message = (
        "Failed url: /get?serviceKey=abc123&numOfRows=1000 "
        "callback?token=secret-value&sggCd=11110"
    )

    sanitized = sanitize_error_message(message)

    assert "abc123" not in sanitized
    assert "secret-value" not in sanitized
    assert "serviceKey=[REDACTED]" in sanitized
    assert "token=[REDACTED]" in sanitized


def test_sanitize_error_message_allows_empty_value() -> None:
    assert sanitize_error_message(None) is None


def test_classify_sgg_coverage_downgrades_expected_codes_without_raw_rows() -> None:
    coverage = classify_sgg_coverage(
        expected_sgg_codes=("11110", "28125", "41110", "41111"),
        current_sgg_codes=("11110", "41111"),
        raw_sgg_codes=("11110", "41111"),
    )

    assert coverage["critical"] == ()
    assert coverage["without_raw_rows"] == ("28125", "41110")


def test_classify_sgg_coverage_keeps_missing_raw_codes_critical() -> None:
    coverage = classify_sgg_coverage(
        expected_sgg_codes=("11110", "28125"),
        current_sgg_codes=("11110",),
        raw_sgg_codes=("11110", "28125"),
    )

    assert coverage["critical"] == ("28125",)
    assert coverage["without_raw_rows"] == ()
