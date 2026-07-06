from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from importlib.resources import files

import psycopg

from safety_zone_monitor.diff import ChangeType, DiffResult, ExistingZone, detect_changes
from safety_zone_monitor.normalize import ZoneRecord


@dataclass(frozen=True)
class RunSummary:
    run_id: uuid.UUID
    fetched_count: int
    polygon_count: int
    skipped_non_polygon_count: int
    diff: DiffResult

    @property
    def change_count(self) -> int:
        return len(self.diff.changes)


class Repository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def migrate(self) -> None:
        migration_dir = files("safety_zone_monitor").joinpath("migrations")
        with psycopg.connect(self.database_url) as connection:
            for migration in sorted(migration_dir.iterdir(), key=lambda path: path.name):
                if migration.name.endswith(".sql"):
                    connection.execute(migration.read_text(encoding="utf-8"))

    def create_run(self, sgg_codes: tuple[str, ...]) -> uuid.UUID:
        run_id = uuid.uuid4()
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "INSERT INTO ingestion_run (run_id, status, monitored_sgg_codes) "
                "VALUES (%s, 'RUNNING', %s)",
                (run_id, list(sgg_codes)),
            )
        return run_id

    def mark_failed(self, run_id: uuid.UUID, error: Exception) -> None:
        message = f"{type(error).__name__}: {error}"[:4000]
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "UPDATE ingestion_run SET status = 'FAILED', finished_at = now(), "
                "error_message = %s WHERE run_id = %s AND status = 'RUNNING'",
                (message, run_id),
            )

    def _load_current(
        self,
        connection: psycopg.Connection,
        sgg_codes: tuple[str, ...],
    ) -> dict[str, ExistingZone]:
        rows = connection.execute(
            "SELECT zone_key, data_hash, snapshot FROM safety_zone WHERE sgg_code = ANY(%s)",
            (list(sgg_codes),),
        ).fetchall()
        return {
            str(row[0]).strip(): ExistingZone(
                zone_key=str(row[0]).strip(),
                data_hash=str(row[1]).strip(),
                snapshot=row[2],
            )
            for row in rows
        }

    @staticmethod
    def _record_values(record: ZoneRecord, run_id: uuid.UUID) -> tuple[object, ...]:
        return (
            record.zone_key,
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
            record.geometry_wkt,
            json.dumps(record.snapshot(), ensure_ascii=False),
            run_id,
        )

    def apply_run(
        self,
        *,
        run_id: uuid.UUID,
        sgg_codes: tuple[str, ...],
        records: list[ZoneRecord],
        fetched_count: int,
        skipped_non_polygon_count: int,
    ) -> RunSummary:
        incoming_sgg_codes = {record.sgg_code for record in records}
        if not incoming_sgg_codes.issubset(set(sgg_codes)):
            raise ValueError("API returned a record outside the configured SGG scope")

        with psycopg.connect(self.database_url) as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext('safety-zone-monitor'))")
            current = self._load_current(connection, sgg_codes)
            diff = detect_changes(records, current)

            event_rows = [
                (
                    run_id,
                    change.zone_key,
                    change.change_type.value,
                    change.old_hash,
                    change.new_hash,
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
                        "INSERT INTO change_event "
                        "(run_id, zone_key, change_type, old_hash, new_hash, "
                        "old_snapshot, new_snapshot) VALUES "
                        "(%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)",
                        event_rows,
                    )

            upsert_sql = """
                INSERT INTO safety_zone (
                    zone_key, data_hash, source_manage_no, project_no, facility_name,
                    facility_type_code, facility_detail_type_code, representative_manage_no,
                    use_yn, sgg_code, emdong_code, stdg_code, assign_type, road_address,
                    road_detail_address, lot_address, lot_detail_address, first_registered_on,
                    geom, snapshot, last_run_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, ST_GeomFromText(%s, 5181), %s::jsonb, %s
                )
                ON CONFLICT (zone_key) DO UPDATE SET
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
                    geom = EXCLUDED.geom,
                    snapshot = EXCLUDED.snapshot,
                    last_seen_at = now(),
                    updated_at = CASE
                        WHEN safety_zone.data_hash <> EXCLUDED.data_hash THEN now()
                        ELSE safety_zone.updated_at
                    END,
                    last_run_id = EXCLUDED.last_run_id
            """
            if records:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        upsert_sql,
                        [self._record_values(record, run_id) for record in records],
                    )

            missing_keys = [
                change.zone_key
                for change in diff.changes
                if change.change_type is ChangeType.MISSING
            ]
            if missing_keys:
                connection.execute(
                    "DELETE FROM safety_zone WHERE zone_key::text = ANY(%s)",
                    (missing_keys,),
                )

            connection.execute(
                """
                UPDATE ingestion_run SET
                    status = 'SUCCESS', finished_at = now(), fetched_count = %s,
                    polygon_count = %s, skipped_non_polygon_count = %s,
                    new_count = %s, updated_count = %s, unchanged_count = %s,
                    missing_count = %s
                WHERE run_id = %s
                """,
                (
                    fetched_count,
                    len(records),
                    skipped_non_polygon_count,
                    diff.count(ChangeType.NEW),
                    diff.count(ChangeType.UPDATED),
                    diff.count(ChangeType.UNCHANGED),
                    diff.count(ChangeType.MISSING),
                    run_id,
                ),
            )
        return RunSummary(
            run_id=run_id,
            fetched_count=fetched_count,
            polygon_count=len(records),
            skipped_non_polygon_count=skipped_non_polygon_count,
            diff=diff,
        )

    def mark_notification_sent(self, run_id: uuid.UUID) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "UPDATE ingestion_run SET notification_sent_at = now() WHERE run_id = %s",
                (run_id,),
            )
