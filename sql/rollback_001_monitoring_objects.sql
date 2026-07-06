-- MANUAL ROLLBACK ONLY.
-- This removes only protection-zone monitoring objects created by this repository.
-- It never drops raw/mobility schemas, standard-node-link objects, or Docker volumes.
BEGIN;

DROP TABLE IF EXISTS ops.notification_log;
DROP TABLE IF EXISTS analysis.zone_change_event;
DROP TABLE IF EXISTS analysis.zone_current;
DROP TABLE IF EXISTS analysis.zone_snapshot;
DROP TABLE IF EXISTS raw.police_zone_item_snapshot;
DROP TABLE IF EXISTS raw.police_zone_api_run;
DROP TABLE IF EXISTS ops.pipeline_run;

COMMIT;
