from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from safety_zone_monitor.normalize import FacilityPointRecord, ZoneRecord


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


class PointChangeType(StrEnum):
    NEW = "NEW"
    POINT_CHANGED = "POINT_CHANGED"
    ATTRIBUTE_CHANGED = "ATTRIBUTE_CHANGED"
    POINT_ATTRIBUTE_CHANGED = "POINT_ATTRIBUTE_CHANGED"
    UNCHANGED = "UNCHANGED"
    DELETED = "DELETED"
    MISSING = "MISSING"


@dataclass(frozen=True)
class ExistingFacilityPoint:
    facility_id: str
    point_ordinal: int
    attr_hash: str
    point_hash: str
    data_hash: str
    snapshot: dict[str, Any]

    @property
    def key(self) -> tuple[str, int]:
        return self.facility_id, self.point_ordinal


@dataclass(frozen=True)
class PointChange:
    change_type: PointChangeType
    facility_id: str
    point_ordinal: int
    zone_group_id: str
    old_attr_hash: str | None
    new_attr_hash: str | None
    old_point_hash: str | None
    new_point_hash: str | None
    old_data_hash: str | None
    new_data_hash: str | None
    old_snapshot: dict[str, Any] | None
    new_snapshot: dict[str, Any] | None


@dataclass(frozen=True)
class PointDiffResult:
    changes: tuple[PointChange, ...]
    unchanged_keys: tuple[tuple[str, int], ...]

    def count(self, change_type: PointChangeType) -> int:
        if change_type is PointChangeType.UNCHANGED:
            return len(self.unchanged_keys)
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


def _updated_point_change_type(
    record: FacilityPointRecord, existing: ExistingFacilityPoint
) -> PointChangeType:
    point_changed = record.point_hash != existing.point_hash
    attribute_changed = record.attr_hash != existing.attr_hash
    if point_changed and attribute_changed:
        return PointChangeType.POINT_ATTRIBUTE_CHANGED
    if point_changed:
        return PointChangeType.POINT_CHANGED
    return PointChangeType.ATTRIBUTE_CHANGED


def detect_point_changes(
    incoming: list[FacilityPointRecord],
    current: dict[tuple[str, int], ExistingFacilityPoint],
    deleted_zone_group_ids: set[str] | None = None,
) -> PointDiffResult:
    deleted_zone_group_ids = deleted_zone_group_ids or set()
    incoming_by_key = {
        (record.facility_id, record.point_ordinal): record for record in incoming
    }
    changes: list[PointChange] = []
    unchanged: list[tuple[str, int]] = []

    for key, record in sorted(incoming_by_key.items()):
        existing = current.get(key)
        if existing is None:
            changes.append(
                PointChange(
                    PointChangeType.NEW,
                    record.facility_id,
                    record.point_ordinal,
                    record.zone_group_id,
                    None,
                    record.attr_hash,
                    None,
                    record.point_hash,
                    None,
                    record.data_hash,
                    None,
                    record.snapshot(),
                )
            )
        elif existing.data_hash != record.data_hash:
            changes.append(
                PointChange(
                    _updated_point_change_type(record, existing),
                    record.facility_id,
                    record.point_ordinal,
                    record.zone_group_id,
                    existing.attr_hash,
                    record.attr_hash,
                    existing.point_hash,
                    record.point_hash,
                    existing.data_hash,
                    record.data_hash,
                    existing.snapshot,
                    record.snapshot(),
                )
            )
        else:
            unchanged.append(key)

    for key in sorted(set(current) - set(incoming_by_key)):
        existing = current[key]
        zone_group_id = str(existing.snapshot.get("zone_group_id") or "")
        change_type = (
            PointChangeType.DELETED
            if zone_group_id in deleted_zone_group_ids
            else PointChangeType.MISSING
        )
        changes.append(
            PointChange(
                change_type,
                existing.facility_id,
                existing.point_ordinal,
                zone_group_id,
                existing.attr_hash,
                None,
                existing.point_hash,
                None,
                existing.data_hash,
                None,
                existing.snapshot,
                None,
            )
        )
    return PointDiffResult(tuple(changes), tuple(unchanged))
