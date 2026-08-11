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
    def __init__(
        self,
        message: str,
        *,
        category: str = "UNKNOWN",
        sgg_code: str | None = None,
        page_no: int | None = None,
    ) -> None:
        self.message = message
        self.category = category
        self.sgg_code = sgg_code
        self.page_no = page_no
        context = []
        if sgg_code:
            context.append(f"sgg={sgg_code}")
        if page_no is not None:
            context.append(f"page={page_no}")
        prefix = f"[{category}]"
        if context:
            prefix += f"[{', '.join(context)}]"
        super().__init__(f"{prefix} {message}")


def _classify_open_api_error(result_code: str, result_message: str) -> str:
    upper = f"{result_code} {result_message}".upper()
    if "ERR_03" in upper or "NO DATA" in upper or "조회된 데이터가 없습니다" in result_message:
        return "EMPTY_RESULT"
    if any(token in upper for token in ("SERVICE_KEY", "AUTH", "KEY", "인증", "SERVICEKEY")):
        return "AUTH_ERROR"
    if any(token in upper for token in ("LIMIT", "LIMITED", "429", "초과", "제한")):
        return "RATE_LIMIT"
    return "OPEN_API_ERROR"


def _classify_request_exception(exc: requests.RequestException) -> str:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code == 429:
        return "RATE_LIMIT"
    if status_code in {401, 403}:
        return "AUTH_ERROR"
    if isinstance(exc, requests.Timeout):
        return "TIMEOUT"
    if isinstance(exc, requests.ConnectionError):
        return "NETWORK_ERROR"
    if status_code and 500 <= status_code <= 599:
        return "SERVER_ERROR"
    if status_code and 400 <= status_code <= 499:
        return "HTTP_CLIENT_ERROR"
    return "NETWORK_ERROR"


def response_body(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    response = payload.get("response")
    if not isinstance(response, Mapping):
        raise ApiError(
            "Open API response does not contain a response object",
            category="MALFORMED_RESPONSE",
        )
    header = response.get("header", {})
    if isinstance(header, Mapping):
        result_code = str(header.get("resultCode", "00"))
        if result_code not in {"00", "0"}:
            result_message = str(header.get("resultMsg", "unknown"))
            raise ApiError(
                f"Open API error {result_code}: {result_message}",
                category=_classify_open_api_error(result_code, result_message),
            )
    body = response.get("body")
    if not isinstance(body, Mapping):
        raise ApiError(
            "Open API response does not contain a body object",
            category="MALFORMED_RESPONSE",
        )
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
        rate_limit_max_retries: int = 4,
        rate_limit_retry_seconds: float = 60.0,
        allow_empty_result: bool = False,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url
        self.service_key = service_key
        self.num_rows = num_rows
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = delay_seconds
        self.rate_limit_max_retries = rate_limit_max_retries
        self.rate_limit_retry_seconds = rate_limit_retry_seconds
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

    def _request_page(self, params: dict[str, object]) -> requests.Response:
        return self.session.get(
            self.base_url,
            params=params,
            timeout=self.timeout_seconds,
        )

    def _fetch_page_once(self, sgg_code: str, page_no: int) -> Mapping[str, Any]:
        params = {
            "serviceKey": self.service_key,
            "numOfRows": self.num_rows,
            "pageNo": page_no,
            "sggCd": sgg_code,
        }
        try:
            response = self._request_page(params)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ApiError(
                f"Failed to fetch {sgg_code} page {page_no}: {exc}",
                category=_classify_request_exception(exc),
                sgg_code=sgg_code,
                page_no=page_no,
            ) from exc
        except ValueError as exc:
            raise ApiError(
                f"Failed to parse JSON for {sgg_code} page {page_no}: {exc}",
                category="MALFORMED_RESPONSE",
                sgg_code=sgg_code,
                page_no=page_no,
            ) from exc
        if not isinstance(payload, Mapping):
            raise ApiError(
                f"Unexpected response type for {sgg_code} page {page_no}",
                category="MALFORMED_RESPONSE",
                sgg_code=sgg_code,
                page_no=page_no,
            )
        try:
            return response_body(payload)
        except ApiError as exc:
            if self.allow_empty_result and exc.category == "EMPTY_RESULT":
                self.empty_result_sgg_codes.add(sgg_code)
                logger.info("Fetched district=%s page=%s/0 items=0", sgg_code, page_no)
                return {
                    "totalCount": 0,
                    "numOfRows": self.num_rows,
                    "items": {"item": []},
                }
            raise ApiError(
                exc.message,
                category=exc.category,
                sgg_code=sgg_code,
                page_no=page_no,
            ) from exc

    def _fetch_page(self, sgg_code: str, page_no: int) -> Mapping[str, Any]:
        attempt = 0
        while True:
            try:
                return self._fetch_page_once(sgg_code, page_no)
            except ApiError as exc:
                if exc.category != "RATE_LIMIT" or attempt >= self.rate_limit_max_retries:
                    raise
                wait_seconds = self.rate_limit_retry_seconds * (attempt + 1)
                logger.warning(
                    "Rate limited while fetching district=%s page=%s; "
                    "retrying in %.1f seconds (%s/%s)",
                    sgg_code,
                    page_no,
                    wait_seconds,
                    attempt + 1,
                    self.rate_limit_max_retries,
                )
                time.sleep(wait_seconds)
                attempt += 1

    def fetch_district(self, sgg_code: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_no = 1
        total_pages: int | None = None
        while total_pages is None or page_no <= total_pages:
            body = self._fetch_page(sgg_code, page_no)
            items = extract_items(body)
            records.extend(items)
            if "totalCount" not in body:
                raise ApiError(
                    f"Response for {sgg_code} is missing totalCount",
                    category="MALFORMED_RESPONSE",
                    sgg_code=sgg_code,
                    page_no=page_no,
                )
            try:
                total_count = int(body["totalCount"])
                actual_page_size = int(body.get("numOfRows") or self.num_rows)
            except (TypeError, ValueError) as exc:
                raise ApiError(
                    f"Response for {sgg_code} has invalid pagination values",
                    category="MALFORMED_RESPONSE",
                    sgg_code=sgg_code,
                    page_no=page_no,
                ) from exc
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
                    f"received {len(records)}",
                    category="INCOMPLETE_PAGE",
                    sgg_code=sgg_code,
                    page_no=page_no,
                )
            if len(records) >= total_count:
                break
            page_no += 1
            if page_no <= total_pages and self.delay_seconds:
                time.sleep(self.delay_seconds)
        if total_pages is not None and len(records) < total_count:
            raise ApiError(
                f"Incomplete response for {sgg_code}: expected {total_count}, "
                f"received {len(records)}",
                category="INCOMPLETE_PAGE",
                sgg_code=sgg_code,
            )
        return records

    def fetch_all(self, sgg_codes: tuple[str, ...]) -> list[dict[str, Any]]:
        all_records: list[dict[str, Any]] = []
        for index, sgg_code in enumerate(sgg_codes):
            all_records.extend(self.fetch_district(sgg_code))
            if index < len(sgg_codes) - 1 and self.delay_seconds:
                time.sleep(self.delay_seconds)
        return all_records