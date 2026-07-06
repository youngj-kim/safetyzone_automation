CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS ingestion_run (
    run_id uuid PRIMARY KEY,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    monitored_sgg_codes text[] NOT NULL,
    fetched_count integer NOT NULL DEFAULT 0,
    polygon_count integer NOT NULL DEFAULT 0,
    skipped_non_polygon_count integer NOT NULL DEFAULT 0,
    new_count integer NOT NULL DEFAULT 0,
    updated_count integer NOT NULL DEFAULT 0,
    unchanged_count integer NOT NULL DEFAULT 0,
    missing_count integer NOT NULL DEFAULT 0,
    error_message text,
    notification_sent_at timestamptz
);

CREATE TABLE IF NOT EXISTS safety_zone (
    zone_key char(64) PRIMARY KEY,
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
    geom geometry(MultiPolygon, 5181) NOT NULL,
    snapshot jsonb NOT NULL,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_run_id uuid NOT NULL REFERENCES ingestion_run(run_id)
);

CREATE INDEX IF NOT EXISTS safety_zone_geom_gix ON safety_zone USING gist (geom);
CREATE INDEX IF NOT EXISTS safety_zone_sgg_code_idx ON safety_zone (sgg_code);
CREATE INDEX IF NOT EXISTS safety_zone_source_manage_no_idx ON safety_zone (source_manage_no);

CREATE TABLE IF NOT EXISTS change_event (
    event_id bigserial PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES ingestion_run(run_id),
    zone_key char(64) NOT NULL,
    change_type text NOT NULL CHECK (change_type IN ('NEW', 'UPDATED', 'MISSING')),
    old_hash char(64),
    new_hash char(64),
    old_snapshot jsonb,
    new_snapshot jsonb,
    detected_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, zone_key, change_type)
);

CREATE INDEX IF NOT EXISTS change_event_detected_at_idx ON change_event (detected_at DESC);
CREATE INDEX IF NOT EXISTS change_event_zone_key_idx ON change_event (zone_key);

