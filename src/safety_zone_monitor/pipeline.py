from __future__ import annotations

import logging

from safety_zone_monitor.api import SafetyZoneApiClient
from safety_zone_monitor.config import Settings
from safety_zone_monitor.db import Repository, RunSummary
from safety_zone_monitor.normalize import normalize_records
from safety_zone_monitor.notify import Notifier

logger = logging.getLogger(__name__)


def run_pipeline(settings: Settings) -> RunSummary:
    repository = Repository(settings.database_url)
    repository.migrate()
    run_id = repository.create_run(settings.sgg_codes)
    try:
        client = SafetyZoneApiClient(
            base_url=settings.api_url,
            service_key=settings.service_key,
            num_rows=settings.num_rows,
            timeout_seconds=settings.timeout_seconds,
            delay_seconds=settings.request_delay_seconds,
        )
        raw_items = client.fetch_all(settings.sgg_codes)
        records, skipped = normalize_records(raw_items)

        # A completely empty response is more likely an upstream/configuration failure than a
        # legitimate nationwide deletion. Refuse to create mass MISSING events in that case.
        if not raw_items:
            raise RuntimeError("Open API returned zero records for all configured districts")

        summary = repository.apply_run(
            run_id=run_id,
            sgg_codes=settings.sgg_codes,
            records=records,
            fetched_count=len(raw_items),
            skipped_non_polygon_count=skipped,
        )
    except Exception as exc:
        repository.mark_failed(run_id, exc)
        raise

    notifier = Notifier(
        slack_webhook_url=settings.slack_webhook_url,
        telegram_bot_token=settings.telegram_bot_token,
        telegram_chat_id=settings.telegram_chat_id,
    )
    if summary.diff.has_changes:
        if notifier.configured and notifier.send(summary):
            repository.mark_notification_sent(run_id)
        elif not notifier.configured:
            logger.warning("Changes were found, but no notification channel is configured")
    return summary
