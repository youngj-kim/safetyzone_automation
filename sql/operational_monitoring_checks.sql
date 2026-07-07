-- Safety-zone monitoring operational checks.
-- Run each section independently in pgAdmin when you want one clean result grid.

-- 1) Latest run health: current row counts + latest pipeline status.
WITH latest_run AS (
    SELECT *
    FROM ops.pipeline_run
    ORDER BY started_at DESC
    LIMIT 1
)
SELECT 'polygon_count' AS item, count(*)::text AS value
FROM analysis.zone_current

UNION ALL

SELECT 'point_count' AS item, count(*)::text AS value
FROM analysis.zone_facility_point_current

UNION ALL

SELECT 'group_count' AS item, count(*)::text AS value
FROM analysis.v_zone_group_current

UNION ALL

SELECT 'latest_pipeline_status' AS item, status::text AS value
FROM latest_run

UNION ALL

SELECT 'latest_pipeline_started_at' AS item, started_at::text AS value
FROM latest_run

UNION ALL

SELECT 'latest_pipeline_finished_at' AS item, finished_at::text AS value
FROM latest_run

UNION ALL

SELECT 'latest_pipeline_sgg_codes' AS item, monitored_sgg_codes::text AS value
FROM latest_run;


-- 2) Recent pipeline history: confirms whether failures are old setup failures or current failures.
SELECT
    started_at,
    finished_at,
    status,
    monitored_sgg_codes,
    fetched_count,
    polygon_count,
    facility_point_count,
    point_only_record_count,
    new_count,
    geometry_changed_count,
    attribute_changed_count,
    geometry_attribute_changed_count,
    deleted_count,
    point_new_count,
    point_changed_count,
    point_missing_count,
    error_message
FROM ops.pipeline_run
ORDER BY started_at DESC
LIMIT 10;


-- 3) Latest successful run diff summary.
-- If you run the same scope twice with unchanged source data, the latest successful run should usually have
-- 0 polygon events and 0 point events, with most rows counted as unchanged in ops.pipeline_run.
WITH latest_success AS (
    SELECT pipeline_run_id
    FROM ops.pipeline_run
    WHERE status = 'SUCCESS'
    ORDER BY finished_at DESC
    LIMIT 1
),
polygon_events AS (
    SELECT change_type, count(*) AS event_count
    FROM analysis.zone_change_event
    WHERE run_id = (SELECT pipeline_run_id FROM latest_success)
    GROUP BY change_type
),
point_events AS (
    SELECT change_type, count(*) AS event_count
    FROM analysis.zone_facility_point_change_event
    WHERE run_id = (SELECT pipeline_run_id FROM latest_success)
    GROUP BY change_type
)
SELECT 'polygon' AS target, change_type, event_count
FROM polygon_events

UNION ALL

SELECT 'point' AS target, change_type, event_count
FROM point_events

ORDER BY target, change_type;


-- 4) Idempotency check for the latest successful run.
-- This is the main "rerun did not create fake changes" check.
WITH latest_success AS (
    SELECT *
    FROM ops.pipeline_run
    WHERE status = 'SUCCESS'
    ORDER BY finished_at DESC
    LIMIT 1
),
event_counts AS (
    SELECT
        (SELECT count(*) FROM analysis.zone_change_event
         WHERE run_id = (SELECT pipeline_run_id FROM latest_success)) AS polygon_event_count,
        (SELECT count(*) FROM analysis.zone_facility_point_change_event
         WHERE run_id = (SELECT pipeline_run_id FROM latest_success)) AS point_event_count
)
SELECT
    ls.pipeline_run_id,
    ls.finished_at,
    ls.monitored_sgg_codes,
    ls.polygon_count,
    ls.unchanged_count AS polygon_unchanged_count,
    ec.polygon_event_count,
    ls.facility_point_count,
    ls.point_unchanged_count,
    ec.point_event_count,
    CASE
        WHEN ec.polygon_event_count = 0
         AND ec.point_event_count = 0
         AND ls.polygon_count = ls.unchanged_count
         AND ls.facility_point_count = ls.point_unchanged_count
            THEN 'PASS'
        ELSE 'CHECK'
    END AS idempotency_status
FROM latest_success ls
CROSS JOIN event_counts ec;


-- 5) Geometry and group linkage quality check.
SELECT 'invalid_polygons' AS check_name, count(*)::text AS value
FROM analysis.zone_current
WHERE ST_IsEmpty(geom) OR NOT ST_IsValid(geom) OR ST_SRID(geom) <> 5179

UNION ALL

SELECT 'invalid_points' AS check_name, count(*)::text AS value
FROM analysis.zone_facility_point_current
WHERE ST_IsEmpty(geom) OR NOT ST_IsValid(geom) OR ST_SRID(geom) <> 5179

UNION ALL

SELECT 'point_groups_without_polygon' AS check_name, count(*)::text AS value
FROM analysis.v_zone_group_current
WHERE polygon_record_count = 0 AND facility_count > 0

UNION ALL

SELECT 'distinct_sgg_codes' AS check_name, count(*)::text AS value
FROM (
    SELECT sgg_code FROM analysis.zone_current
    UNION
    SELECT sgg_code FROM analysis.zone_facility_point_current
) s;
