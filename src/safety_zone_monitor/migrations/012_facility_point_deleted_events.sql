ALTER TABLE ops.pipeline_run
    ADD COLUMN IF NOT EXISTS point_deleted_count integer NOT NULL DEFAULT 0;

DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'analysis.zone_facility_point_change_event'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%change_type%'
    LIMIT 1;

    IF constraint_name IS NOT NULL THEN
        EXECUTE format(
            'ALTER TABLE analysis.zone_facility_point_change_event DROP CONSTRAINT %I',
            constraint_name
        );
    END IF;
END $$;

ALTER TABLE analysis.zone_facility_point_change_event
    ADD CONSTRAINT zone_facility_point_change_event_change_type_check
    CHECK (
        change_type IN (
            'NEW',
            'POINT_CHANGED',
            'ATTRIBUTE_CHANGED',
            'POINT_ATTRIBUTE_CHANGED',
            'DELETED',
            'MISSING'
        )
    );
