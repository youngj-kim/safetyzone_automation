-- Read-only QC for the protection-zone monitoring objects.
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema IN ('raw', 'analysis', 'ops')
  AND (
      table_name LIKE 'police_zone%'
      OR table_name LIKE 'zone_%'
      OR table_name IN ('pipeline_run', 'notification_log')
  )
ORDER BY table_schema, table_name;

SELECT f_table_schema, f_table_name, f_geometry_column, type, srid
FROM public.geometry_columns
WHERE f_table_schema = 'analysis'
  AND f_table_name IN ('zone_snapshot', 'zone_current')
ORDER BY f_table_name;

SELECT 'raw.police_zone_api_run' AS object_name, COUNT(*) AS row_count
FROM raw.police_zone_api_run
UNION ALL
SELECT 'raw.police_zone_item_snapshot', COUNT(*)
FROM raw.police_zone_item_snapshot
UNION ALL
SELECT 'analysis.zone_snapshot', COUNT(*)
FROM analysis.zone_snapshot
UNION ALL
SELECT 'analysis.zone_current', COUNT(*)
FROM analysis.zone_current
UNION ALL
SELECT 'analysis.zone_change_event', COUNT(*)
FROM analysis.zone_change_event
UNION ALL
SELECT 'ops.pipeline_run', COUNT(*)
FROM ops.pipeline_run;
