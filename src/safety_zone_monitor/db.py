from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import psycopg

from safety_zone_monitor.diff import (
    ChangeType,
    DiffResult,
    ExistingFacilityPoint,
    ExistingZone,
    PointChangeType,
    PointDiffResult,
    detect_changes,
    detect_point_changes,
)
from safety_zone_monitor.normalize import FacilityPointRecord, ZoneRecord, clean_text, stable_hash

DEFAULT_DASHBOARD_BASELINE_DATE = "2026-07-07"
SENSITIVE_QUERY_PARAM_PATTERN = re.compile(
    r"([?&](?:serviceKey|service_key|key|token)=)[^&\s]+",
    re.IGNORECASE,
)


def sanitize_error_message(message: str | None) -> str | None:
    if not message:
        return message
    return SENSITIVE_QUERY_PARAM_PATTERN.sub(r"\1[REDACTED]", message)


@dataclass(frozen=True)
class RunSummary:
    run_id: uuid.UUID
    fetched_count: int
    polygon_count: int
    facility_point_count: int
    point_only_record_count: int
    skipped_non_polygon_count: int
    skipped_inactive_count: int
    diff: DiffResult
    point_diff: PointDiffResult

    @property
    def change_count(self) -> int:
        return len(self.diff.changes) + len(self.point_diff.changes)

    @property
    def point_change_count(self) -> int:
        return len(self.point_diff.changes)

    @property
    def has_changes(self) -> bool:
        return self.diff.has_changes or self.point_diff.has_changes


