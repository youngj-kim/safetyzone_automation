from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from importlib.resources import files
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
            point_diff = detect_point_changes(facility_points, current_points)
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
            if event_rows:
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
            if point_event_rows:
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
                if change.change_type is PointChangeType.MISSING
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

            metrics = (
                len(raw_items),
                len(records),
                len(facility_points),
                point_only_record_count,
                skipped_non_polygon_count,
                skipped_inactive_count,
                diff.count(ChangeType.NEW),
                diff.count(ChangeType.GEOMETRY_CHANGED),
                diff.count(ChangeType.ATTRIBUTE_CHANGED),
                diff.count(ChangeType.GEOMETRY_ATTRIBUTE_CHANGED),
                diff.count(ChangeType.UNCHANGED),
                diff.count(ChangeType.DELETED),
                point_diff.count(PointChangeType.NEW),
                sum(
                    point_diff.count(change_type)
                    for change_type in (
                        PointChangeType.POINT_CHANGED,
                        PointChangeType.ATTRIBUTE_CHANGED,
                        PointChangeType.POINT_ATTRIBUTE_CHANGED,
                    )
                ),
                point_diff.count(PointChangeType.UNCHANGED),
                point_diff.count(PointChangeType.MISSING),
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
                    point_unchanged_count = %s, point_missing_count = %s
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
            diff=diff,
            point_diff=point_diff,
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
