import pytest

from safety_zone_monitor.api import ApiError, SafetyZoneApiClient, extract_items, response_body


def test_extract_items_accepts_single_object() -> None:
    body = {"items": {"item": {"ptznMngNo": "A-1"}}}
    assert extract_items(body) == [{"ptznMngNo": "A-1"}]


def test_response_body_accepts_success() -> None:
    payload = {"response": {"header": {"resultCode": "00"}, "body": {"totalCount": 0}}}
    assert response_body(payload)["totalCount"] == 0


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
    with pytest.raises(ApiError, match="Incomplete response"):
        client.fetch_district("11110")
