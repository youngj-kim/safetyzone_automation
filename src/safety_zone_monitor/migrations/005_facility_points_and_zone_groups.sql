-- Preserve point facilities and connect them to their representative protection-zone group.
ALTER TABLE ops.pipeline_run
    ADD COLUMN IF NOT EXISTS facility_point_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS point_only_record_count integer NOT NULL DEFAULT 0;

ALTER TABLE analysis.zone_snapshot
    ADD COLUMN IF NOT EXISTS zone_group_id text;

ALTER TABLE analysis.zone_current
    ADD COLUMN IF NOT EXISTS zone_group_id text;

UPDATE analysis.zone_snapshot
SET zone_group_id = COALESCE(
    NULLIF(attrs ->> 'representative_manage_no', ''),
    NULLIF(attrs ->> 'source_manage_no', ''),
    zone_id::text
)
WHERE zone_group_id IS NULL;

UPDATE analysis.zone_current
SET zone_group_id = COALESCE(
    NULLIF(representative_manage_no, ''),
    NULLIF(source_manage_no, ''),
    zone_id::text
)
WHERE zone_group_id IS NULL;

ALTER TABLE analysis.zone_snapshot
    ALTER COLUMN zone_group_id SET NOT NULL;
ALTER TABLE analysis.zone_current
    ALTER COLUMN zone_group_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS zone_snapshot_group_id_idx
    ON analysis.zone_snapshot (zone_group_id);
CREATE INDEX IF NOT EXISTS zone_current_group_id_idx
    ON analysis.zone_current (zone_group_id);

CREATE TABLE IF NOT EXISTS analysis.zone_facility_point_snapshot (
    run_id uuid NOT NULL REFERENCES raw.police_zone_api_run(run_id),
    facility_id char(64) NOT NULL,
    point_ordinal integer NOT NULL CHECK (point_ordinal > 0),
    zone_group_id text NOT NULL,
    attr_hash char(64) NOT NULL,
    point_hash char(64) NOT NULL,
    data_hash char(64) NOT NULL,
    source_manage_no text,
    facility_name text,
    sgg_code varchar(5) NOT NULL,
    use_yn text,
    geom geometry(Point, 5179) NOT NULL,
    attrs jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, facility_id, point_ordinal)
);

CREATE INDEX IF NOT EXISTS zone_facility_point_snapshot_geom_gix
    ON analysis.zone_facility_point_snapshot USING gist (geom);
CREATE INDEX IF NOT EXISTS zone_facility_point_snapshot_group_idx
    ON analysis.zone_facility_point_snapshot (zone_group_id);

CREATE TABLE IF NOT EXISTS analysis.zone_facility_point_current (
    facility_id char(64) NOT NULL,
    point_ordinal integer NOT NULL CHECK (point_ordinal > 0),
    zone_group_id text NOT NULL,
    attr_hash char(64) NOT NULL,
    point_hash char(64) NOT NULL,
    data_hash char(64) NOT NULL,
    source_manage_no text,
    facility_name text,
    sgg_code varchar(5) NOT NULL,
    use_yn text,
    geom geometry(Point, 5179) NOT NULL,
    attrs jsonb NOT NULL,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_run_id uuid NOT NULL REFERENCES raw.police_zone_api_run(run_id),
    PRIMARY KEY (facility_id, point_ordinal)
);

CREATE INDEX IF NOT EXISTS zone_facility_point_current_geom_gix
    ON analysis.zone_facility_point_current USING gist (geom);
CREATE INDEX IF NOT EXISTS zone_facility_point_current_group_idx
    ON analysis.zone_facility_point_current (zone_group_id);
CREATE INDEX IF NOT EXISTS zone_facility_point_current_sgg_idx
    ON analysis.zone_facility_point_current (sgg_code);
CREATE INDEX IF NOT EXISTS zone_facility_point_current_manage_no_idx
    ON analysis.zone_facility_point_current (source_manage_no);

CREATE OR REPLACE VIEW analysis.v_zone_group_current AS
WITH polygon_groups AS (
    SELECT
        zone_group_id,
        COUNT(*)::integer AS polygon_record_count,
        ARRAY_AGG(zone_id::text ORDER BY zone_id::text) AS zone_ids,
        ARRAY_AGG(source_manage_no ORDER BY source_manage_no)
            FILTER (WHERE source_manage_no IS NOT NULL) AS polygon_manage_nos,
        COALESCE(
            MAX(facility_name) FILTER (WHERE source_manage_no = zone_group_id),
            MIN(facility_name)
        ) AS representative_name,
        ARRAY_AGG(DISTINCT sgg_code ORDER BY sgg_code) AS sgg_codes,
        ST_Multi(
            ST_CollectionExtract(
                ST_MakeValid(ST_UnaryUnion(ST_Collect(geom))),
                3
            )
        )::geometry(MultiPolygon, 5179) AS geom
    FROM analysis.zone_current
    GROUP BY zone_group_id
),
point_groups AS (
    SELECT
        zone_group_id,
        COUNT(*)::integer AS point_count,
        COUNT(DISTINCT facility_id)::integer AS facility_count,
        ARRAY_AGG(DISTINCT facility_id::text ORDER BY facility_id::text) AS facility_ids,
        ARRAY_AGG(DISTINCT source_manage_no ORDER BY source_manage_no)
            FILTER (WHERE source_manage_no IS NOT NULL) AS facility_manage_nos,
        ARRAY_AGG(DISTINCT facility_name ORDER BY facility_name)
            FILTER (WHERE facility_name IS NOT NULL) AS facility_names,
        ARRAY_AGG(DISTINCT sgg_code ORDER BY sgg_code) AS sgg_codes,
        ST_Multi(ST_Collect(geom))::geometry(MultiPoint, 5179) AS facility_points
    FROM analysis.zone_facility_point_current
    GROUP BY zone_group_id
)
SELECT
    COALESCE(z.zone_group_id, p.zone_group_id) AS zone_group_id,
    z.representative_name,
    COALESCE(z.polygon_record_count, 0) AS polygon_record_count,
    COALESCE(p.facility_count, 0) AS facility_count,
    COALESCE(p.point_count, 0) AS point_count,
    z.zone_ids,
    z.polygon_manage_nos,
    p.facility_ids,
    p.facility_manage_nos,
    p.facility_names,
    COALESCE(z.sgg_codes, p.sgg_codes) AS sgg_codes,
    z.geom,
    p.facility_points
FROM polygon_groups AS z
FULL OUTER JOIN point_groups AS p USING (zone_group_id);

COMMENT ON VIEW analysis.v_zone_group_current IS
    'Representative management number based integrated view of polygons and facility points';
