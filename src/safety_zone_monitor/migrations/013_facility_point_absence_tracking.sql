CREATE TABLE IF NOT EXISTS analysis.zone_facility_point_absence (
    facility_id char(64) NOT NULL,
    point_ordinal integer NOT NULL CHECK (point_ordinal > 0),
    zone_group_id text NOT NULL,
    source_manage_no text,
    facility_name text,
    sgg_code text NOT NULL,
    first_missing_run_id uuid NOT NULL REFERENCES raw.police_zone_api_run(run_id),
    first_missing_at timestamptz NOT NULL DEFAULT now(),
    last_missing_run_id uuid NOT NULL REFERENCES raw.police_zone_api_run(run_id),
    last_missing_at timestamptz NOT NULL DEFAULT now(),
    missing_streak integer NOT NULL DEFAULT 1 CHECK (missing_streak > 0),
    last_change_type text NOT NULL CHECK (last_change_type IN ('DELETED', 'MISSING')),
    old_snapshot jsonb,
    PRIMARY KEY (facility_id, point_ordinal)
);

CREATE INDEX IF NOT EXISTS zone_facility_point_absence_sgg_idx
    ON analysis.zone_facility_point_absence (sgg_code);
CREATE INDEX IF NOT EXISTS zone_facility_point_absence_manage_no_idx
    ON analysis.zone_facility_point_absence (source_manage_no);
CREATE INDEX IF NOT EXISTS zone_facility_point_absence_last_missing_idx
    ON analysis.zone_facility_point_absence (last_missing_at DESC);

COMMENT ON TABLE analysis.zone_facility_point_absence IS
    'Open absence state for facility points that disappeared from the source API';

INSERT INTO analysis.zone_facility_point_absence (
    facility_id,
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
    last_change_type,
    old_snapshot
)
SELECT
    latest.facility_id,
    latest.point_ordinal,
    latest.zone_group_id,
    latest.old_snapshot ->> 'source_manage_no',
    latest.old_snapshot ->> 'facility_name',
    COALESCE(latest.old_snapshot ->> 'sgg_code', latest.new_snapshot ->> 'sgg_code'),
    latest.run_id,
    latest.detected_at,
    latest.run_id,
    latest.detected_at,
    1,
    latest.change_type,
    latest.old_snapshot
FROM (
    SELECT DISTINCT ON (event.facility_id, event.point_ordinal)
        event.*
    FROM analysis.zone_facility_point_change_event AS event
    ORDER BY event.facility_id, event.point_ordinal, event.detected_at DESC, event.event_id DESC
) AS latest
WHERE latest.change_type IN ('DELETED', 'MISSING')
  AND NOT EXISTS (
      SELECT 1
      FROM analysis.zone_facility_point_current AS current_point
      WHERE current_point.facility_id = latest.facility_id
        AND current_point.point_ordinal = latest.point_ordinal
  )
ON CONFLICT (facility_id, point_ordinal) DO NOTHING;
