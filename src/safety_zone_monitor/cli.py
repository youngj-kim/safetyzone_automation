from __future__ import annotations

import argparse
import logging

from safety_zone_monitor.config import Settings
from safety_zone_monitor.db import Repository
from safety_zone_monitor.diff import ChangeType
from safety_zone_monitor.pipeline import run_pipeline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safety Zone Change Monitoring System")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="Create or update the PostGIS schema")
    subparsers.add_parser("run", help="Fetch, normalize, compare, store, and notify")
    return parser


def main() -> None:
    args = _parser().parse_args()
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    if args.command == "init-db":
        Repository(settings.database_url).migrate()
        print("Database schema is ready.")
        return

    summary = run_pipeline(settings)
    print(
        "Run complete: "
        f"NEW={summary.diff.count(ChangeType.NEW)} "
        f"UPDATED={summary.diff.count(ChangeType.UPDATED)} "
        f"UNCHANGED={summary.diff.count(ChangeType.UNCHANGED)} "
        f"MISSING={summary.diff.count(ChangeType.MISSING)}"
    )
