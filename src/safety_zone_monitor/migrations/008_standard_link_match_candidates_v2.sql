CREATE TABLE IF NOT EXISTS analysis.zone_link_match_candidate_v2 (
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
    match_rule_code text NOT NULL,
    match_rule_description text NOT NULL,
    is_touch_or_graze boolean NOT NULL,
    link_midpoint_inside_zone boolean NOT NULL,
    same_road_as_seed boolean NOT NULL,
    connected_to_seed boolean NOT NULL,
    seed_link_id text,
    created_run_id uuid REFERENCES ops.pipeline_run(pipeline_run_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (zone_id, link_id)
);

CREATE TABLE IF NOT EXISTS analysis.zone_link_match_excluded_v2 (
    excluded_id bigserial PRIMARY KEY,
    zone_id char(64) NOT NULL REFERENCES analysis.zone_current(zone_id) ON DELETE CASCADE,
    zone_group_id text NOT NULL,
    source_manage_no text,
    facility_name text,
    sgg_code varchar(5) NOT NULL,
    link_id text NOT NULL,
    distance_m double precision NOT NULL,
    intersection_length_m double precision NOT NULL,
    link_length_m double precision NOT NULL,
    intersection_ratio double precision NOT NULL,
    exclusion_code text NOT NULL,
    exclusion_reason text NOT NULL,
    is_touch_or_graze boolean NOT NULL,
    link_midpoint_inside_zone boolean NOT NULL,
    created_run_id uuid REFERENCES ops.pipeline_run(pipeline_run_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (zone_id, link_id)
);

CREATE INDEX IF NOT EXISTS zone_link_match_candidate_v2_zone_idx
    ON analysis.zone_link_match_candidate_v2 (zone_id);
CREATE INDEX IF NOT EXISTS zone_link_match_candidate_v2_group_idx
    ON analysis.zone_link_match_candidate_v2 (zone_group_id);
CREATE INDEX IF NOT EXISTS zone_link_match_candidate_v2_link_idx
    ON analysis.zone_link_match_candidate_v2 (link_id);
CREATE INDEX IF NOT EXISTS zone_link_match_candidate_v2_grade_idx
    ON analysis.zone_link_match_candidate_v2 (candidate_grade, review_status);
CREATE INDEX IF NOT EXISTS zone_link_match_candidate_v2_sgg_idx
    ON analysis.zone_link_match_candidate_v2 (sgg_code);
CREATE INDEX IF NOT EXISTS zone_link_match_candidate_v2_rule_idx
    ON analysis.zone_link_match_candidate_v2 (match_rule_code);

CREATE INDEX IF NOT EXISTS zone_link_match_excluded_v2_zone_idx
    ON analysis.zone_link_match_excluded_v2 (zone_id);
CREATE INDEX IF NOT EXISTS zone_link_match_excluded_v2_group_idx
    ON analysis.zone_link_match_excluded_v2 (zone_group_id);
CREATE INDEX IF NOT EXISTS zone_link_match_excluded_v2_link_idx
    ON analysis.zone_link_match_excluded_v2 (link_id);
CREATE INDEX IF NOT EXISTS zone_link_match_excluded_v2_code_idx
    ON analysis.zone_link_match_excluded_v2 (exclusion_code);
CREATE INDEX IF NOT EXISTS zone_link_match_excluded_v2_sgg_idx
    ON analysis.zone_link_match_excluded_v2 (sgg_code);

CREATE OR REPLACE VIEW analysis.v_zone_link_match_candidate_v2 AS
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
    l.road_no,
    l.f_node_id,
    l.t_node_id,
    c.candidate_grade,
    c.review_status,
    c.distance_m,
    c.intersection_length_m,
    c.link_length_m,
    c.intersection_ratio,
    c.match_rule_code,
    c.match_rule_description,
    c.is_touch_or_graze,
    c.link_midpoint_inside_zone,
    c.same_road_as_seed,
    c.connected_to_seed,
    c.seed_link_id,
    c.created_run_id,
    c.created_at,
    c.updated_at,
    z.geom AS zone_geom,
    l.geom AS link_geom
FROM analysis.zone_link_match_candidate_v2 AS c
JOIN analysis.zone_current AS z
  ON z.zone_id = c.zone_id
JOIN mobility.std_link AS l
  ON l.link_id = c.link_id;

CREATE OR REPLACE VIEW analysis.v_zone_link_match_excluded_v2 AS
SELECT
    e.excluded_id,
    e.zone_id,
    e.zone_group_id,
    e.source_manage_no,
    e.facility_name,
    e.sgg_code,
    e.link_id,
    l.road_name,
    l.road_rank,
    l.road_type,
    l.road_no,
    l.f_node_id,
    l.t_node_id,
    e.distance_m,
    e.intersection_length_m,
    e.link_length_m,
    e.intersection_ratio,
    e.exclusion_code,
    e.exclusion_reason,
    e.is_touch_or_graze,
    e.link_midpoint_inside_zone,
    e.created_run_id,
    e.created_at,
    e.updated_at,
    z.geom AS zone_geom,
    l.geom AS link_geom
FROM analysis.zone_link_match_excluded_v2 AS e
JOIN analysis.zone_current AS z
  ON z.zone_id = e.zone_id
JOIN mobility.std_link AS l
  ON l.link_id = e.link_id;

CREATE OR REPLACE VIEW analysis.v_zone_link_match_coverage_v2 AS
SELECT
    z.zone_id,
    z.zone_group_id,
    z.source_manage_no,
    z.facility_name,
    z.sgg_code,
    COUNT(c.match_id)::integer AS candidate_count,
    COUNT(c.match_id) FILTER (WHERE c.candidate_grade = 'A')::integer AS grade_a_count,
    COUNT(c.match_id) FILTER (WHERE c.candidate_grade = 'B')::integer AS grade_b_count,
    COUNT(c.match_id) FILTER (WHERE c.candidate_grade = 'C')::integer AS grade_c_count,
    COUNT(c.match_id) FILTER (WHERE c.candidate_grade = 'D')::integer AS grade_d_count,
    COUNT(e.excluded_id)::integer AS excluded_count,
    COALESCE(MIN(c.distance_m), MIN(e.distance_m)) AS nearest_reviewed_link_distance_m,
    CASE
        WHEN COUNT(c.match_id) FILTER (WHERE c.candidate_grade = 'A') > 0
            THEN 'MATCHED_A'
        WHEN COUNT(c.match_id) > 0
            THEN 'MATCHED_REVIEW'
        WHEN COUNT(e.excluded_id) > 0
            THEN 'NO_ACCEPTED_CANDIDATE'
        ELSE 'NO_CANDIDATE_WITHIN_20M'
    END AS coverage_status,
    z.geom AS zone_geom
FROM analysis.zone_current AS z
LEFT JOIN analysis.zone_link_match_candidate_v2 AS c
  ON c.zone_id = z.zone_id
LEFT JOIN analysis.zone_link_match_excluded_v2 AS e
  ON e.zone_id = z.zone_id
GROUP BY
    z.zone_id,
    z.zone_group_id,
    z.source_manage_no,
    z.facility_name,
    z.sgg_code,
    z.geom;

COMMENT ON TABLE analysis.zone_link_match_candidate_v2 IS
    'Second-round protection-zone to standard-link candidates with stricter overlap and seed-connectivity rules';
COMMENT ON TABLE analysis.zone_link_match_excluded_v2 IS
    'Second-round rejected nearby standard-link records with explicit exclusion reasons';
COMMENT ON VIEW analysis.v_zone_link_match_candidate_v2 IS
    'QGIS review view for second-round accepted A/B/C/D standard-link candidates';
COMMENT ON VIEW analysis.v_zone_link_match_excluded_v2 IS
    'QGIS review view for second-round rejected/touch/graze standard-link candidates';
COMMENT ON VIEW analysis.v_zone_link_match_coverage_v2 IS
    'Protection-zone level second-round matching coverage summary';
