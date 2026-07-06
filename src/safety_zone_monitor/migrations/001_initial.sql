-- Additive-only objects for the existing mobility_db.
-- Never drop or alter raw.raw_std_*, mobility.std_*, or existing views here.
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS analysis;
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.pipeline_run (
    pipeline_run_id uuid PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    monitored_sgg_codes text[] NOT NULL,
    fetched_count integer NOT NULL DEFAULT 0,
    polygon_count integer NOT NULL DEFAULT 0,
    skipped_non_polygon_count integer NOT NULL DEFAULT 0,
    new_count integer NOT NULL DEFAULT 0,
    geometry_changed_count integer NOT NULL DEFAULT 0,
    attribute_changed_count integer NOT NULL DEFAULT 0,
    geometry_attribute_changed_count integer NOT NULL DEFAULT 0,
    unchanged_count integer NOT NULL DEFAULT 0,
    deleted_count integer NOT NULL DEFAULT 0,
    error_message text,
    notification_sent_at timestamptz
);

CREATE TABLE IF NOT EXISTS raw.police_zone_api_run (
    run_id uuid PRIMARY KEY REFERENCES ops.pipeline_run(pipeline_run_id),
    requested_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    status text NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    source_endpoint text NOT NULL,
    monitored_sgg_codes text[] NOT NULL,
    response_count integer NOT NULL DEFAULT 0,
    error_count integer NOT NULL DEFAULT 0,
    error_message text
);

CREATE TABLE IF NOT EXISTS raw.police_zone_item_snapshot (
    run_id uuid NOT NULL REFERENCES raw.police_zone_api_run(run_id),
    item_ordinal integer NOT NULL,
    source_manage_no text,
    sgg_code varchar(5),
    raw_json jsonb NOT NULL,
    raw_wkt text,
    payload_hash char(64) NOT NULL,
    captured_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, item_ordinal)
);

CREATE INDEX IF NOT EXISTS police_zone_item_snapshot_manage_no_idx
    ON raw.police_zone_item_snapshot (source_manage_no);
CREATE INDEX IF NOT EXISTS police_zone_item_snapshot_sgg_code_idx
    ON raw.police_zone_item_snapshot (sgg_code);

CREATE TABLE IF NOT EXISTS analysis.zone_snapshot (
    run_id uuid NOT NULL REFERENCES raw.police_zone_api_run(run_id),
    zone_id char(64) NOT NULL,
    attr_hash char(64) NOT NULL,
    geom_hash char(64) NOT NULL,
    data_hash char(64) NOT NULL,
    attrs jsonb NOT NULL,
    geom geometry(MultiPolygon, 5179) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, zone_id)
);

CREATE INDEX IF NOT EXISTS zone_snapshot_geom_gix
    ON analysis.zone_snapshot USING gist (geom);
CREATE INDEX IF NOT EXISTS zone_snapshot_zone_id_idx
    ON analysis.zone_snapshot (zone_id);

CREATE TABLE IF NOT EXISTS analysis.zone_current (
    zone_id char(64) PRIMARY KEY,
    attr_hash char(64) NOT NULL,
    geom_hash char(64) NOT NULL,
    data_hash char(64) NOT NULL,
    source_manage_no text,
    project_no text,
    facility_name text,
    facility_type_code text,
    facility_detail_type_code text,
    representative_manage_no text,
    use_yn text,
    sgg_code varchar(5) NOT NULL,
    emdong_code text,
    stdg_code text,
    assign_type text,
    road_address text,
    road_detail_address text,
    lot_address text,
    lot_detail_address text,
    first_registered_on date,
    last_modified_on date,
    geom geometry(MultiPolygon, 5179) NOT NULL,
    attrs jsonb NOT NULL,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_run_id uuid NOT NULL REFERENCES raw.police_zone_api_run(run_id)
);

CREATE INDEX IF NOT EXISTS zone_current_geom_gix
    ON analysis.zone_current USING gist (geom);
CREATE INDEX IF NOT EXISTS zone_current_sgg_code_idx
    ON analysis.zone_current (sgg_code);
CREATE INDEX IF NOT EXISTS zone_current_source_manage_no_idx
    ON analysis.zone_current (source_manage_no);

CREATE TABLE IF NOT EXISTS analysis.zone_change_event (
    event_id bigserial PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES raw.police_zone_api_run(run_id),
    zone_id char(64) NOT NULL,
    change_type text NOT NULL CHECK (
        change_type IN (
            'NEW',
            'GEOMETRY_CHANGED',
            'ATTRIBUTE_CHANGED',
            'GEOMETRY_ATTRIBUTE_CHANGED',
            'DELETED'
        )
    ),
    old_attr_hash char(64),
    new_attr_hash char(64),
    old_geom_hash char(64),
    new_geom_hash char(64),
    old_data_hash char(64),
    new_data_hash char(64),
    old_snapshot jsonb,
    new_snapshot jsonb,
    detected_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, zone_id, change_type)
);

CREATE INDEX IF NOT EXISTS zone_change_event_detected_at_idx
    ON analysis.zone_change_event (detected_at DESC);
CREATE INDEX IF NOT EXISTS zone_change_event_zone_id_idx
    ON analysis.zone_change_event (zone_id);

CREATE TABLE IF NOT EXISTS ops.notification_log (
    notification_id bigserial PRIMARY KEY,
    pipeline_run_id uuid NOT NULL REFERENCES ops.pipeline_run(pipeline_run_id),
    channel text NOT NULL,
    status text NOT NULL CHECK (status IN ('SENT', 'FAILED')),
    sent_at timestamptz NOT NULL DEFAULT now(),
    payload_summary jsonb,
    error_message text
);

