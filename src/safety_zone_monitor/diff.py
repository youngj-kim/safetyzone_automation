from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from safety_zone_monitor.normalize import ZoneRecord


class ChangeType(StrEnum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"
    MISSING = "MISSING"


@dataclass(frozen=True)
class ExistingZone:
    zone_key: str
    data_hash: str
    snapshot: dict[str, Any]


@dataclass(frozen=True)
class Change:
    change_type: ChangeType
    zone_key: str
    old_hash: str | None
    new_hash: str | None
    old_snapshot: dict[str, Any] | None
    new_snapshot: dict[str, Any] | None


@dataclass(frozen=True)
class DiffResult:
    changes: tuple[Change, ...]
    unchanged_keys: tuple[str, ...]

    def count(self, change_type: ChangeType) -> int:
        if change_type is ChangeType.UNCHANGED:
            return len(self.unchanged_keys)
        return sum(change.change_type is change_type for change in self.changes)

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)


def detect_changes(
    incoming: list[ZoneRecord],
    current: dict[str, ExistingZone],
) -> DiffResult:
    incoming_by_key = {record.zone_key: record for record in incoming}
    changes: list[Change] = []
    unchanged: list[str] = []
    for zone_key, record in sorted(incoming_by_key.items()):
        existing = current.get(zone_key)
        if existing is None:
            changes.append(
                Change(
                    ChangeType.NEW,
                    zone_key,
                    None,
                    record.data_hash,
                    None,
                    record.snapshot(),
                )
            )
        elif existing.data_hash != record.data_hash:
            changes.append(
                Change(
                    ChangeType.UPDATED,
                    zone_key,
                    existing.data_hash,
                    record.data_hash,
                    existing.snapshot,
                    record.snapshot(),
                )
            )
        else:
            unchanged.append(zone_key)

    for zone_key in sorted(set(current) - set(incoming_by_key)):
        existing = current[zone_key]
        changes.append(
            Change(
                ChangeType.MISSING,
                zone_key,
                existing.data_hash,
                None,
                existing.snapshot,
                None,
            )
        )
    return DiffResult(tuple(changes), tuple(unchanged))
