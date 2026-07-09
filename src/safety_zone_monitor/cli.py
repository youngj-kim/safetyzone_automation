from __future__ import annotations

import argparse
import json
import logging

from safety_zone_monitor.config import Settings
from safety_zone_monitor.db import Repository
from safety_zone_monitor.diff import ChangeType, PointChangeType
from safety_zone_monitor.notify import Notifier
from safety_zone_monitor.pipeline import run_pipeline
from safety_zone_monitor.sgg_codes import write_sgg_codes


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safety Zone Change Monitoring System")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "audit-db", help="Read-only check of the existing mobility_db integration contract"
    )
    subparsers.add_parser(
        "init-db", help="Add raw/analysis/ops monitoring objects to the existing mobility_db"
    )
    subparsers.add_parser("run", help="Fetch, normalize, compare, store, and notify")
    subparsers.add_parser(
        "quality-report", help="Read-only quality checks for current safety-zone data"
    )
    subparsers.add_parser(
        "test-notification", help="Send a test Slack/Telegram message without touching DB data"
    )
    link_candidates = subparsers.add_parser(
        "build-link-candidates",
        help="Build protection-zone to standard-link spatial match candidates",
    )
    link_candidates.add_argument("--near-distance-m", type=float, default=5.0)
    link_candidates.add_argument("--max-distance-m", type=float, default=20.0)
    link_candidates.add_argument("--strong-intersection-length-m", type=float, default=10.0)
    link_candidates.add_argument("--strong-intersection-ratio", type=float, default=0.3)
    build_codes = subparsers.add_parser(
        "build-sgg-codes", help="Build current SGG list from the official legal-code CSV"
    )
    build_codes.add_argument("--source", required=True, help="Official legal-code CSV path")
    build_codes.add_argument(
        "--output", default="config/sgg_codes_nationwide.txt", help="Output text path"
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "build-sgg-codes":
        codes = write_sgg_codes(args.source, args.output)
        print(f"Wrote {len(codes)} current SGG codes to {args.output}.")
        return
    settings = Settings.from_env(require_pipeline=args.command == "run")
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    repository = Repository(settings.database_url)
    if args.command == "audit-db":
        print(
            json.dumps(
                repository.audit_host_contract(include_counts=True),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.command == "init-db":
        audit = repository.audit_host_contract()
        missing = [name for name, exists in audit["required_objects"].items() if not exists]
        if missing:
            raise RuntimeError("Required mobility objects are missing: " + ", ".join(missing))
        repository.migrate()
        print("Monitoring schemas are ready in the existing mobility_db.")
        return
    if args.command == "quality-report":
        report = repository.quality_report(settings.sgg_codes)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report["status"] != "PASS":
            raise SystemExit(1)
        return
    if args.command == "build-link-candidates":
        if not settings.sgg_codes:
            raise RuntimeError("SGG_CODES or SGG_CODES_FILE is required")
        repository.migrate()
        report = repository.build_link_match_candidates(
            settings.sgg_codes,
            near_distance_m=args.near_distance_m,
            max_distance_m=args.max_distance_m,
            strong_intersection_length_m=args.strong_intersection_length_m,
            strong_intersection_ratio=args.strong_intersection_ratio,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if args.command == "test-notification":
        notifier = Notifier(
            slack_webhook_url=settings.slack_webhook_url,
            telegram_bot_token=settings.telegram_bot_token,
            telegram_chat_id=settings.telegram_chat_id,
            timeout_seconds=settings.timeout_seconds,
        )
        if not notifier.configured:
            raise RuntimeError("No notification channel is configured")
        sent = notifier.send_text(
            "[보호구역 모니터링 테스트]\n"
            "Telegram/Slack 알림 연결이 정상입니다.\n"
            "이 메시지는 운영 데이터를 변경하지 않는 테스트 발송입니다."
        )
        print("Notification test sent: " + ", ".join(sent))
        return

    summary = run_pipeline(settings)
    print(
        "Run complete: "
        f"NEW={summary.diff.count(ChangeType.NEW)} "
        f"GEOMETRY_CHANGED={summary.diff.count(ChangeType.GEOMETRY_CHANGED)} "
        f"ATTRIBUTE_CHANGED={summary.diff.count(ChangeType.ATTRIBUTE_CHANGED)} "
        f"GEOMETRY_ATTRIBUTE_CHANGED="
        f"{summary.diff.count(ChangeType.GEOMETRY_ATTRIBUTE_CHANGED)} "
        f"UNCHANGED={summary.diff.count(ChangeType.UNCHANGED)} "
        f"DELETED={summary.diff.count(ChangeType.DELETED)} | "
        f"POINT_NEW={summary.point_diff.count(PointChangeType.NEW)} "
        f"POINT_CHANGED={summary.point_diff.count(PointChangeType.POINT_CHANGED)} "
        f"POINT_ATTRIBUTE_CHANGED={summary.point_diff.count(PointChangeType.ATTRIBUTE_CHANGED)} "
        f"POINT_BOTH_CHANGED="
        f"{summary.point_diff.count(PointChangeType.POINT_ATTRIBUTE_CHANGED)} "
        f"POINT_UNCHANGED={summary.point_diff.count(PointChangeType.UNCHANGED)} "
        f"POINT_MISSING={summary.point_diff.count(PointChangeType.MISSING)}"
    )
