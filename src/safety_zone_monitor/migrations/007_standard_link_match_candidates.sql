CREATE TABLE IF NOT EXISTS analysis.zone_link_match_candidate (
    match_id bigserial PRIMARY KEY,
    zone_id char(64) NOT NULL REFERENCES analysis.zone_current(zone_id) ON DELETE CASCADE,
    zone_group_id text NOT NULL,
    source_manage_no text,
    facility_name text,
    sgg_code varchar(5) NOT NULL,
    link_id text NOT NULL,
    candidate_grade text NOT NULL CHECK (candidate_grade IN ('A', 'B', 'C', 'D')),
    review_status text NOT NULL CHECK (
        review_status IN ('AUTO_CANDIDATE', 'NEEDS_REVIEW', 'ACCEPTED', 'REJECTED')
    ),
    distance_m double precision NOT NULL,
    intersection_length_m double precision NOT NULL,
    link_length_m double precision NOT NULL,
    intersection_ratio double precision NOT NULL,
    match_reason text NOT NULL,
    created_run_id uuid REFERENCES ops.pipeline_run(pipeline_run_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (zone_id, link_id)
);

CREATE INDEX IF NOT EXISTS zone_link_match_candidate_zone_idx
    ON analysis.zone_link_match_candidate (zone_id);
CREATE INDEX IF NOT EXISTS zone_link_match_candidate_group_idx
    ON analysis.zone_link_match_candidate (zone_group_id);
CREATE INDEX IF NOT EXISTS zone_link_match_candidate_link_idx
    ON analysis.zone_link_match_candidate (link_id);
CREATE INDEX IF NOT EXISTS zone_link_match_candidate_grade_idx
    ON analysis.zone_link_match_candidate (candidate_grade, review_status);
CREATE INDEX IF NOT EXISTS zone_link_match_candidate_sgg_idx
    ON analysis.zone_link_match_candidate (sgg_code);

CREATE OR REPLACE VIEW analysis.v_zone_link_match_candidate AS
SELECT
    c.match_id,
    c.zone_id,
    c.zone_group_id,
    c.source_manage_no,
    c.facility_name,
    c.sgg_code,
    c.link_id,
    l.road_name,
    l.road_rank,
    l.road_type,
    c.candidate_grade,
    c.review_status,
    c.distance_m,
    c.intersection_length_m,
    c.link_length_m,
    c.intersection_ratio,
    c.match_reason,
    c.created_run_id,
    c.created_at,
    c.updated_at,
    z.geom AS zone_geom,
    l.geom AS link_geom
FROM analysis.zone_link_match_candidate AS c
JOIN analysis.zone_current AS z
  ON z.zone_id = c.zone_id
JOIN mobility.std_link AS l
  ON l.link_id = c.link_id;

COMMENT ON TABLE analysis.zone_link_match_candidate IS
    'Candidate table for protection-zone to standard-link spatial matching; does not update mobility.std_link';
COMMENT ON VIEW analysis.v_zone_link_match_candidate IS
    'QGIS review view joining zone-link candidates with protection-zone and standard-link geometry';
