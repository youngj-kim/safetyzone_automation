from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from safety_zone_monitor.normalize import ZoneRecord


class ChangeType(StrEnum):
    NEW = "NEW"
    GEOMETRY_CHANGED = "GEOMETRY_CHANGED"
    ATTRIBUTE_CHANGED = "ATTRIBUTE_CHANGED"
    GEOMETRY_ATTRIBUTE_CHANGED = "GEOMETRY_ATTRIBUTE_CHANGED"
    UNCHANGED = "UNCHANGED"
    DELETED = "DELETED"


@dataclass(frozen=True)
class ExistingZone:
    zone_id: str
    attr_hash: str
    geom_hash: str
    data_hash: str
    snapshot: dict[str, Any]


@dataclass(frozen=True)
class Change:
    change_type: ChangeType
    zone_id: str
    old_attr_hash: str | None
    new_attr_hash: str | None
    old_geom_hash: str | None
    new_geom_hash: str | None
    old_data_hash: str | None
    new_data_hash: str | None
    old_snapshot: dict[str, Any] | None
    new_snapshot: dict[str, Any] | None


@dataclass(frozen=True)
class DiffResult:
    changes: tuple[Change, ...]
    unchanged_ids: tuple[str, ...]

    def count(self, change_type: ChangeType) -> int:
        if change_type is ChangeType.UNCHANGED:
            return len(self.unchanged_ids)
        return sum(change.change_type is change_type for change in self.changes)

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)


def _updated_change_type(record: ZoneRecord, existing: ExistingZone) -> ChangeType:
    geometry_changed = record.geom_hash != existing.geom_hash
    attribute_changed = record.attr_hash != existing.attr_hash
    if geometry_changed and attribute_changed:
        return ChangeType.GEOMETRY_ATTRIBUTE_CHANGED
    if geometry_changed:
        return ChangeType.GEOMETRY_CHANGED
    return ChangeType.ATTRIBUTE_CHANGED


def detect_changes(
    incoming: list[ZoneRecord],
    current: dict[str, ExistingZone],
) -> DiffResult:
    incoming_by_id = {record.zone_id: record for record in incoming}
    changes: list[Change] = []
    unchanged: list[str] = []
    for zone_id, record in sorted(incoming_by_id.items()):
        existing = current.get(zone_id)
        if existing is None:
            changes.append(
                Change(
                    ChangeType.NEW,
                    zone_id,
                    None,
                    record.attr_hash,
                    None,
                    record.geom_hash,
                    None,
                    record.data_hash,
                    None,
                    record.snapshot(),
                )
            )
        elif existing.data_hash != record.data_hash:
            changes.append(
                Change(
                    _updated_change_type(record, existing),
                    zone_id,
                    existing.attr_hash,
                    record.attr_hash,
                    existing.geom_hash,
                    record.geom_hash,
                    existing.data_hash,
                    record.data_hash,
                    existing.snapshot,
                    record.snapshot(),
                )
            )
        else:
            unchanged.append(zone_id)

    for zone_id in sorted(set(current) - set(incoming_by_id)):
        existing = current[zone_id]
        changes.append(
            Change(
                ChangeType.DELETED,
                zone_id,
                existing.attr_hash,
                None,
                existing.geom_hash,
                None,
                existing.data_hash,
                None,
                existing.snapshot,
                None,
            )
        )
    return DiffResult(tuple(changes), tuple(unchanged))