class Repository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, connect_timeout=10)

    def migrate(self) -> None:
        migration_dir = files("safety_zone_monitor").joinpath("migrations")
        with self._connect() as connection:
            has_postgis = connection.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis')"
            ).fetchone()[0]
            if not has_postgis:
                raise RuntimeError(
                    "The target mobility_db does not have PostGIS installed; "
                    "do not create a separate database for this pipeline"
                )
            for migration in sorted(migration_dir.iterdir(), key=lambda path: path.name):
                if migration.name.endswith(".sql"):
                    connection.execute(migration.read_text(encoding="utf-8"))

    def audit_host_contract(self, *, include_counts: bool = False) -> dict[str, Any]:
        """Read-only verification of the standard-node-link integration contract."""
        with self._connect() as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            schemas = [
                row[0]
                for row in connection.execute(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name IN ('raw', 'mobility', 'analysis', 'ops') "
                    "ORDER BY schema_name"
                ).fetchall()
            ]
            required = (
                "raw.raw_std_link_20260612",
                "raw.raw_std_node_20260612",
                "raw.raw_std_multilink_20260612",
                "mobility.std_link",
                "mobility.std_node",
                "mobility.std_multilink",
                "mobility.v_multilink_summary",
                "mobility.v_std_link_multilink_summary",
            )
            objects = {
                name: connection.execute("SELECT to_regclass(%s)::text", (name,)).fetchone()[0]
                is not None
                for name in required
            }
            geometry = connection.execute(
                """
                SELECT f_table_schema, f_table_name, type, srid
                FROM public.geometry_columns
                WHERE (f_table_schema, f_table_name) IN (
                    ('mobility', 'std_link'), ('mobility', 'std_node')
                )
                ORDER BY f_table_schema, f_table_name
                """
            ).fetchall()
            counts: dict[str, int] = {}
            if include_counts:
                for name in (
                    "mobility.std_link",
                    "mobility.std_node",
                    "mobility.std_multilink",
                ):
                    counts[name] = connection.execute(
                        f"SELECT COUNT(*) FROM {name}"  # noqa: S608 - fixed allowlist above
                    ).fetchone()[0]
            connection.rollback()
        return {
            "schemas": schemas,
            "required_objects": objects,
            "geometry": [
                {"schema": row[0], "table": row[1], "type": row[2], "srid": row[3]}
                for row in geometry
            ],
            "exact_rows": counts,
        }

    def quality_report(self, expected_sgg_codes: tuple[str, ...] = ()) -> dict[str, Any]:
        """Read-only checks for identity, coverage, group linkage, and geometry quality."""
        with self._connect() as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            latest = connection.execute(
                "SELECT pipeline_run_id, finished_at, monitored_sgg_codes "
                "FROM ops.pipeline_run WHERE status = 'SUCCESS' "
                "ORDER BY finished_at DESC LIMIT 1"
            ).fetchone()
            current_counts = {
                "polygons": connection.execute(
                    "SELECT COUNT(*) FROM analysis.zone_current"
                ).fetchone()[0],
                "facility_points": connection.execute(
                    "SELECT COUNT(*) FROM analysis.zone_facility_point_current"
                ).fetchone()[0],
                "zone_groups": connection.execute(
                    "SELECT COUNT(*) FROM analysis.v_zone_group_current"
                ).fetchone()[0],
            }
            current_sgg_codes = tuple(
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT sgg_code FROM ("
                    "SELECT sgg_code FROM analysis.zone_current UNION ALL "
                    "SELECT sgg_code FROM analysis.zone_facility_point_current"
                    ") AS scope ORDER BY sgg_code"
                ).fetchall()
            )
            duplicate_zone_manage_nos = connection.execute(
                "SELECT COUNT(*) FROM (SELECT source_manage_no "
                "FROM analysis.zone_current WHERE source_manage_no IS NOT NULL "
                "GROUP BY source_manage_no HAVING COUNT(*) > 1) AS duplicates"
            ).fetchone()[0]
            duplicate_point_manage_nos = connection.execute(
                "SELECT COUNT(*) FROM (SELECT source_manage_no "
                "FROM analysis.zone_facility_point_current "
                "WHERE source_manage_no IS NOT NULL GROUP BY source_manage_no "
                "HAVING COUNT(DISTINCT facility_id) > 1) AS duplicates"
            ).fetchone()[0]
            orphan_point_groups = connection.execute(
                "SELECT COUNT(*) FROM analysis.v_zone_group_current "
                "WHERE polygon_record_count = 0 AND facility_count > 0"
            ).fetchone()[0]
            invalid_polygons = connection.execute(
                "SELECT COUNT(*) FROM analysis.zone_current "
                "WHERE ST_IsEmpty(geom) OR NOT ST_IsValid(geom) OR ST_SRID(geom) <> 5179"
            ).fetchone()[0]
            invalid_points = connection.execute(
                "SELECT COUNT(*) FROM analysis.zone_facility_point_current "
                "WHERE ST_IsEmpty(geom) OR NOT ST_IsValid(geom) OR ST_SRID(geom) <> 5179"
            ).fetchone()[0]
            missing_sgg_codes = sorted(set(expected_sgg_codes) - set(current_sgg_codes))
            connection.rollback()

        critical_counts = {
            "duplicate_zone_manage_nos": duplicate_zone_manage_nos,
            "duplicate_point_manage_nos": duplicate_point_manage_nos,
            "invalid_polygons": invalid_polygons,
            "invalid_points": invalid_points,
            "missing_expected_sgg_codes": len(missing_sgg_codes),
        }
        return {
            "status": "PASS" if not any(critical_counts.values()) else "FAIL",
            "latest_successful_run": {
                "run_id": str(latest[0]) if latest else None,
                "finished_at": latest[1].isoformat() if latest else None,
                "monitored_sgg_codes": latest[2] if latest else [],
            },
            "current_counts": current_counts,
            "current_sgg_count": len(current_sgg_codes),
            "current_sgg_codes": current_sgg_codes,
            "critical_checks": critical_counts,
            "missing_expected_sgg_codes": missing_sgg_codes,
            "warnings": {"point_groups_without_polygon": orphan_point_groups},
        }

    def create_run(self, sgg_codes: tuple[str, ...], source_endpoint: str) -> uuid.UUID:
        run_id = uuid.uuid4()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO ops.pipeline_run "
                "(pipeline_run_id, status, monitored_sgg_codes) "
                "VALUES (%s, 'RUNNING', %s)",
                (run_id, list(sgg_codes)),
            )
            connection.execute(
                "INSERT INTO raw.police_zone_api_run "
                "(run_id, status, source_endpoint, monitored_sgg_codes) "
                "VALUES (%s, 'RUNNING', %s, %s)",
                (run_id, source_endpoint, list(sgg_codes)),
            )
        return run_id

    def mark_failed(self, run_id: uuid.UUID, error: Exception) -> None:
        message = f"{type(error).__name__}: {error}"[:4000]
        with self._connect() as connection:
            connection.execute(
                "UPDATE ops.pipeline_run SET status = 'FAILED', finished_at = now(), "
                "error_message = %s WHERE pipeline_run_id = %s AND status = 'RUNNING'",
                (message, run_id),
            )
            connection.execute(
                "UPDATE raw.police_zone_api_run SET status = 'FAILED', completed_at = now(), "
                "error_count = error_count + 1, error_message = %s "
                "WHERE run_id = %s AND status = 'RUNNING'",
                (message, run_id),
            )

    def _load_current(
        self,
        connection: psycopg.Connection,
        sgg_codes: tuple[str, ...],
    ) -> dict[str, ExistingZone]:
        rows = connection.execute(
            "SELECT zone_id, attr_hash, geom_hash, data_hash, attrs "
            "FROM analysis.zone_current WHERE sgg_code = ANY(%s)",
            (list(sgg_codes),),
        ).fetchall()
        return {
            str(row[0]).strip(): ExistingZone(
                zone_id=str(row[0]).strip(),
                attr_hash=str(row[1]).strip(),
                geom_hash=str(row[2]).strip(),
                data_hash=str(row[3]).strip(),
                snapshot={
                    "zone_id": str(row[0]).strip(),
                    "attr_hash": str(row[1]).strip(),
                    "geom_hash": str(row[2]).strip(),
                    "data_hash": str(row[3]).strip(),
                    **row[4],
                },
            )
            for row in rows
        }

    def _load_current_points(
        self,
        connection: psycopg.Connection,
        sgg_codes: tuple[str, ...],
    ) -> dict[tuple[str, int], ExistingFacilityPoint]:
        rows = connection.execute(
            "SELECT facility_id, point_ordinal, zone_group_id, attr_hash, point_hash, "
            "data_hash, attrs FROM analysis.zone_facility_point_current "
            "WHERE sgg_code = ANY(%s)",
            (list(sgg_codes),),
        ).fetchall()
        result = {}
        for row in rows:
            facility_id = str(row[0]).strip()
            point_ordinal = row[1]
            snapshot = {
                "facility_id": facility_id,
                "point_ordinal": point_ordinal,
                "zone_group_id": row[2],
                "attr_hash": str(row[3]).strip(),
                "point_hash": str(row[4]).strip(),
                "data_hash": str(row[5]).strip(),
                **row[6],
            }
            existing = ExistingFacilityPoint(
                facility_id=facility_id,
                point_ordinal=point_ordinal,
                attr_hash=str(row[3]).strip(),
                point_hash=str(row[4]).strip(),
                data_hash=str(row[5]).strip(),
                snapshot=snapshot,
            )
            result[existing.key] = existing
        return result

    @staticmethod
    def _record_values(record: ZoneRecord, run_id: uuid.UUID) -> tuple[object, ...]:
        return (
            record.zone_id,
            record.zone_group_id,
            record.attr_hash,
            record.geom_hash,
            record.data_hash,
            record.source_manage_no,
            record.project_no,
            record.facility_name,
            record.facility_type_code,
            record.facility_detail_type_code,
            record.representative_manage_no,
            record.use_yn,
            record.sgg_code,
            record.emdong_code,
            record.stdg_code,
            record.assign_type,
            record.road_address,
            record.road_detail_address,
            record.lot_address,
            record.lot_detail_address,
            record.first_registered_on,
            record.last_modified_on,
            record.geometry_wkt,
            json.dumps(record.attributes(), ensure_ascii=False),
            json.dumps(record.geometry_qc, ensure_ascii=False),
            run_id,
        )

    @staticmethod
    def _point_values(
        record: FacilityPointRecord, run_id: uuid.UUID
    ) -> tuple[object, ...]:
        return (
            record.facility_id,
            record.point_ordinal,
            record.zone_group_id,
            record.attr_hash,
            record.point_hash,
            record.data_hash,
            record.source_manage_no,
            record.facility_name,
            record.sgg_code,
            record.use_yn,
            record.geometry_wkt,
            json.dumps(record.attrs, ensure_ascii=False),
            run_id,
        )

    @staticmethod
    def _raw_values(
        run_id: uuid.UUID, item_ordinal: int, item: dict[str, Any]
    ) -> tuple[object, ...]:
        return (
            run_id,
            item_ordinal,
            clean_text(item.get("ptznMngNo")),
            clean_text(item.get("sggCd")),
            json.dumps(item, ensure_ascii=False),
            clean_text(item.get("fturGeomVl")),
            stable_hash(item),
        )

    def apply_run(
        self,
        *,
        run_id: uuid.UUID,
        sgg_codes: tuple[str, ...],
        raw_items: list[dict[str, Any]],
        records: list[ZoneRecord],
        facility_points: list[FacilityPointRecord],
        skipped_non_polygon_count: int,
        skipped_inactive_count: int,
        point_only_record_count: int,
        record_events: bool = True,
    ) -> RunSummary:
        incoming_sgg_codes = {record.sgg_code for record in records} | {
            record.sgg_code for record in facility_points
        }
        if not incoming_sgg_codes.issubset(set(sgg_codes)):
            raise ValueError("API returned a record outside the configured SGG scope")

        with self._connect() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext('police-zone-daily-monitor'))"
            )

            if raw_items:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO raw.police_zone_item_snapshot "
                        "(run_id, item_ordinal, source_manage_no, sgg_code, "
                        "raw_json, raw_wkt, payload_hash) "
                        "VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)",
                        [
                            self._raw_values(run_id, index, item)
                            for index, item in enumerate(raw_items, start=1)
                        ],
                    )

            if records:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO analysis.zone_snapshot "
                        "(run_id, zone_id, zone_group_id, attr_hash, geom_hash, data_hash, attrs, "
                        "geometry_qc, geom) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, "
                        "ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Transform("
                        "ST_UnaryUnion(ST_CollectionExtract("
                        "ST_GeomFromText(%s, 5181), 3)), 5179)), 3))::"
                        "geometry(MultiPolygon, 5179))",
                        [
                            (
                                run_id,
                                record.zone_id,
                                record.zone_group_id,
                                record.attr_hash,
                                record.geom_hash,
                                record.data_hash,
                                json.dumps(record.attributes(), ensure_ascii=False),
                                json.dumps(record.geometry_qc, ensure_ascii=False),
                                record.geometry_wkt,
                            )
                            for record in records
                        ],
                    )

            if facility_points:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO analysis.zone_facility_point_snapshot "
                        "(run_id, facility_id, point_ordinal, zone_group_id, attr_hash, "
                        "point_hash, data_hash, source_manage_no, facility_name, sgg_code, "
                        "use_yn, geom, attrs) VALUES "
                        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                        "ST_Transform(ST_GeomFromText(%s, 5181), 5179)::geometry(Point, 5179), "
                        "%s::jsonb)",
                        [
                            (
                                run_id,
                                point.facility_id,
                                point.point_ordinal,
                                point.zone_group_id,
                                point.attr_hash,
                                point.point_hash,
                                point.data_hash,
                                point.source_manage_no,
                                point.facility_name,
                                point.sgg_code,
                                point.use_yn,
                                point.geometry_wkt,
                                json.dumps(point.attrs, ensure_ascii=False),
                            )
                            for point in facility_points
                        ],
                    )

            current = self._load_current(connection, sgg_codes)
            diff = detect_changes(records, current)
            current_points = self._load_current_points(connection, sgg_codes)
            deleted_zone_group_ids = {
                str(change.old_snapshot.get("zone_group_id") or "")
                for change in diff.changes
                if change.change_type is ChangeType.DELETED and change.old_snapshot is not None
            }
            point_diff = detect_point_changes(
                facility_points,
                current_points,
                deleted_zone_group_ids=deleted_zone_group_ids,
            )
            event_rows = [
                (
                    run_id,
                    change.zone_id,
                    change.change_type.value,
                    change.old_attr_hash,
                    change.new_attr_hash,
                    change.old_geom_hash,
                    change.new_geom_hash,
                    change.old_data_hash,
                    change.new_data_hash,
                    json.dumps(change.old_snapshot, ensure_ascii=False)
                    if change.old_snapshot is not None
                    else None,
                    json.dumps(change.new_snapshot, ensure_ascii=False)
                    if change.new_snapshot is not None
                    else None,
                )
                for change in diff.changes
            ]
            if record_events and event_rows:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO analysis.zone_change_event "
                        "(run_id, zone_id, change_type, old_attr_hash, new_attr_hash, "
                        "old_geom_hash, new_geom_hash, old_data_hash, new_data_hash, "
                        "old_snapshot, new_snapshot) VALUES "
                        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)",
                        event_rows,
                    )

            point_event_rows = [
                (
                    run_id,
                    change.facility_id,
                    change.point_ordinal,
                    change.zone_group_id,
                    change.change_type.value,
                    change.old_attr_hash,
                    change.new_attr_hash,
                    change.old_point_hash,
                    change.new_point_hash,
                    change.old_data_hash,
                    change.new_data_hash,
                    json.dumps(change.old_snapshot, ensure_ascii=False)
                    if change.old_snapshot is not None
                    else None,
                    json.dumps(change.new_snapshot, ensure_ascii=False)
                    if change.new_snapshot is not None
                    else None,
                )
                for change in point_diff.changes
            ]
            if record_events and point_event_rows:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO analysis.zone_facility_point_change_event "
                        "(run_id, facility_id, point_ordinal, zone_group_id, change_type, "
                        "old_attr_hash, new_attr_hash, old_point_hash, new_point_hash, "
                        "old_data_hash, new_data_hash, old_snapshot, new_snapshot) VALUES "
                        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                        "%s::jsonb, %s::jsonb)",
                        point_event_rows,
                    )

            if facility_points:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "DELETE FROM analysis.zone_facility_point_absence "
                        "WHERE facility_id = %s AND point_ordinal = %s",
                        [
                            (point.facility_id, point.point_ordinal)
                            for point in facility_points
                        ],
                    )

            point_absence_rows = [
                (
                    change.facility_id,
                    change.point_ordinal,
                    change.zone_group_id,
                    (change.old_snapshot or {}).get("source_manage_no"),
                    (change.old_snapshot or {}).get("facility_name"),
                    (change.old_snapshot or {}).get("sgg_code"),
                    run_id,
                    run_id,
                    change.change_type.value,
                    json.dumps(change.old_snapshot, ensure_ascii=False)
                    if change.old_snapshot is not None
                    else None,
                )
                for change in point_diff.changes
                if change.change_type in (PointChangeType.DELETED, PointChangeType.MISSING)
            ]
            if record_events and point_absence_rows:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO analysis.zone_facility_point_absence "
                        "(facility_id, point_ordinal, zone_group_id, source_manage_no, "
                        "facility_name, sgg_code, first_missing_run_id, last_missing_run_id, "
                        "last_change_type, old_snapshot) VALUES "
                        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
                        "ON CONFLICT (facility_id, point_ordinal) DO UPDATE SET "
                        "zone_group_id = EXCLUDED.zone_group_id, "
                        "source_manage_no = EXCLUDED.source_manage_no, "
                        "facility_name = EXCLUDED.facility_name, "
                        "sgg_code = EXCLUDED.sgg_code, "
                        "last_missing_run_id = EXCLUDED.last_missing_run_id, "
                        "last_missing_at = now(), "
                        "missing_streak = analysis.zone_facility_point_absence.missing_streak + 1, "
                        "last_change_type = EXCLUDED.last_change_type, "
                        "old_snapshot = EXCLUDED.old_snapshot",
                        point_absence_rows,
                    )

            if record_events:
                connection.execute(
                    "UPDATE analysis.zone_facility_point_absence "
                    "SET last_missing_run_id = %s, last_missing_at = now(), "
                    "missing_streak = missing_streak + 1 "
                    "WHERE sgg_code = ANY(%s) "
                    "AND last_change_type = 'MISSING' "
                    "AND last_missing_run_id <> %s",
                    (run_id, list(sgg_codes), run_id),
                )

            upsert_sql = """
                INSERT INTO analysis.zone_current (
                    zone_id, zone_group_id, attr_hash, geom_hash, data_hash,
                    source_manage_no, project_no,
                    facility_name, facility_type_code, facility_detail_type_code,
                    representative_manage_no, use_yn, sgg_code, emdong_code, stdg_code,
                    assign_type, road_address, road_detail_address, lot_address,
                    lot_detail_address, first_registered_on, last_modified_on, geom, attrs,
                    geometry_qc, last_run_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Transform(ST_UnaryUnion(
                        ST_CollectionExtract(ST_GeomFromText(%s, 5181), 3)
                    ), 5179)), 3))::geometry(MultiPolygon, 5179),
                    %s::jsonb, %s::jsonb, %s
                )
                ON CONFLICT (zone_id) DO UPDATE SET
                    zone_group_id = EXCLUDED.zone_group_id,
                    attr_hash = EXCLUDED.attr_hash,
                    geom_hash = EXCLUDED.geom_hash,
                    data_hash = EXCLUDED.data_hash,
                    source_manage_no = EXCLUDED.source_manage_no,
                    project_no = EXCLUDED.project_no,
                    facility_name = EXCLUDED.facility_name,
                    facility_type_code = EXCLUDED.facility_type_code,
                    facility_detail_type_code = EXCLUDED.facility_detail_type_code,
                    representative_manage_no = EXCLUDED.representative_manage_no,
                    use_yn = EXCLUDED.use_yn,
                    sgg_code = EXCLUDED.sgg_code,
                    emdong_code = EXCLUDED.emdong_code,
                    stdg_code = EXCLUDED.stdg_code,
                    assign_type = EXCLUDED.assign_type,
                    road_address = EXCLUDED.road_address,
                    road_detail_address = EXCLUDED.road_detail_address,
                    lot_address = EXCLUDED.lot_address,
                    lot_detail_address = EXCLUDED.lot_detail_address,
                    first_registered_on = EXCLUDED.first_registered_on,
                    last_modified_on = EXCLUDED.last_modified_on,
                    geom = EXCLUDED.geom,
                    attrs = EXCLUDED.attrs,
                    geometry_qc = EXCLUDED.geometry_qc,
                    last_seen_at = now(),
                    updated_at = CASE
                        WHEN analysis.zone_current.data_hash <> EXCLUDED.data_hash THEN now()
                        ELSE analysis.zone_current.updated_at
                    END,
                    last_run_id = EXCLUDED.last_run_id
            """
            if records:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        upsert_sql,
                        [self._record_values(record, run_id) for record in records],
                    )

            point_upsert_sql = """
                INSERT INTO analysis.zone_facility_point_current (
                    facility_id, point_ordinal, zone_group_id, attr_hash, point_hash,
                    data_hash, source_manage_no, facility_name, sgg_code, use_yn,
                    geom, attrs, last_run_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    ST_Transform(ST_GeomFromText(%s, 5181), 5179)::geometry(Point, 5179),
                    %s::jsonb, %s
                )
                ON CONFLICT (facility_id, point_ordinal) DO UPDATE SET
                    zone_group_id = EXCLUDED.zone_group_id,
                    attr_hash = EXCLUDED.attr_hash,
                    point_hash = EXCLUDED.point_hash,
                    data_hash = EXCLUDED.data_hash,
                    source_manage_no = EXCLUDED.source_manage_no,
                    facility_name = EXCLUDED.facility_name,
                    sgg_code = EXCLUDED.sgg_code,
                    use_yn = EXCLUDED.use_yn,
                    geom = EXCLUDED.geom,
                    attrs = EXCLUDED.attrs,
                    last_seen_at = now(),
                    updated_at = CASE
                        WHEN analysis.zone_facility_point_current.data_hash
                            <> EXCLUDED.data_hash THEN now()
                        ELSE analysis.zone_facility_point_current.updated_at
                    END,
                    last_run_id = EXCLUDED.last_run_id
            """
            if facility_points:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        point_upsert_sql,
                        [self._point_values(point, run_id) for point in facility_points],
                    )

            missing_point_keys = [
                (change.facility_id, change.point_ordinal)
                for change in point_diff.changes
                if change.change_type in (PointChangeType.DELETED, PointChangeType.MISSING)
            ]
            if missing_point_keys:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "DELETE FROM analysis.zone_facility_point_current "
                        "WHERE facility_id = %s AND point_ordinal = %s",
                        missing_point_keys,
                    )

            deleted_ids = [
                change.zone_id
                for change in diff.changes
                if change.change_type is ChangeType.DELETED
            ]
            if deleted_ids:
                connection.execute(
                    "DELETE FROM analysis.zone_current WHERE zone_id::text = ANY(%s)",
                    (deleted_ids,),
                )

            summary_diff = diff if record_events else DiffResult((), ())
            summary_point_diff = point_diff if record_events else PointDiffResult((), ())
            metrics = (
                len(raw_items),
                len(records),
                len(facility_points),
                point_only_record_count,
                skipped_non_polygon_count,
                skipped_inactive_count,
                summary_diff.count(ChangeType.NEW),
                summary_diff.count(ChangeType.GEOMETRY_CHANGED),
                summary_diff.count(ChangeType.ATTRIBUTE_CHANGED),
                summary_diff.count(ChangeType.GEOMETRY_ATTRIBUTE_CHANGED),
                summary_diff.count(ChangeType.UNCHANGED),
                summary_diff.count(ChangeType.DELETED),
                summary_point_diff.count(PointChangeType.NEW),
                sum(
                    summary_point_diff.count(change_type)
                    for change_type in (
                        PointChangeType.POINT_CHANGED,
                        PointChangeType.ATTRIBUTE_CHANGED,
                        PointChangeType.POINT_ATTRIBUTE_CHANGED,
                    )
                ),
                summary_point_diff.count(PointChangeType.UNCHANGED),
                summary_point_diff.count(PointChangeType.DELETED),
                summary_point_diff.count(PointChangeType.MISSING),
                run_id,
            )
            connection.execute(
                """
                UPDATE ops.pipeline_run SET
                    status = 'SUCCESS', finished_at = now(), fetched_count = %s,
                    polygon_count = %s, facility_point_count = %s,
                    point_only_record_count = %s, skipped_non_polygon_count = %s,
                    skipped_inactive_count = %s,
                    new_count = %s, geometry_changed_count = %s,
                    attribute_changed_count = %s, geometry_attribute_changed_count = %s,
                    unchanged_count = %s, deleted_count = %s,
                    point_new_count = %s, point_changed_count = %s,
                    point_unchanged_count = %s, point_deleted_count = %s,
                    point_missing_count = %s
                WHERE pipeline_run_id = %s
                """,
                metrics,
            )
            connection.execute(
                "UPDATE raw.police_zone_api_run SET status = 'SUCCESS', "
                "completed_at = now(), response_count = %s WHERE run_id = %s",
                (len(raw_items), run_id),
            )

        return RunSummary(
            run_id=run_id,
            fetched_count=len(raw_items),
            polygon_count=len(records),
            facility_point_count=len(facility_points),
            point_only_record_count=point_only_record_count,
            skipped_non_polygon_count=skipped_non_polygon_count,
            skipped_inactive_count=skipped_inactive_count,
            diff=summary_diff,
            point_diff=summary_point_diff,
        )

    def record_notification(
        self,
        run_id: uuid.UUID,
        channel: str,
        status: str,
        payload_summary: dict[str, Any],
        error_message: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO ops.notification_log "
                "(pipeline_run_id, channel, status, payload_summary, error_message) "
                "VALUES (%s, %s, %s, %s::jsonb, %s)",
                (
                    run_id,
                    channel,
                    status,
                    json.dumps(payload_summary, ensure_ascii=False),
                    error_message,
                ),
            )

    def mark_notification_sent(self, run_id: uuid.UUID) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE ops.pipeline_run SET notification_sent_at = now() "
                "WHERE pipeline_run_id = %s",
                (run_id,),
            )

    def dashboard_overview(self, *, recent_run_limit: int = 20) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            has_point_deleted_count = connection.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'ops'
                      AND table_name = 'pipeline_run'
                      AND column_name = 'point_deleted_count'
                )
                """
            ).fetchone()[0]
            point_deleted_count_sql = (
                "point_deleted_count"
                if has_point_deleted_count
                else "0 AS point_deleted_count"
            )
            counts = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*)::integer FROM analysis.zone_current) AS polygons,
                    (SELECT COUNT(*)::integer FROM analysis.zone_facility_point_current)
                        AS facility_points,
                    (
                        SELECT COUNT(DISTINCT sgg_code)::integer
                        FROM (
                            SELECT sgg_code FROM analysis.zone_current
                            UNION ALL
                            SELECT sgg_code FROM analysis.zone_facility_point_current
                        ) AS scope
                    ) AS sgg_codes
                """
            ).fetchone()
            run_rows = connection.execute(
                """
                SELECT
                    pipeline_run_id,
                    started_at,
                    finished_at,
                    status,
                    monitored_sgg_codes,
                    fetched_count,
                    polygon_count,
                    facility_point_count,
                    new_count,
                    geometry_changed_count,
                    attribute_changed_count,
                    geometry_attribute_changed_count,
                    deleted_count,
                    point_new_count,
                    point_changed_count,
                    """ + point_deleted_count_sql + """,
                    point_missing_count,
                    error_message,
                    notification_sent_at
                FROM ops.pipeline_run
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (recent_run_limit,),
            ).fetchall()
            connection.rollback()

        return {
            "current_counts": {
                "polygons": counts[0],
                "facility_points": counts[1],
                "sgg_codes": counts[2],
            },
            "recent_runs": [
                {
                    "run_id": str(row[0]),
                    "started_at": row[1].isoformat() if row[1] else None,
                    "finished_at": row[2].isoformat() if row[2] else None,
                    "status": row[3],
                    "monitored_sgg_codes": row[4],
                    "fetched_count": row[5],
                    "polygon_count": row[6],
                    "facility_point_count": row[7],
                    "polygon_changes": {
                        "new": row[8],
                        "geometry_changed": row[9],
                        "attribute_changed": row[10],
                        "geometry_attribute_changed": row[11],
                        "deleted": row[12],
                    },
                    "point_changes": {
                        "new": row[13],
                        "changed": row[14],
                        "deleted": row[15],
                        "missing": row[16],
                    },
                    "error_message": sanitize_error_message(row[17]),
                    "notification_sent_at": row[18].isoformat() if row[18] else None,
                }
                for row in run_rows
            ],
        }

    def dashboard_change_events(
        self,
        *,
        limit: int = 500,
        baseline_date: str | None = DEFAULT_DASHBOARD_BASELINE_DATE,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            polygon_rows = connection.execute(
                """
                SELECT
                    'Polygon' AS layer_type,
                    event_id,
                    run_id,
                    change_type,
                    COALESCE(new_snapshot ->> 'facility_name', old_snapshot ->> 'facility_name')
                        AS facility_name,
                    COALESCE(
                        new_snapshot ->> 'source_manage_no',
                        old_snapshot ->> 'source_manage_no'
                    )
                        AS source_manage_no,
                    COALESCE(new_snapshot ->> 'sgg_code', old_snapshot ->> 'sgg_code')
                        AS sgg_code,
                    COALESCE(new_snapshot ->> 'zone_group_id', old_snapshot ->> 'zone_group_id')
                        AS zone_group_id,
                    COALESCE(
                        new_snapshot ->> 'first_registered_on',
                        old_snapshot ->> 'first_registered_on'
                    )
                        AS first_registered_on,
                    COALESCE(
                        new_snapshot ->> 'last_modified_on',
                        old_snapshot ->> 'last_modified_on'
                    )
                        AS last_modified_on,
                    COALESCE(
                        new_snapshot ->> 'facility_type_code',
                        old_snapshot ->> 'facility_type_code'
                    )
                        AS facility_type_code,
                    detected_at
                FROM analysis.zone_change_event
                WHERE (%s::date IS NULL)
                   OR NOT (
                       change_type = 'NEW'
                       AND (detected_at AT TIME ZONE 'Asia/Seoul')::date <= %s::date
                   )
                ORDER BY detected_at DESC
                LIMIT %s
                """,
                (baseline_date, baseline_date, limit),
            ).fetchall()
            point_rows = connection.execute(
                """
                SELECT
                    'Point' AS layer_type,
                    event_id,
                    run_id,
                    change_type,
                    COALESCE(new_snapshot ->> 'facility_name', old_snapshot ->> 'facility_name')
                        AS facility_name,
                    COALESCE(
                        new_snapshot ->> 'source_manage_no',
                        old_snapshot ->> 'source_manage_no'
                    )
                        AS source_manage_no,
                    COALESCE(new_snapshot ->> 'sgg_code', old_snapshot ->> 'sgg_code')
                        AS sgg_code,
                    zone_group_id,
                    COALESCE(
                        new_snapshot ->> 'first_registered_on',
                        old_snapshot ->> 'first_registered_on'
                    )
                        AS first_registered_on,
                    COALESCE(
                        new_snapshot ->> 'last_modified_on',
                        old_snapshot ->> 'last_modified_on'
                    )
                        AS last_modified_on,
                    COALESCE(
                        new_snapshot ->> 'facility_type_code',
                        old_snapshot ->> 'facility_type_code'
                    )
                        AS facility_type_code,
                    detected_at
                FROM analysis.zone_facility_point_change_event
                WHERE (%s::date IS NULL)
                   OR NOT (
                       change_type = 'NEW'
                       AND (detected_at AT TIME ZONE 'Asia/Seoul')::date <= %s::date
                   )
                ORDER BY detected_at DESC
                LIMIT %s
                """,
                (baseline_date, baseline_date, limit),
            ).fetchall()
            connection.rollback()

        rows = sorted(
            [*polygon_rows, *point_rows],
            key=lambda row: row[11],
            reverse=True,
        )[:limit]
        return {
            "events": [
                {
                    "layer_type": row[0],
                    "event_id": row[1],
                    "run_id": str(row[2]),
                    "change_type": row[3],
                    "facility_name": row[4],
                    "source_manage_no": row[5],
                    "sgg_code": row[6],
                    "zone_group_id": row[7],
                    "api_first_registered_on": row[8],
                    "api_last_modified_on": row[9],
                    "facility_type_code": row[10],
                    "detected_at": row[11].isoformat() if row[11] else None,
                }
                for row in rows
            ]
        }

    def dashboard_timelines(
        self,
        *,
        limit: int = 1000,
        baseline_date: str | None = DEFAULT_DASHBOARD_BASELINE_DATE,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            polygon_rows = connection.execute(
                """
                SELECT
                    'Polygon' AS layer_type,
                    event_id,
                    run_id,
                    change_type,
                    COALESCE(new_snapshot ->> 'facility_name', old_snapshot ->> 'facility_name')
                        AS facility_name,
                    COALESCE(
                        new_snapshot ->> 'source_manage_no',
                        old_snapshot ->> 'source_manage_no'
                    )
                        AS source_manage_no,
                    COALESCE(new_snapshot ->> 'zone_group_id', old_snapshot ->> 'zone_group_id')
                        AS zone_group_id,
                    COALESCE(new_snapshot ->> 'sgg_code', old_snapshot ->> 'sgg_code')
                        AS sgg_code,
                    COALESCE(
                        new_snapshot ->> 'first_registered_on',
                        old_snapshot ->> 'first_registered_on'
                    )
                        AS first_registered_on,
                    COALESCE(
                        new_snapshot ->> 'last_modified_on',
                        old_snapshot ->> 'last_modified_on'
                    )
                        AS last_modified_on,
                    COALESCE(
                        new_snapshot ->> 'facility_type_code',
                        old_snapshot ->> 'facility_type_code'
                    )
                        AS facility_type_code,
                    detected_at
                FROM analysis.zone_change_event
                WHERE (%s::date IS NULL)
                   OR NOT (
                       change_type = 'NEW'
                       AND (detected_at AT TIME ZONE 'Asia/Seoul')::date <= %s::date
                   )
                ORDER BY detected_at DESC
                LIMIT %s
                """,
                (baseline_date, baseline_date, limit),
            ).fetchall()
            point_rows = connection.execute(
                """
                SELECT
                    'Point' AS layer_type,
                    event_id,
                    run_id,
                    change_type,
                    COALESCE(new_snapshot ->> 'facility_name', old_snapshot ->> 'facility_name')
                        AS facility_name,
                    COALESCE(
                        new_snapshot ->> 'source_manage_no',
                        old_snapshot ->> 'source_manage_no'
                    )
                        AS source_manage_no,
                    zone_group_id,
                    COALESCE(new_snapshot ->> 'sgg_code', old_snapshot ->> 'sgg_code')
                        AS sgg_code,
                    COALESCE(
                        new_snapshot ->> 'first_registered_on',
                        old_snapshot ->> 'first_registered_on'
                    )
                        AS first_registered_on,
                    COALESCE(
                        new_snapshot ->> 'last_modified_on',
                        old_snapshot ->> 'last_modified_on'
                    )
                        AS last_modified_on,
                    COALESCE(
                        new_snapshot ->> 'facility_type_code',
                        old_snapshot ->> 'facility_type_code'
                    )
                        AS facility_type_code,
                    detected_at
                FROM analysis.zone_facility_point_change_event
                WHERE (%s::date IS NULL)
                   OR NOT (
                       change_type = 'NEW'
                       AND (detected_at AT TIME ZONE 'Asia/Seoul')::date <= %s::date
                   )
                ORDER BY detected_at DESC
                LIMIT %s
                """,
                (baseline_date, baseline_date, limit),
            ).fetchall()
            has_absence_table = connection.execute(
                "SELECT to_regclass('analysis.zone_facility_point_absence') IS NOT NULL"
            ).fetchone()[0]
            absence_rows = []
            if has_absence_table:
                absence_rows = connection.execute(
                    """
                    SELECT
                        facility_id::text,
                        point_ordinal,
                        zone_group_id,
                        source_manage_no,
                        facility_name,
                        sgg_code,
                        first_missing_run_id,
                        first_missing_at,
                        last_missing_run_id,
                        last_missing_at,
                        missing_streak,
                        last_change_type
                    FROM analysis.zone_facility_point_absence
                    ORDER BY last_missing_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                ).fetchall()
            connection.rollback()

        grouped: dict[str, dict[str, Any]] = {}
        rows = sorted([*polygon_rows, *point_rows], key=lambda row: row[11], reverse=True)
        for row in rows:
            layer_type = row[0]
            source_manage_no = row[5]
            zone_group_id = row[6]
            entity_id = source_manage_no or zone_group_id or str(row[1])
            entity_key = f"{layer_type}:{entity_id}"
            event = {
                "layer_type": layer_type,
                "event_id": row[1],
                "run_id": str(row[2]),
                "change_type": row[3],
                "facility_name": row[4],
                "source_manage_no": source_manage_no,
                "zone_group_id": zone_group_id,
                "sgg_code": row[7],
                "api_first_registered_on": row[8],
                "api_last_modified_on": row[9],
                "facility_type_code": row[10],
                "detected_at": row[11].isoformat() if row[11] else None,
            }
            if entity_key not in grouped:
                grouped[entity_key] = {
                    "entity_key": entity_key,
                    "layer_type": layer_type,
                    "source_manage_no": source_manage_no,
                    "zone_group_id": zone_group_id,
                    "facility_name": row[4],
                    "sgg_code": row[7],
                    "facility_type_code": row[10],
                    "events": [],
                }
            grouped[entity_key]["events"].append(event)

        timelines = []
        for timeline in grouped.values():
            events = timeline["events"]
            latest_type = events[0]["change_type"] if events else None
            missing_streak = 0
            for event in events:
                if event["change_type"] != "MISSING":
                    break
                missing_streak += 1
            had_missing = any(event["change_type"] == "MISSING" for event in events[1:])
            if latest_type == "DELETED":
                status_hint = "DELETED_CONFIRMED"
            elif latest_type == "MISSING" and missing_streak >= 2:
                status_hint = "DELETE_CANDIDATE"
            elif latest_type == "MISSING":
                status_hint = "MISSING_REVIEW"
            elif latest_type and latest_type != "MISSING" and had_missing:
                status_hint = "RETURNED"
            elif latest_type == "NEW":
                status_hint = "NEW"
            elif latest_type:
                status_hint = "UPDATED"
            else:
                status_hint = "CURRENT"

            timeline["latest_change_type"] = latest_type
            timeline["latest_detected_at"] = events[0]["detected_at"] if events else None
            timeline["missing_streak"] = missing_streak
            timeline["status_hint"] = status_hint
            timelines.append(timeline)

        for row in absence_rows:
            source_manage_no = row[3]
            zone_group_id = row[2]
            entity_id = source_manage_no or zone_group_id or f"{row[0]}:{row[1]}"
            entity_key = f"Point:{entity_id}"
            timeline = grouped.get(entity_key)
            if timeline is None:
                timeline = {
                    "entity_key": entity_key,
                    "layer_type": "Point",
                    "source_manage_no": source_manage_no,
                    "zone_group_id": zone_group_id,
                    "facility_name": row[4],
                    "sgg_code": row[5],
                    "events": [],
                    "latest_change_type": row[11],
                    "latest_detected_at": row[9].isoformat() if row[9] else None,
                }
                grouped[entity_key] = timeline
                timelines.append(timeline)
            timeline["missing_streak"] = max(
                int(timeline.get("missing_streak") or 0),
                int(row[10] or 0),
            )
            if row[11] == "DELETED":
                timeline["status_hint"] = "DELETED_CONFIRMED"
            elif int(row[10] or 0) >= 2:
                timeline["status_hint"] = "DELETE_CANDIDATE"
            else:
                timeline["status_hint"] = "MISSING_REVIEW"
            timeline["absence"] = {
                "facility_id": str(row[0]).strip(),
                "point_ordinal": row[1],
                "first_missing_run_id": str(row[6]),
                "first_missing_at": row[7].isoformat() if row[7] else None,
                "last_missing_run_id": str(row[8]),
                "last_missing_at": row[9].isoformat() if row[9] else None,
                "missing_streak": row[10],
                "last_change_type": row[11],
            }

        deleted_polygon_manage_nos = {
            timeline.get("source_manage_no")
            for timeline in timelines
            if timeline.get("layer_type") == "Polygon"
            and timeline.get("latest_change_type") == "DELETED"
            and timeline.get("source_manage_no")
        }
        for timeline in timelines:
            if (
                timeline.get("layer_type") == "Point"
                and timeline.get("latest_change_type") == "MISSING"
                and timeline.get("source_manage_no") in deleted_polygon_manage_nos
            ):
                timeline["status_hint"] = "DELETED_CONFIRMED"

        timelines.sort(key=lambda item: item.get("latest_detected_at") or "", reverse=True)
        return {"timelines": timelines}

    def dashboard_current_zones_geojson(self) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            rows = connection.execute(
                """
                SELECT
                    zone_id::text,
                    zone_group_id,
                    source_manage_no,
                    facility_name,
                    facility_type_code,
                    sgg_code,
                    first_registered_on,
                    last_modified_on,
                    updated_at,
                    ST_AsGeoJSON(ST_Transform(geom, 4326)) AS geometry
                FROM analysis.zone_current
                ORDER BY sgg_code, facility_name, source_manage_no
                """
            ).fetchall()
            connection.rollback()
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": row[0],
                    "properties": {
                        "zone_group_id": row[1],
                        "source_manage_no": row[2],
                        "facility_name": row[3],
                        "facility_type_code": row[4],
                        "sgg_code": row[5],
                        "api_first_registered_on": row[6].isoformat() if row[6] else None,
                        "api_last_modified_on": row[7].isoformat() if row[7] else None,
                        "updated_at": row[8].isoformat() if row[8] else None,
                    },
                    "geometry": json.loads(row[9]),
                }
                for row in rows
            ],
        }

    def dashboard_current_points_geojson(self) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            rows = connection.execute(
                """
                SELECT
                    facility_id::text,
                    point_ordinal,
                    zone_group_id,
                    source_manage_no,
                    facility_name,
                    sgg_code,
                    attrs ->> 'facility_type_code' AS facility_type_code,
                    attrs ->> 'first_registered_on' AS first_registered_on,
                    attrs ->> 'last_modified_on' AS last_modified_on,
                    updated_at,
                    ST_AsGeoJSON(ST_Transform(geom, 4326)) AS geometry
                FROM analysis.zone_facility_point_current
                ORDER BY sgg_code, facility_name, source_manage_no, point_ordinal
                """
            ).fetchall()
            connection.rollback()
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": f"{row[0]}-{row[1]}",
                    "properties": {
                        "facility_id": row[0],
                        "point_ordinal": row[1],
                        "zone_group_id": row[2],
                        "source_manage_no": row[3],
                        "facility_name": row[4],
                        "sgg_code": row[5],
                        "facility_type_code": row[6],
                        "api_first_registered_on": row[7],
                        "api_last_modified_on": row[8],
                        "updated_at": row[9].isoformat() if row[9] else None,
                    },
                    "geometry": json.loads(row[10]),
                }
                for row in rows
            ],
        }

    def dashboard_change_zones_geojson(
        self,
        *,
        limit: int = 500,
        baseline_date: str | None = DEFAULT_DASHBOARD_BASELINE_DATE,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            rows = connection.execute(
                """
                SELECT
                    e.event_id,
                    e.run_id,
                    e.zone_id::text,
                    e.change_type,
                    COALESCE(e.new_snapshot ->> 'facility_name', e.old_snapshot ->> 'facility_name')
                        AS facility_name,
                    COALESCE(
                        e.new_snapshot ->> 'source_manage_no',
                        e.old_snapshot ->> 'source_manage_no'
                    )
                        AS source_manage_no,
                    COALESCE(e.new_snapshot ->> 'sgg_code', e.old_snapshot ->> 'sgg_code')
                        AS sgg_code,
                    COALESCE(e.new_snapshot ->> 'zone_group_id', e.old_snapshot ->> 'zone_group_id')
                        AS zone_group_id,
                    COALESCE(
                        e.new_snapshot ->> 'first_registered_on',
                        e.old_snapshot ->> 'first_registered_on'
                    )
                        AS first_registered_on,
                    COALESCE(
                        e.new_snapshot ->> 'last_modified_on',
                        e.old_snapshot ->> 'last_modified_on'
                    )
                        AS last_modified_on,
                    COALESCE(
                        e.new_snapshot ->> 'facility_type_code',
                        e.old_snapshot ->> 'facility_type_code'
                    )
                        AS facility_type_code,
                    e.detected_at,
                    ST_AsGeoJSON(ST_Transform(g.geom, 4326)) AS geometry
                FROM analysis.zone_change_event AS e
                JOIN LATERAL (
                    SELECT zs.geom
                    FROM analysis.zone_snapshot AS zs
                    WHERE zs.zone_id = e.zone_id
                      AND (zs.run_id = e.run_id OR zs.created_at <= e.detected_at)
                    ORDER BY (zs.run_id = e.run_id) DESC, zs.created_at DESC
                    LIMIT 1
                ) AS g ON true
                WHERE (%s::date IS NULL)
                   OR NOT (
                       e.change_type = 'NEW'
                       AND (e.detected_at AT TIME ZONE 'Asia/Seoul')::date <= %s::date
                   )
                ORDER BY e.detected_at DESC
                LIMIT %s
                """,
                (baseline_date, baseline_date, limit),
            ).fetchall()
            connection.rollback()
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": row[0],
                    "properties": {
                        "layer_type": "Polygon",
                        "run_id": str(row[1]),
                        "zone_id": row[2],
                        "change_type": row[3],
                        "facility_name": row[4],
                        "source_manage_no": row[5],
                        "sgg_code": row[6],
                        "zone_group_id": row[7],
                        "api_first_registered_on": row[8],
                        "api_last_modified_on": row[9],
                        "facility_type_code": row[10],
                        "detected_at": row[11].isoformat() if row[11] else None,
                    },
                    "geometry": json.loads(row[12]),
                }
                for row in rows
            ],
        }

    def dashboard_change_points_geojson(
        self,
        *,
        limit: int = 500,
        baseline_date: str | None = DEFAULT_DASHBOARD_BASELINE_DATE,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            rows = connection.execute(
                """
                SELECT
                    e.event_id,
                    e.run_id,
                    e.facility_id::text,
                    e.point_ordinal,
                    e.zone_group_id,
                    e.change_type,
                    COALESCE(e.new_snapshot ->> 'facility_name', e.old_snapshot ->> 'facility_name')
                        AS facility_name,
                    COALESCE(
                        e.new_snapshot ->> 'source_manage_no',
                        e.old_snapshot ->> 'source_manage_no'
                    )
                        AS source_manage_no,
                    COALESCE(e.new_snapshot ->> 'sgg_code', e.old_snapshot ->> 'sgg_code')
                        AS sgg_code,
                    COALESCE(
                        e.new_snapshot ->> 'first_registered_on',
                        e.old_snapshot ->> 'first_registered_on'
                    )
                        AS first_registered_on,
                    COALESCE(
                        e.new_snapshot ->> 'last_modified_on',
                        e.old_snapshot ->> 'last_modified_on'
                    )
                        AS last_modified_on,
                    COALESCE(
                        e.new_snapshot ->> 'facility_type_code',
                        e.old_snapshot ->> 'facility_type_code'
                    )
                        AS facility_type_code,
                    e.detected_at,
                    ST_AsGeoJSON(ST_Transform(g.geom, 4326)) AS geometry
                FROM analysis.zone_facility_point_change_event AS e
                JOIN LATERAL (
                    SELECT ps.geom
                    FROM analysis.zone_facility_point_snapshot AS ps
                    WHERE ps.facility_id = e.facility_id
                      AND ps.point_ordinal = e.point_ordinal
                      AND (ps.run_id = e.run_id OR ps.created_at <= e.detected_at)
                    ORDER BY (ps.run_id = e.run_id) DESC, ps.created_at DESC
                    LIMIT 1
                ) AS g ON true
                WHERE (%s::date IS NULL)
                   OR NOT (
                       e.change_type = 'NEW'
                       AND (e.detected_at AT TIME ZONE 'Asia/Seoul')::date <= %s::date
                   )
                ORDER BY e.detected_at DESC
                LIMIT %s
                """,
                (baseline_date, baseline_date, limit),
            ).fetchall()
            connection.rollback()
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": row[0],
                    "properties": {
                        "layer_type": "Point",
                        "run_id": str(row[1]),
                        "facility_id": row[2],
                        "point_ordinal": row[3],
                        "zone_group_id": row[4],
                        "change_type": row[5],
                        "facility_name": row[6],
                        "source_manage_no": row[7],
                        "sgg_code": row[8],
                        "api_first_registered_on": row[9],
                        "api_last_modified_on": row[10],
                        "facility_type_code": row[11],
                        "detected_at": row[12].isoformat() if row[12] else None,
                    },
                    "geometry": json.loads(row[13]),
                }
                for row in rows
            ],
        }

    def export_dashboard_data(
        self,
        output_dir: str | Path,
        *,
        event_limit: int = 500,
        baseline_date: str | None = DEFAULT_DASHBOARD_BASELINE_DATE,
    ) -> None:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        datasets = {
            "overview.json": self.dashboard_overview(),
            "change_events.json": self.dashboard_change_events(
                limit=event_limit,
                baseline_date=baseline_date,
            ),
            "current_zones.geojson": self.dashboard_current_zones_geojson(),
            "current_points.geojson": self.dashboard_current_points_geojson(),
            "change_zones.geojson": self.dashboard_change_zones_geojson(
                limit=event_limit,
                baseline_date=baseline_date,
            ),
            "change_points.geojson": self.dashboard_change_points_geojson(
                limit=event_limit,
                baseline_date=baseline_date,
            ),
            "timelines.json": self.dashboard_timelines(
                limit=event_limit * 2,
                baseline_date=baseline_date,
            ),
        }
        for filename, payload in datasets.items():
            (target / filename).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def build_link_match_candidates(
        self,
        sgg_codes: tuple[str, ...],
        *,
        near_distance_m: float = 5.0,
        max_distance_m: float = 20.0,
        strong_intersection_length_m: float = 10.0,
        strong_intersection_ratio: float = 0.3,
    ) -> dict[str, Any]:
        if not sgg_codes:
            raise ValueError("At least one SGG code is required")

        with self._connect() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext('zone-link-match-candidates'))"
            )
            latest_run_id = connection.execute(
                "SELECT pipeline_run_id FROM ops.pipeline_run "
                "WHERE status = 'SUCCESS' ORDER BY finished_at DESC LIMIT 1"
            ).fetchone()
            connection.execute(
                "DELETE FROM analysis.zone_link_match_candidate WHERE sgg_code = ANY(%s)",
                (list(sgg_codes),),
            )
            connection.execute(
                """
                WITH scoped_zones AS (
                    SELECT
                        zone_id,
                        zone_group_id,
                        source_manage_no,
                        facility_name,
                        sgg_code,
                        geom
                    FROM analysis.zone_current
                    WHERE sgg_code = ANY(%(sgg_codes)s)
                ),
                raw_candidates AS (
                    SELECT
                        z.zone_id,
                        z.zone_group_id,
                        z.source_manage_no,
                        z.facility_name,
                        z.sgg_code,
                        l.link_id,
                        metrics.intersects,
                        metrics.distance_m,
                        metrics.link_length_m,
                        CASE
                            WHEN metrics.intersects THEN
                                ST_Length(
                                    ST_CollectionExtract(
                                        ST_Intersection(z.geom, l.geom),
                                        2
                                    )
                                )
                            ELSE 0::double precision
                        END AS intersection_length_m
                    FROM scoped_zones AS z
                    JOIN mobility.std_link AS l
                      ON ST_DWithin(z.geom, l.geom, %(max_distance_m)s)
                    CROSS JOIN LATERAL (
                        SELECT
                            ST_Intersects(z.geom, l.geom) AS intersects,
                            ST_Distance(z.geom, l.geom) AS distance_m,
                            COALESCE(NULLIF(l.length_m, 0), ST_Length(l.geom))
                                AS link_length_m
                    ) AS metrics
                ),
                classified AS (
                    SELECT
                        *,
                        CASE
                            WHEN link_length_m > 0
                                THEN intersection_length_m / link_length_m
                            ELSE 0::double precision
                        END AS intersection_ratio
                    FROM raw_candidates
                ),
                graded AS (
                    SELECT
                        *,
                        CASE
                            WHEN intersects
                             AND (
                                intersection_length_m >= %(strong_intersection_length_m)s
                                OR intersection_ratio >= %(strong_intersection_ratio)s
                             )
                                THEN 'A'
                            WHEN intersects
                                THEN 'B'
                            WHEN distance_m <= %(near_distance_m)s
                                THEN 'C'
                            ELSE 'D'
                        END AS candidate_grade
                    FROM classified
                )
                INSERT INTO analysis.zone_link_match_candidate (
                    zone_id,
                    zone_group_id,
                    source_manage_no,
                    facility_name,
                    sgg_code,
                    link_id,
                    candidate_grade,
                    review_status,
                    distance_m,
                    intersection_length_m,
                    link_length_m,
                    intersection_ratio,
                    match_reason,
                    created_run_id
                )
                SELECT
                    zone_id,
                    zone_group_id,
                    source_manage_no,
                    facility_name,
                    sgg_code,
                    link_id,
                    candidate_grade,
                    CASE
                        WHEN candidate_grade = 'A' THEN 'AUTO_CANDIDATE'
                        ELSE 'NEEDS_REVIEW'
                    END AS review_status,
                    distance_m,
                    intersection_length_m,
                    link_length_m,
                    intersection_ratio,
                    CASE candidate_grade
                        WHEN 'A' THEN 'strong polygon-link intersection'
                        WHEN 'B' THEN 'weak polygon-link intersection'
                        WHEN 'C' THEN 'non-intersecting link within 5m'
                        ELSE 'non-intersecting link within 20m'
                    END AS match_reason,
                    %(latest_run_id)s
                FROM graded
                ON CONFLICT (zone_id, link_id) DO UPDATE SET
                    zone_group_id = EXCLUDED.zone_group_id,
                    source_manage_no = EXCLUDED.source_manage_no,
                    facility_name = EXCLUDED.facility_name,
                    sgg_code = EXCLUDED.sgg_code,
                    candidate_grade = EXCLUDED.candidate_grade,
                    review_status = EXCLUDED.review_status,
                    distance_m = EXCLUDED.distance_m,
                    intersection_length_m = EXCLUDED.intersection_length_m,
                    link_length_m = EXCLUDED.link_length_m,
                    intersection_ratio = EXCLUDED.intersection_ratio,
                    match_reason = EXCLUDED.match_reason,
                    created_run_id = EXCLUDED.created_run_id,
                    updated_at = now()
                """,
                {
                    "sgg_codes": list(sgg_codes),
                    "near_distance_m": near_distance_m,
                    "max_distance_m": max_distance_m,
                    "strong_intersection_length_m": strong_intersection_length_m,
                    "strong_intersection_ratio": strong_intersection_ratio,
                    "latest_run_id": latest_run_id[0] if latest_run_id else None,
                },
            )
            counts = connection.execute(
                """
                SELECT candidate_grade, review_status, COUNT(*)::integer
                FROM analysis.zone_link_match_candidate
                WHERE sgg_code = ANY(%s)
                GROUP BY candidate_grade, review_status
                ORDER BY candidate_grade, review_status
                """,
                (list(sgg_codes),),
            ).fetchall()
            total = sum(row[2] for row in counts)

        return {
            "sgg_codes": sgg_codes,
            "total_candidates": total,
            "counts": [
                {"candidate_grade": row[0], "review_status": row[1], "count": row[2]}
                for row in counts
            ],
            "thresholds": {
                "near_distance_m": near_distance_m,
                "max_distance_m": max_distance_m,
                "strong_intersection_length_m": strong_intersection_length_m,
                "strong_intersection_ratio": strong_intersection_ratio,
            },
        }

    def build_link_match_candidates_v2(
        self,
        sgg_codes: tuple[str, ...],
        *,
        near_distance_m: float = 5.0,
        max_distance_m: float = 20.0,
        strong_intersection_length_m: float = 20.0,
        strong_intersection_ratio: float = 0.2,
        weak_intersection_length_m: float = 10.0,
        weak_intersection_ratio: float = 0.1,
        short_link_length_m: float = 20.0,
        short_link_inside_ratio: float = 0.5,
        near_parallel_length_m: float = 20.0,
        near_parallel_ratio: float = 0.2,
        tiny_adjacency_length_m: float = 10.0,
        tiny_adjacency_ratio: float = 0.1,
        junction_link_length_m: float = 35.0,
    ) -> dict[str, Any]:
        """Build second-round standard-link candidates with stricter review rules."""
        if not sgg_codes:
            raise ValueError("At least one SGG code is required")

        params = {
            "sgg_codes": list(sgg_codes),
            "near_distance_m": near_distance_m,
            "max_distance_m": max_distance_m,
            "strong_intersection_length_m": strong_intersection_length_m,
            "strong_intersection_ratio": strong_intersection_ratio,
            "weak_intersection_length_m": weak_intersection_length_m,
            "weak_intersection_ratio": weak_intersection_ratio,
            "short_link_length_m": short_link_length_m,
            "short_link_inside_ratio": short_link_inside_ratio,
            "near_parallel_length_m": near_parallel_length_m,
            "near_parallel_ratio": near_parallel_ratio,
            "tiny_adjacency_length_m": tiny_adjacency_length_m,
            "tiny_adjacency_ratio": tiny_adjacency_ratio,
            "junction_link_length_m": junction_link_length_m,
        }

        with self._connect() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext('zone-link-match-candidates-v2'))"
            )
            latest_run_id = connection.execute(
                "SELECT pipeline_run_id FROM ops.pipeline_run "
                "WHERE status = 'SUCCESS' ORDER BY finished_at DESC LIMIT 1"
            ).fetchone()
            params["latest_run_id"] = latest_run_id[0] if latest_run_id else None

            connection.execute(
                "DELETE FROM analysis.zone_link_match_candidate_v2 WHERE sgg_code = ANY(%s)",
                (list(sgg_codes),),
            )
            connection.execute(
                "DELETE FROM analysis.zone_link_match_excluded_v2 WHERE sgg_code = ANY(%s)",
                (list(sgg_codes),),
            )
            connection.execute("DROP TABLE IF EXISTS tmp_zone_link_raw_v2")
            connection.execute("DROP TABLE IF EXISTS tmp_zone_link_seeds_v2")
            connection.execute("DROP TABLE IF EXISTS tmp_zone_link_evaluated_v2")
            connection.execute(
                """
                CREATE TEMP TABLE tmp_zone_link_raw_v2 ON COMMIT DROP AS
                WITH scoped_zones AS (
                    SELECT
                        zone_id,
                        zone_group_id,
                        source_manage_no,
                        facility_name,
                        sgg_code,
                        geom
                    FROM analysis.zone_current
                    WHERE sgg_code = ANY(%(sgg_codes)s)
                ),
                raw_candidates AS (
                    SELECT
                        z.zone_id,
                        z.zone_group_id,
                        z.source_manage_no,
                        z.facility_name,
                        z.sgg_code,
                        l.link_id,
                        l.road_name,
                        l.road_rank,
                        l.road_type,
                        l.road_no,
                        l.connect,
                        l.multi_link,
                        l.f_node_id,
                        l.t_node_id,
                        metrics.intersects,
                        metrics.distance_m,
                        metrics.link_length_m,
                        metrics.link_midpoint_inside_zone,
                        metrics.proximity_overlap_length_m,
                        CASE
                            WHEN metrics.intersects THEN
                                ST_Length(
                                    ST_CollectionExtract(
                                        ST_Intersection(z.geom, l.geom),
                                        2
                                    )
                                )
                            ELSE 0::double precision
                        END AS intersection_length_m
                    FROM scoped_zones AS z
                    JOIN mobility.std_link AS l
                      ON ST_DWithin(z.geom, l.geom, %(max_distance_m)s)
                    CROSS JOIN LATERAL (
                        SELECT
                            ST_Intersects(z.geom, l.geom) AS intersects,
                            ST_Distance(z.geom, l.geom) AS distance_m,
                            COALESCE(NULLIF(l.length_m, 0), ST_Length(l.geom))
                                AS link_length_m,
                            ST_Covers(z.geom, ST_Centroid(l.geom))
                                AS link_midpoint_inside_zone,
                            ST_Length(
                                ST_CollectionExtract(
                                    ST_Intersection(
                                        ST_Buffer(z.geom, %(near_distance_m)s),
                                        l.geom
                                    ),
                                    2
                                )
                            ) AS proximity_overlap_length_m
                    ) AS metrics
                )
                SELECT
                    *,
                    CASE
                        WHEN link_length_m > 0
                            THEN intersection_length_m / link_length_m
                        ELSE 0::double precision
                    END AS intersection_ratio,
                    CASE
                        WHEN link_length_m > 0
                            THEN proximity_overlap_length_m / link_length_m
                        ELSE 0::double precision
                    END AS proximity_overlap_ratio,
                    (
                        intersects
                        AND (
                            intersection_length_m < %(weak_intersection_length_m)s
                            OR CASE
                                WHEN link_length_m > 0
                                    THEN intersection_length_m / link_length_m
                                ELSE 0::double precision
                            END < %(weak_intersection_ratio)s
                        )
                    ) AS is_touch_or_graze
                FROM raw_candidates
                """,
                params,
            )
            connection.execute(
                "CREATE INDEX tmp_zone_link_raw_v2_group_idx "
                "ON tmp_zone_link_raw_v2 (zone_group_id)"
            )
            connection.execute(
                "CREATE INDEX tmp_zone_link_raw_v2_intersects_idx "
                "ON tmp_zone_link_raw_v2 (intersects)"
            )
            connection.execute(
                "CREATE INDEX tmp_zone_link_raw_v2_node_idx "
                "ON tmp_zone_link_raw_v2 (f_node_id, t_node_id)"
            )
            connection.execute("ANALYZE tmp_zone_link_raw_v2")
            connection.execute(
                """
                CREATE TEMP TABLE tmp_zone_link_seeds_v2 ON COMMIT DROP AS
                SELECT
                    *,
                    CASE
                        WHEN intersection_length_m >= %(strong_intersection_length_m)s
                         AND intersection_ratio >= %(strong_intersection_ratio)s
                            THEN 'A'
                        WHEN link_length_m < %(short_link_length_m)s
                         AND intersection_ratio >= %(short_link_inside_ratio)s
                         AND link_midpoint_inside_zone
                            THEN 'A'
                        ELSE 'B'
                    END AS seed_grade
                FROM tmp_zone_link_raw_v2
                WHERE intersects
                  AND (
                    (
                        intersection_length_m >= %(weak_intersection_length_m)s
                        AND intersection_ratio >= %(weak_intersection_ratio)s
                    )
                    OR (
                        link_length_m < %(short_link_length_m)s
                        AND intersection_ratio >= %(short_link_inside_ratio)s
                        AND link_midpoint_inside_zone
                    )
                  )
                """,
                params,
            )
            connection.execute(
                "CREATE INDEX tmp_zone_link_seeds_v2_group_idx "
                "ON tmp_zone_link_seeds_v2 (zone_group_id)"
            )
            connection.execute(
                "CREATE INDEX tmp_zone_link_seeds_v2_road_name_idx "
                "ON tmp_zone_link_seeds_v2 (zone_group_id, road_name)"
            )
            connection.execute(
                "CREATE INDEX tmp_zone_link_seeds_v2_road_no_idx "
                "ON tmp_zone_link_seeds_v2 (zone_group_id, road_no)"
            )
            connection.execute(
                "CREATE INDEX tmp_zone_link_seeds_v2_node_idx "
                "ON tmp_zone_link_seeds_v2 (zone_group_id, f_node_id, t_node_id)"
            )
            connection.execute("ANALYZE tmp_zone_link_seeds_v2")
            connection.execute(
                """
                CREATE TEMP TABLE tmp_zone_link_evaluated_v2 ON COMMIT DROP AS
                SELECT
                    r.*,
                    seed.seed_link_id,
                    COALESCE(seed.same_road_as_seed, false) AS same_road_as_seed,
                    COALESCE(seed.connected_to_seed, false) AS connected_to_seed,
                    (
                        r.road_rank IN ('101', '102')
                        AND r.intersects
                        AND r.intersection_length_m >= %(weak_intersection_length_m)s
                        AND r.intersection_ratio >= %(weak_intersection_ratio)s
                    ) AS potential_grade_separated,
                    CASE
                        WHEN r.road_rank IN ('101', '102')
                         AND r.intersects
                         AND r.intersection_length_m >= %(weak_intersection_length_m)s
                         AND r.intersection_ratio >= %(weak_intersection_ratio)s
                            THEN 'B'
                        WHEN r.intersects
                         AND r.intersection_length_m >= %(strong_intersection_length_m)s
                         AND r.intersection_ratio >= %(strong_intersection_ratio)s
                            THEN 'A'
                        WHEN r.intersects
                         AND r.link_length_m < %(short_link_length_m)s
                         AND r.intersection_ratio >= %(short_link_inside_ratio)s
                         AND r.link_midpoint_inside_zone
                            THEN 'A'
                        WHEN r.distance_m <= %(near_distance_m)s
                         AND r.proximity_overlap_length_m >= %(near_parallel_length_m)s
                         AND r.proximity_overlap_ratio >= %(near_parallel_ratio)s
                            THEN 'A'
                        WHEN r.distance_m <= %(near_distance_m)s
                         AND seed.seed_link_id IS NOT NULL
                         AND seed.connected_to_seed
                         AND (
                            r.link_length_m <= %(junction_link_length_m)s
                            OR r.proximity_overlap_ratio >= %(short_link_inside_ratio)s
                         )
                            THEN 'A'
                        WHEN r.intersects
                         AND r.intersection_length_m >= %(weak_intersection_length_m)s
                         AND r.intersection_ratio >= %(weak_intersection_ratio)s
                            THEN 'B'
                        WHEN NOT r.intersects
                         AND r.distance_m <= %(near_distance_m)s
                         AND NOT (
                            r.proximity_overlap_length_m < %(tiny_adjacency_length_m)s
                            AND r.proximity_overlap_ratio < %(tiny_adjacency_ratio)s
                         )
                         AND seed.seed_link_id IS NOT NULL
                         AND (seed.same_road_as_seed OR seed.connected_to_seed)
                            THEN 'C'
                        WHEN NOT r.intersects
                         AND r.distance_m <= %(max_distance_m)s
                         AND seed.seed_link_id IS NOT NULL
                         AND seed.connected_to_seed
                            THEN 'D'
                    END AS candidate_grade
                FROM tmp_zone_link_raw_v2 AS r
                LEFT JOIN LATERAL (
                    SELECT
                        s.link_id AS seed_link_id,
                        (
                            NULLIF(r.road_name, '') IS NOT NULL
                            AND r.road_name = s.road_name
                        )
                        OR (
                            NULLIF(r.road_no, '') IS NOT NULL
                            AND r.road_no = s.road_no
                        ) AS same_road_as_seed,
                        r.f_node_id IN (s.f_node_id, s.t_node_id)
                        OR r.t_node_id IN (s.f_node_id, s.t_node_id)
                            AS connected_to_seed
                    FROM tmp_zone_link_seeds_v2 AS s
                    WHERE s.zone_group_id = r.zone_group_id
                      AND s.link_id <> r.link_id
                      AND (
                        (
                            NULLIF(r.road_name, '') IS NOT NULL
                            AND r.road_name = s.road_name
                        )
                        OR (
                            NULLIF(r.road_no, '') IS NOT NULL
                            AND r.road_no = s.road_no
                        )
                        OR r.f_node_id IN (s.f_node_id, s.t_node_id)
                        OR r.t_node_id IN (s.f_node_id, s.t_node_id)
                      )
                    ORDER BY
                        CASE s.seed_grade WHEN 'A' THEN 1 ELSE 2 END,
                        s.distance_m,
                        s.link_id
                    LIMIT 1
                ) AS seed ON NOT r.intersects
                """,
                params,
            )
            connection.execute(
                "CREATE INDEX tmp_zone_link_evaluated_v2_grade_idx "
                "ON tmp_zone_link_evaluated_v2 (candidate_grade)"
            )
            connection.execute(
                "CREATE INDEX tmp_zone_link_evaluated_v2_sgg_idx "
                "ON tmp_zone_link_evaluated_v2 (sgg_code)"
            )
            connection.execute("ANALYZE tmp_zone_link_evaluated_v2")
            connection.execute(
                """
                INSERT INTO analysis.zone_link_match_candidate_v2 (
                    zone_id,
                    zone_group_id,
                    source_manage_no,
                    facility_name,
                    sgg_code,
                    link_id,
                    candidate_grade,
                    review_status,
                    distance_m,
                    intersection_length_m,
                    link_length_m,
                    intersection_ratio,
                    proximity_overlap_length_m,
                    proximity_overlap_ratio,
                    match_rule_code,
                    match_rule_description,
                    is_touch_or_graze,
                    potential_grade_separated,
                    link_midpoint_inside_zone,
                    same_road_as_seed,
                    connected_to_seed,
                    seed_link_id,
                    created_run_id
                )
                SELECT
                    zone_id,
                    zone_group_id,
                    source_manage_no,
                    facility_name,
                    sgg_code,
                    link_id,
                    candidate_grade,
                    CASE
                        WHEN candidate_grade = 'A' THEN 'AUTO_CANDIDATE'
                        ELSE 'NEEDS_REVIEW'
                    END AS review_status,
                    distance_m,
                    intersection_length_m,
                    link_length_m,
                    intersection_ratio,
                    proximity_overlap_length_m,
                    proximity_overlap_ratio,
                    CASE candidate_grade
                        WHEN 'A' THEN
                            CASE
                                WHEN intersects
                                 AND intersection_length_m >= %(strong_intersection_length_m)s
                                 AND intersection_ratio >= %(strong_intersection_ratio)s
                                    THEN 'A_STRONG_OVERLAP'
                                WHEN intersects
                                 AND link_length_m < %(short_link_length_m)s
                                 AND intersection_ratio >= %(short_link_inside_ratio)s
                                 AND link_midpoint_inside_zone
                                    THEN 'A_SHORT_INSIDE'
                                WHEN distance_m <= %(near_distance_m)s
                                 AND proximity_overlap_length_m >= %(near_parallel_length_m)s
                                 AND proximity_overlap_ratio >= %(near_parallel_ratio)s
                                    THEN 'A_NEAR_PARALLEL_CORRIDOR'
                                ELSE 'A_JUNCTION_COMPONENT'
                            END
                        WHEN 'B' THEN
                            CASE
                                WHEN potential_grade_separated THEN 'B_POTENTIAL_GRADE_SEPARATED'
                                ELSE 'B_WEAK_OVERLAP'
                            END
                        WHEN 'C' THEN 'C_NEAR_CONNECTED_OR_SAME_ROAD'
                        ELSE 'D_EXTENDED_NODE_CONNECTED'
                    END AS match_rule_code,
                    CASE candidate_grade
                        WHEN 'A' THEN
                            CASE
                                WHEN intersects
                                 AND intersection_length_m >= %(strong_intersection_length_m)s
                                 AND intersection_ratio >= %(strong_intersection_ratio)s
                                    THEN 'direct overlap meeting both length and ratio thresholds'
                                WHEN intersects
                                 AND link_length_m < %(short_link_length_m)s
                                 AND intersection_ratio >= %(short_link_inside_ratio)s
                                 AND link_midpoint_inside_zone
                                    THEN 'short link mostly inside the protection-zone polygon'
                                WHEN distance_m <= %(near_distance_m)s
                                 AND proximity_overlap_length_m >= %(near_parallel_length_m)s
                                 AND proximity_overlap_ratio >= %(near_parallel_ratio)s
                                    THEN 'near parallel corridor inside the zone buffer'
                                ELSE 'short or buffered junction link connected to a seed'
                            END
                        WHEN 'B' THEN
                            CASE
                                WHEN potential_grade_separated
                                    THEN 'high-rank overlap kept for grade-separation review'
                                ELSE 'direct overlap meeting weak length and ratio thresholds'
                            END
                        WHEN 'C'
                            THEN 'nearby non-intersecting link tied to an A/B seed'
                        ELSE 'extended nearby non-intersecting link node-connected to an A/B seed'
                    END AS match_rule_description,
                    is_touch_or_graze,
                    potential_grade_separated,
                    link_midpoint_inside_zone,
                    CASE WHEN candidate_grade IN ('A', 'B') THEN false ELSE same_road_as_seed END,
                    CASE WHEN candidate_grade IN ('A', 'B') THEN false ELSE connected_to_seed END,
                    CASE WHEN candidate_grade IN ('A', 'B') THEN link_id ELSE seed_link_id END,
                    %(latest_run_id)s
                FROM tmp_zone_link_evaluated_v2
                WHERE candidate_grade IS NOT NULL
                ON CONFLICT (zone_id, link_id) DO UPDATE SET
                    zone_group_id = EXCLUDED.zone_group_id,
                    source_manage_no = EXCLUDED.source_manage_no,
                    facility_name = EXCLUDED.facility_name,
                    sgg_code = EXCLUDED.sgg_code,
                    candidate_grade = EXCLUDED.candidate_grade,
                    review_status = EXCLUDED.review_status,
                    distance_m = EXCLUDED.distance_m,
                    intersection_length_m = EXCLUDED.intersection_length_m,
                    link_length_m = EXCLUDED.link_length_m,
                    intersection_ratio = EXCLUDED.intersection_ratio,
                    proximity_overlap_length_m = EXCLUDED.proximity_overlap_length_m,
                    proximity_overlap_ratio = EXCLUDED.proximity_overlap_ratio,
                    match_rule_code = EXCLUDED.match_rule_code,
                    match_rule_description = EXCLUDED.match_rule_description,
                    is_touch_or_graze = EXCLUDED.is_touch_or_graze,
                    potential_grade_separated = EXCLUDED.potential_grade_separated,
                    link_midpoint_inside_zone = EXCLUDED.link_midpoint_inside_zone,
                    same_road_as_seed = EXCLUDED.same_road_as_seed,
                    connected_to_seed = EXCLUDED.connected_to_seed,
                    seed_link_id = EXCLUDED.seed_link_id,
                    created_run_id = EXCLUDED.created_run_id,
                    updated_at = now()
                """,
                params,
            )
            connection.execute(
                """
                INSERT INTO analysis.zone_link_match_excluded_v2 (
                    zone_id,
                    zone_group_id,
                    source_manage_no,
                    facility_name,
                    sgg_code,
                    link_id,
                    distance_m,
                    intersection_length_m,
                    link_length_m,
                    intersection_ratio,
                    proximity_overlap_length_m,
                    proximity_overlap_ratio,
                    exclusion_code,
                    exclusion_reason,
                    is_touch_or_graze,
                    potential_grade_separated,
                    link_midpoint_inside_zone,
                    created_run_id
                )
                SELECT
                    zone_id,
                    zone_group_id,
                    source_manage_no,
                    facility_name,
                    sgg_code,
                    link_id,
                    distance_m,
                    intersection_length_m,
                    link_length_m,
                    intersection_ratio,
                    proximity_overlap_length_m,
                    proximity_overlap_ratio,
                    CASE
                        WHEN is_touch_or_graze THEN 'TOUCH_OR_GRAZE'
                        WHEN distance_m <= %(near_distance_m)s
                         AND proximity_overlap_length_m < %(tiny_adjacency_length_m)s
                         AND proximity_overlap_ratio < %(tiny_adjacency_ratio)s
                            THEN 'TINY_ADJACENCY'
                        WHEN NOT intersects AND seed_link_id IS NULL THEN 'NO_AB_SEED'
                        WHEN NOT intersects
                         AND distance_m <= %(near_distance_m)s
                         AND NOT (same_road_as_seed OR connected_to_seed)
                            THEN 'NEAR_BUT_UNRELATED_TO_SEED'
                        WHEN NOT intersects
                         AND distance_m <= %(max_distance_m)s
                         AND NOT connected_to_seed
                            THEN 'EXTENDED_BUT_NOT_NODE_CONNECTED'
                        ELSE 'V2_RULE_EXCLUDED'
                    END AS exclusion_code,
                    CASE
                        WHEN is_touch_or_graze
                            THEN 'link only touches or grazes the zone boundary'
                        WHEN distance_m <= %(near_distance_m)s
                         AND proximity_overlap_length_m < %(tiny_adjacency_length_m)s
                         AND proximity_overlap_ratio < %(tiny_adjacency_ratio)s
                            THEN 'nearby link has only tiny adjacency to the protection-zone buffer'
                        WHEN NOT intersects AND seed_link_id IS NULL
                            THEN 'no A/B seed exists in the same zone group'
                        WHEN NOT intersects
                         AND distance_m <= %(near_distance_m)s
                         AND NOT (same_road_as_seed OR connected_to_seed)
                            THEN 'nearby link is not same-road or node-connected to a seed'
                        WHEN NOT intersects
                         AND distance_m <= %(max_distance_m)s
                         AND NOT connected_to_seed
                            THEN 'extended-distance link is not node-connected to a seed'
                        ELSE 'candidate did not satisfy second-round rules'
                    END AS exclusion_reason,
                    is_touch_or_graze,
                    potential_grade_separated,
                    link_midpoint_inside_zone,
                    %(latest_run_id)s
                FROM tmp_zone_link_evaluated_v2
                WHERE candidate_grade IS NULL
                ON CONFLICT (zone_id, link_id) DO UPDATE SET
                    zone_group_id = EXCLUDED.zone_group_id,
                    source_manage_no = EXCLUDED.source_manage_no,
                    facility_name = EXCLUDED.facility_name,
                    sgg_code = EXCLUDED.sgg_code,
                    distance_m = EXCLUDED.distance_m,
                    intersection_length_m = EXCLUDED.intersection_length_m,
                    link_length_m = EXCLUDED.link_length_m,
                    intersection_ratio = EXCLUDED.intersection_ratio,
                    proximity_overlap_length_m = EXCLUDED.proximity_overlap_length_m,
                    proximity_overlap_ratio = EXCLUDED.proximity_overlap_ratio,
                    exclusion_code = EXCLUDED.exclusion_code,
                    exclusion_reason = EXCLUDED.exclusion_reason,
                    is_touch_or_graze = EXCLUDED.is_touch_or_graze,
                    potential_grade_separated = EXCLUDED.potential_grade_separated,
                    link_midpoint_inside_zone = EXCLUDED.link_midpoint_inside_zone,
                    created_run_id = EXCLUDED.created_run_id,
                    updated_at = now()
                """,
                params,
            )
            counts = connection.execute(
                """
                SELECT candidate_grade, review_status, COUNT(*)::integer
                FROM analysis.zone_link_match_candidate_v2
                WHERE sgg_code = ANY(%s)
                GROUP BY candidate_grade, review_status
                ORDER BY candidate_grade, review_status
                """,
                (list(sgg_codes),),
            ).fetchall()
            excluded_counts = connection.execute(
                """
                SELECT exclusion_code, COUNT(*)::integer
                FROM analysis.zone_link_match_excluded_v2
                WHERE sgg_code = ANY(%s)
                GROUP BY exclusion_code
                ORDER BY exclusion_code
                """,
                (list(sgg_codes),),
            ).fetchall()
            coverage_counts = connection.execute(
                """
                SELECT coverage_status, COUNT(*)::integer
                FROM analysis.v_zone_link_match_coverage_v2
                WHERE sgg_code = ANY(%s)
                GROUP BY coverage_status
                ORDER BY coverage_status
                """,
                (list(sgg_codes),),
            ).fetchall()
            total = sum(row[2] for row in counts)
            excluded_total = sum(row[1] for row in excluded_counts)

        return {
            "sgg_codes": sgg_codes,
            "total_candidates": total,
            "total_excluded": excluded_total,
            "counts": [
                {"candidate_grade": row[0], "review_status": row[1], "count": row[2]}
                for row in counts
            ],
            "excluded_counts": [
                {"exclusion_code": row[0], "count": row[1]} for row in excluded_counts
            ],
            "coverage_counts": [
                {"coverage_status": row[0], "count": row[1]} for row in coverage_counts
            ],
            "thresholds": {
                "near_distance_m": near_distance_m,
                "max_distance_m": max_distance_m,
                "strong_intersection_length_m": strong_intersection_length_m,
                "strong_intersection_ratio": strong_intersection_ratio,
                "weak_intersection_length_m": weak_intersection_length_m,
                "weak_intersection_ratio": weak_intersection_ratio,
                "short_link_length_m": short_link_length_m,
                "short_link_inside_ratio": short_link_inside_ratio,
                "near_parallel_length_m": near_parallel_length_m,
                "near_parallel_ratio": near_parallel_ratio,
                "tiny_adjacency_length_m": tiny_adjacency_length_m,
                "tiny_adjacency_ratio": tiny_adjacency_ratio,
                "junction_link_length_m": junction_link_length_m,
            },
        }
