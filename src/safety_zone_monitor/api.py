from __future__ import annotations

import logging
import math
import time
from collections.abc import Mapping
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class ApiError(RuntimeError):
    pass


def response_body(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    response = payload.get("response")
    if not isinstance(response, Mapping):
        raise ApiError("Open API response does not contain a response object")
    header = response.get("header", {})
    if isinstance(header, Mapping):
        result_code = str(header.get("resultCode", "00"))
        if result_code not in {"00", "0"}:
            raise ApiError(f"Open API error {result_code}: {header.get('resultMsg', 'unknown')}")
    body = response.get("body")
    if not isinstance(body, Mapping):
        raise ApiError("Open API response does not contain a body object")
    return body


def extract_items(body: Mapping[str, Any]) -> list[dict[str, Any]]:
    items_container = body.get("items", {})
    if not isinstance(items_container, Mapping):
        return []
    items = items_container.get("item", [])
    if isinstance(items, Mapping):
        return [dict(items)]
    if isinstance(items, list):
        return [dict(item) for item in items if isinstance(item, Mapping)]
    return []


class SafetyZoneApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        service_key: str,
        num_rows: int = 1000,
        timeout_seconds: float = 30.0,
        delay_seconds: float = 0.2,
        allow_empty_result: bool = False,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url
        self.service_key = service_key
        self.num_rows = num_rows
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = delay_seconds
        self.allow_empty_result = allow_empty_result
        self.empty_result_sgg_codes: set[str] = set()
        self.session = session or requests.Session()
        if session is None:
            retry = Retry(
                total=3,
                connect=3,
                read=3,
                status=3,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset({"GET"}),
                respect_retry_after_header=True,
            )
            self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({"User-Agent": "safety-zone-monitor/0.1"})

    def _fetch_page(self, sgg_code: str, page_no: int) -> Mapping[str, Any]:
        params = {
            "serviceKey": self.service_key,
            "numOfRows": self.num_rows,
            "pageNo": page_no,
            "sggCd": sgg_code,
        }
        try:
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ApiError(f"Failed to fetch {sgg_code} page {page_no}: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise ApiError(f"Unexpected response type for {sgg_code} page {page_no}")
        try:
            return response_body(payload)
        except ApiError as exc:
            if self.allow_empty_result and "ERR_03" in str(exc):
                self.empty_result_sgg_codes.add(sgg_code)
                logger.info("Fetched district=%s page=%s/0 items=0", sgg_code, page_no)
                return {
                    "totalCount": 0,
                    "numOfRows": self.num_rows,
                    "items": {"item": []},
                }
            raise

    def fetch_district(self, sgg_code: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_no = 1
        total_pages: int | None = None
        while total_pages is None or page_no <= total_pages:
            body = self._fetch_page(sgg_code, page_no)
            items = extract_items(body)
            records.extend(items)
            if "totalCount" not in body:
                raise ApiError(f"Response for {sgg_code} is missing totalCount")
            total_count = int(body["totalCount"])
            actual_page_size = int(body.get("numOfRows") or self.num_rows)
            total_pages = max(1, math.ceil(total_count / max(actual_page_size, 1)))
            logger.info(
                "Fetched district=%s page=%s/%s items=%s",
                sgg_code,
                page_no,
                total_pages,
                len(items),
            )
            if not items and len(records) < total_count:
                raise ApiError(
                    f"Incomplete response for {sgg_code}: expected {total_count}, "
                    f"received {len(records)}"
                )
            if len(records) >= total_count:
                break
            page_no += 1
            if page_no <= total_pages and self.delay_seconds:
                time.sleep(self.delay_seconds)
        if total_pages is not None and len(records) < total_count:
            raise ApiError(
                f"Incomplete response for {sgg_code}: expected {total_count}, "
                f"received {len(records)}"
            )
        return records

    def fetch_all(self, sgg_codes: tuple[str, ...]) -> list[dict[str, Any]]:
        all_records: list[dict[str, Any]] = []
        for index, sgg_code in enumerate(sgg_codes):
            all_records.extend(self.fetch_district(sgg_code))
            if index < len(sgg_codes) - 1 and self.delay_seconds:
                time.sleep(self.delay_seconds)
        return all_records
