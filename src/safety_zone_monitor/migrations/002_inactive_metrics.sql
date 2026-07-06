ALTER TABLE ops.pipeline_run
    ADD COLUMN IF NOT EXISTS skipped_inactive_count integer NOT NULL DEFAULT 0;
