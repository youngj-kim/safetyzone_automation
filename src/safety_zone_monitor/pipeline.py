from __future__ import annotations

import logging
from collections import Counter

from safety_zone_monitor.api import SafetyZoneApiClient
from safety_zone_monitor.config import Settings
from safety_zone_monitor.db import Repository, RunSummary
from safety_zone_monitor.normalize import normalize_records
from safety_zone_monitor.notify import Notifier

logger = logging.getLogger(__name__)


def _validate_response_coverage(
    raw_items: list[dict[str, object]], sgg_codes: tuple[str, ...]
) -> None:
    if not raw_items:
        raise RuntimeError("Open API returned zero records for all configured districts")
    response_counts = Counter(
        str(item.get("sggCd", "")).strip() for item in raw_items
    )
    empty_districts = [code for code in sgg_codes if response_counts.get(code, 0) == 0]
    if empty_districts:
        raise RuntimeError(
            "Open API returned zero records for configured district(s); "
            "current rows were not changed: " + ", ".join(empty_districts)
        )


def _verify_mobility_contract(repository: Repository) -> None:
    audit = repository.audit_host_contract()
    missing = [name for name, exists in audit["required_objects"].items() if not exists]
    if missing:
        raise RuntimeError(
            "The existing mobility_db is missing required object(s): " + ", ".join(missing)
        )
    std_link_geometry = next(
        (
            item
            for item in audit["geometry"]
            if item["schema"] == "mobility" and item["table"] == "std_link"
        ),
        None,
    )
    if not std_link_geometry or std_link_geometry["srid"] != 5179:
        raise RuntimeError("mobility.std_link must exist with SRID 5179")


def run_pipeline(settings: Settings, *, record_events: bool = True) -> RunSummary:
    repository = Repository(settings.database_url)
    _verify_mobility_contract(repository)
    repository.migrate()
    run_id = repository.create_run(settings.sgg_codes, settings.api_url)
    try:
        client = SafetyZoneApiClient(
            base_url=settings.api_url,
            service_key=settings.service_key,
            num_rows=settings.num_rows,
            timeout_seconds=settings.timeout_seconds,
            delay_seconds=settings.request_delay_seconds,
            allow_empty_result=not record_events,
        )
        raw_items = client.fetch_all(settings.sgg_codes)
        normalized = normalize_records(raw_items)

        # Never interpret an empty district response as a legitimate mass deletion.
        if record_events:
            _validate_response_coverage(raw_items, settings.sgg_codes)

        summary = repository.apply_run(
            run_id=run_id,
            sgg_codes=settings.sgg_codes,
            raw_items=raw_items,
            records=normalized.zones,
            facility_points=normalized.facility_points,
            skipped_non_polygon_count=normalized.skipped_non_polygon_count,
            skipped_inactive_count=normalized.skipped_inactive_count,
            point_only_record_count=normalized.point_only_record_count,
            record_events=record_events,
        )
    except Exception as exc:
        repository.mark_failed(run_id, exc)
        raise

    notifier = Notifier(
        slack_webhook_url=settings.slack_webhook_url,
        telegram_bot_token=settings.telegram_bot_token,
        telegram_chat_id=settings.telegram_chat_id,
    )
    if record_events and summary.has_changes:
        if notifier.configured:
            payload = {
                "change_count": summary.change_count,
                "polygon_change_count": len(summary.diff.changes),
                "point_change_count": summary.point_change_count,
                "run_id": str(summary.run_id),
            }
            try:
                sent_channels = notifier.send(summary)
                for channel in sent_channels:
                    repository.record_notification(run_id, channel, "SENT", payload)
                if sent_channels:
                    repository.mark_notification_sent(run_id)
            except Exception as exc:
                for channel in notifier.channels:
                    repository.record_notification(
                        run_id,
                        channel,
                        "FAILED",
                        payload,
                        f"{type(exc).__name__}: {exc}"[:4000],
                    )
                raise
        else:
            logger.warning("Changes were found, but no notification channel is configured")
    return summary
