import pytest
import requests

from safety_zone_monitor.api import (
    ApiError,
    SafetyZoneApiClient,
    _classify_request_exception,
    extract_items,
    response_body,
)


def test_extract_items_accepts_single_object() -> None:
    body = {"items": {"item": {"ptznMngNo": "A-1"}}}
    assert extract_items(body) == [{"ptznMngNo": "A-1"}]


def test_response_body_accepts_success() -> None:
    payload = {"response": {"header": {"resultCode": "00"}, "body": {"totalCount": 0}}}
    assert response_body(payload)["totalCount"] == 0


def test_response_body_classifies_empty_result() -> None:
    payload = {
        "response": {
            "header": {"resultCode": "ERR_03", "resultMsg": "조회된 데이터가 없습니다."},
            "body": {},
        }
    }

    with pytest.raises(ApiError) as exc_info:
        response_body(payload)

    assert exc_info.value.category == "EMPTY_RESULT"


def test_response_body_classifies_auth_error() -> None:
    payload = {
        "response": {
            "header": {
                "resultCode": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
                "resultMsg": "SERVICE KEY IS NOT REGISTERED ERROR.",
            },
            "body": {},
        }
    }

    with pytest.raises(ApiError) as exc_info:
        response_body(payload)

    assert exc_info.value.category == "AUTH_ERROR"


class StubClient(SafetyZoneApiClient):
    def __init__(self, pages: list[dict]) -> None:
        super().__init__(base_url="https://example.invalid", service_key="test", delay_seconds=0)
        self.pages = pages

    def _fetch_page(self, sgg_code: str, page_no: int) -> dict:
        return self.pages[page_no - 1]


def test_incomplete_pagination_fails_instead_of_creating_missing_records() -> None:
    client = StubClient(
        [
            {"totalCount": 2, "numOfRows": 1, "items": {"item": [{"id": 1}]}},
            {"totalCount": 2, "numOfRows": 1, "items": {"item": []}},
        ]
    )
    with pytest.raises(ApiError, match="Incomplete response") as exc_info:
        client.fetch_district("11110")

    assert exc_info.value.category == "INCOMPLETE_PAGE"


def test_invalid_pagination_values_are_malformed_response() -> None:
    client = StubClient(
        [
            {"totalCount": "not-a-number", "numOfRows": 1, "items": {"item": []}},
        ]
    )

    with pytest.raises(ApiError) as exc_info:
        client.fetch_district("11110")

    assert exc_info.value.category == "MALFORMED_RESPONSE"


class EmptyResultClient(SafetyZoneApiClient):
    def __init__(self) -> None:
        super().__init__(
            base_url="https://example.invalid",
            service_key="test",
            delay_seconds=0,
            allow_empty_result=True,
        )

    def _fetch_page(self, sgg_code: str, page_no: int) -> dict:
        self.empty_result_sgg_codes.add(sgg_code)
        return {"totalCount": 0, "numOfRows": 1000, "items": {"item": []}}


def test_empty_result_district_is_recorded_and_returns_no_records() -> None:
    client = EmptyResultClient()

    assert client.fetch_district("28125") == []
    assert client.empty_result_sgg_codes == {"28125"}


class ResponseStub:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def test_http_429_request_error_is_rate_limit() -> None:
    error = requests.HTTPError("too many requests")
    error.response = ResponseStub(429)

    assert _classify_request_exception(error) == "RATE_LIMIT"
