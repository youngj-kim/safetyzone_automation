-- Standard link matching round-1 review helper queries.
-- Run these in pgAdmin or QGIS DB Manager.

-- 1. Current candidate distribution.
select
    candidate_grade,
    review_status,
    count(*) as candidate_count,
    round(avg(distance_m)::numeric, 2) as avg_distance_m,
    round(avg(intersection_length_m)::numeric, 2) as avg_intersection_length_m,
    round(avg(intersection_ratio)::numeric, 3) as avg_intersection_ratio
from analysis.zone_link_match_candidate
group by candidate_grade, review_status
order by candidate_grade, review_status;

-- 2. Direct-intersection candidates most likely to be grazing/touching cases.
select
    zone_id,
    zone_group_id,
    facility_name,
    sgg_code,
    link_id,
    candidate_grade,
    distance_m,
    intersection_length_m,
    link_length_m,
    intersection_ratio,
    match_reason
from analysis.zone_link_match_candidate
where candidate_grade in ('A', 'B')
order by intersection_ratio asc nulls last, intersection_length_m asc nulls last
limit 200;

-- 3. Zones with no current standard-link candidate.
select
    z.zone_id,
    z.zone_group_id,
    z.source_manage_no,
    z.facility_name,
    z.sgg_code,
    count(c.match_id) as candidate_count
from analysis.zone_current z
left join analysis.zone_link_match_candidate c
    on c.zone_id = z.zone_id
group by
    z.zone_id,
    z.zone_group_id,
    z.source_manage_no,
    z.facility_name,
    z.sgg_code
having count(c.match_id) = 0
order by z.sgg_code, z.facility_name, z.zone_id;

-- 4. C/D candidates to review first: near but not intersecting.
select
    zone_id,
    zone_group_id,
    facility_name,
    sgg_code,
    link_id,
    candidate_grade,
    distance_m,
    road_name,
    match_reason
from analysis.v_zone_link_match_candidate
where candidate_grade in ('C', 'D')
order by candidate_grade, distance_m asc
limit 300;

