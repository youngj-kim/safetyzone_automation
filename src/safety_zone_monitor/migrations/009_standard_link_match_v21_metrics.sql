DROP VIEW IF EXISTS analysis.v_zone_link_match_coverage_review_v23;
DROP VIEW IF EXISTS analysis.v_zone_link_match_excluded_review_v23;
DROP VIEW IF EXISTS analysis.v_zone_link_match_candidate_review_v23;

ALTER TABLE analysis.zone_link_match_candidate_v2
    ADD COLUMN IF NOT EXISTS proximity_overlap_length_m double precision NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS proximity_overlap_ratio double precision NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS potential_grade_separated boolean NOT NULL DEFAULT false;

ALTER TABLE analysis.zone_link_match_excluded_v2
    ADD COLUMN IF NOT EXISTS proximity_overlap_length_m double precision NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS proximity_overlap_ratio double precision NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS potential_grade_separated boolean NOT NULL DEFAULT false;

DROP VIEW IF EXISTS analysis.v_zone_link_match_candidate_v2;
DROP VIEW IF EXISTS analysis.v_zone_link_match_excluded_v2;

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
    l.connect,
    l.multi_link,
    l.f_node_id,
    l.t_node_id,
    c.candidate_grade,
    c.review_status,
    c.distance_m,
    c.intersection_length_m,
    c.link_length_m,
    c.intersection_ratio,
    c.proximity_overlap_length_m,
    c.proximity_overlap_ratio,
    c.match_rule_code,
    c.match_rule_description,
    c.is_touch_or_graze,
    c.potential_grade_separated,
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
    l.connect,
    l.multi_link,
    l.f_node_id,
    l.t_node_id,
    e.distance_m,
    e.intersection_length_m,
    e.link_length_m,
    e.intersection_ratio,
    e.proximity_overlap_length_m,
    e.proximity_overlap_ratio,
    e.exclusion_code,
    e.exclusion_reason,
    e.is_touch_or_graze,
    e.potential_grade_separated,
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

COMMENT ON COLUMN analysis.zone_link_match_candidate_v2.proximity_overlap_length_m IS
    'Length of the standard link inside the near-distance buffer around the protection-zone polygon';
COMMENT ON COLUMN analysis.zone_link_match_candidate_v2.proximity_overlap_ratio IS
    'Share of the standard link inside the near-distance buffer around the protection-zone polygon';
COMMENT ON COLUMN analysis.zone_link_match_candidate_v2.potential_grade_separated IS
    'Review flag for high-rank links that may be grade-separated upper roads in 2D spatial matching';
