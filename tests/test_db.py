from safety_zone_monitor.db import sanitize_error_message


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
