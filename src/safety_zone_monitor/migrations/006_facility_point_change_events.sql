ALTER TABLE ops.pipeline_run
    ADD COLUMN IF NOT EXISTS point_new_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS point_changed_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS point_unchanged_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS point_deleted_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS point_missing_count integer NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS analysis.zone_facility_point_change_event (
    event_id bigserial PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES raw.police_zone_api_run(run_id),
    facility_id char(64) NOT NULL,
    point_ordinal integer NOT NULL CHECK (point_ordinal > 0),
    zone_group_id text NOT NULL,
    change_type text NOT NULL CHECK (
        change_type IN (
            'NEW',
            'POINT_CHANGED',
            'ATTRIBUTE_CHANGED',
            'POINT_ATTRIBUTE_CHANGED',
            'DELETED',
            'MISSING'
        )
    ),
    old_attr_hash char(64),
    new_attr_hash char(64),
    old_point_hash char(64),
    new_point_hash char(64),
    old_data_hash char(64),
    new_data_hash char(64),
    old_snapshot jsonb,
    new_snapshot jsonb,
    detected_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, facility_id, point_ordinal, change_type)
);

CREATE INDEX IF NOT EXISTS zone_facility_point_event_detected_idx
    ON analysis.zone_facility_point_change_event (detected_at DESC);
CREATE INDEX IF NOT EXISTS zone_facility_point_event_facility_idx
    ON analysis.zone_facility_point_change_event (facility_id, point_ordinal);
CREATE INDEX IF NOT EXISTS zone_facility_point_event_group_idx
    ON analysis.zone_facility_point_change_event (zone_group_id);

COMMENT ON TABLE analysis.zone_facility_point_change_event IS
    'Detected changes for separately stored facility points; unchanged rows are counted only';
