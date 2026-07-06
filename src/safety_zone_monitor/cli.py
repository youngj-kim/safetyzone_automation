from __future__ import annotations

import argparse
import json
import logging

from safety_zone_monitor.config import Settings
from safety_zone_monitor.db import Repository
from safety_zone_monitor.diff import ChangeType
from safety_zone_monitor.pipeline import run_pipeline


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
    return parser


def main() -> None:
    args = _parser().parse_args()
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

    summary = run_pipeline(settings)
    print(
        "Run complete: "
        f"NEW={summary.diff.count(ChangeType.NEW)} "
        f"GEOMETRY_CHANGED={summary.diff.count(ChangeType.GEOMETRY_CHANGED)} "
        f"ATTRIBUTE_CHANGED={summary.diff.count(ChangeType.ATTRIBUTE_CHANGED)} "
        f"GEOMETRY_ATTRIBUTE_CHANGED="
        f"{summary.diff.count(ChangeType.GEOMETRY_ATTRIBUTE_CHANGED)} "
        f"UNCHANGED={summary.diff.count(ChangeType.UNCHANGED)} "
        f"DELETED={summary.diff.count(ChangeType.DELETED)}"
    )
