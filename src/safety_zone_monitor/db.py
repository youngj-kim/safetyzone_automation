from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

import psycopg

from safety_zone_monitor.diff import ChangeType, DiffResult, ExistingZone, detect_changes
from safety_zone_monitor.normalize import ZoneRecord, clean_text, stable_hash


@dataclass(frozen=True)
class RunSummary:
    run_id: uuid.UUID
    fetched_count: int
    polygon_count: int
    skipped_non_polygon_count: int
    skipped_inactive_count: int
    diff: DiffResult

    @property
    def change_count(self) -> int:
        return len(self.diff.changes)


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

    @staticmethod
    def _record_values(record: ZoneRecord, run_id: uuid.UUID) -> tuple[object, ...]:
        return (
            record.zone_id,
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
        skipped_non_polygon_count: int,
        skipped_inactive_count: int,
    ) -> RunSummary:
        incoming_sgg_codes = {record.sgg_code for record in records}
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
                        "(run_id, zone_id, attr_hash, geom_hash, data_hash, attrs, geom) "
                        "VALUES (%s, %s, %s, %s, %s, %s::jsonb, "
                        "ST_Multi(ST_Transform(ST_GeomFromText(%s, 5181), 5179))::"
                        "geometry(MultiPolygon, 5179))",
                        [
                            (
                                run_id,
                                record.zone_id,
                                record.attr_hash,
                                record.geom_hash,
                                record.data_hash,
                                json.dumps(record.attributes(), ensure_ascii=False),
                                record.geometry_wkt,
                            )
                            for record in records
                        ],
                    )

            current = self._load_current(connection, sgg_codes)
            diff = detect_changes(records, current)
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

            upsert_sql = """
                INSERT INTO analysis.zone_current (
                    zone_id, attr_hash, geom_hash, data_hash, source_manage_no, project_no,
                    facility_name, facility_type_code, facility_detail_type_code,
                    representative_manage_no, use_yn, sgg_code, emdong_code, stdg_code,
                    assign_type, road_address, road_detail_address, lot_address,
                    lot_detail_address, first_registered_on, last_modified_on, geom, attrs,
                    last_run_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    ST_Multi(ST_Transform(ST_GeomFromText(%s, 5181), 5179))::
                        geometry(MultiPolygon, 5179),
                    %s::jsonb, %s
                )
                ON CONFLICT (zone_id) DO UPDATE SET
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
                skipped_non_polygon_count,
                skipped_inactive_count,
                diff.count(ChangeType.NEW),
                diff.count(ChangeType.GEOMETRY_CHANGED),
                diff.count(ChangeType.ATTRIBUTE_CHANGED),
                diff.count(ChangeType.GEOMETRY_ATTRIBUTE_CHANGED),
                diff.count(ChangeType.UNCHANGED),
                diff.count(ChangeType.DELETED),
                run_id,
            )
            connection.execute(
                """
                UPDATE ops.pipeline_run SET
                    status = 'SUCCESS', finished_at = now(), fetched_count = %s,
                    polygon_count = %s, skipped_non_polygon_count = %s,
                    skipped_inactive_count = %s,
                    new_count = %s, geometry_changed_count = %s,
                    attribute_changed_count = %s, geometry_attribute_changed_count = %s,
                    unchanged_count = %s, deleted_count = %s
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
            skipped_non_polygon_count=skipped_non_polygon_count,
            skipped_inactive_count=skipped_inactive_count,
            diff=diff,
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
