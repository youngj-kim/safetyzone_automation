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
    l.geom AS link_geom,
    CASE l.road_type
        WHEN '000' THEN '일반도로'
        WHEN '001' THEN '고가차도'
        WHEN '002' THEN '지하차도'
        WHEN '003' THEN '교량'
        WHEN '004' THEN '터널'
        ELSE '미분류'
    END AS road_type_name,
    CASE l.connect
        WHEN '1' THEN '연결로 있음'
        ELSE '연결로 없음'
    END AS connect_name,
    CASE l.multi_link
        WHEN '1' THEN '중용구간'
        ELSE '독립구간'
    END AS multi_link_name,
    CASE
        WHEN l.road_type = '000' AND COALESCE(l.connect, '0') = '0' THEN 'NORMAL_ROAD'
        WHEN l.road_type = '001' THEN 'ELEVATED_ROAD_REVIEW'
        WHEN l.road_type = '002' THEN 'UNDERPASS_REVIEW'
        WHEN l.road_type = '003' THEN 'BRIDGE_REVIEW'
        WHEN l.road_type = '004' THEN 'TUNNEL_REVIEW'
        WHEN COALESCE(l.connect, '0') = '1' THEN 'RAMP_CONNECTOR_REVIEW'
        ELSE 'STRUCTURE_REVIEW'
    END AS link_structure_category,
    (
        l.road_type IN ('001', '002', '003', '004')
        OR COALESCE(l.connect, '0') = '1'
    ) AS structure_review_flag
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
    l.geom AS link_geom,
    CASE l.road_type
        WHEN '000' THEN '일반도로'
        WHEN '001' THEN '고가차도'
        WHEN '002' THEN '지하차도'
        WHEN '003' THEN '교량'
        WHEN '004' THEN '터널'
        ELSE '미분류'
    END AS road_type_name,
    CASE l.connect
        WHEN '1' THEN '연결로 있음'
        ELSE '연결로 없음'
    END AS connect_name,
    CASE l.multi_link
        WHEN '1' THEN '중용구간'
        ELSE '독립구간'
    END AS multi_link_name,
    CASE
        WHEN l.road_type = '000' AND COALESCE(l.connect, '0') = '0' THEN 'NORMAL_ROAD'
        WHEN l.road_type = '001' THEN 'ELEVATED_ROAD_REVIEW'
        WHEN l.road_type = '002' THEN 'UNDERPASS_REVIEW'
        WHEN l.road_type = '003' THEN 'BRIDGE_REVIEW'
        WHEN l.road_type = '004' THEN 'TUNNEL_REVIEW'
        WHEN COALESCE(l.connect, '0') = '1' THEN 'RAMP_CONNECTOR_REVIEW'
        ELSE 'STRUCTURE_REVIEW'
    END AS link_structure_category,
    (
        l.road_type IN ('001', '002', '003', '004')
        OR COALESCE(l.connect, '0') = '1'
    ) AS structure_review_flag
FROM analysis.zone_link_match_excluded_v2 AS e
JOIN analysis.zone_current AS z
  ON z.zone_id = e.zone_id
JOIN mobility.std_link AS l
  ON l.link_id = e.link_id;

COMMENT ON VIEW analysis.v_zone_link_match_candidate_v2 IS
    'Second-round protection-zone to standard-link candidates with standard-link structure review fields';
COMMENT ON VIEW analysis.v_zone_link_match_excluded_v2 IS
    'Second-round excluded protection-zone to standard-link pairs with standard-link structure review fields';
