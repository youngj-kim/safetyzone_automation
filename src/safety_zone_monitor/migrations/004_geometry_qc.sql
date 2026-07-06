ALTER TABLE analysis.zone_snapshot
    ADD COLUMN IF NOT EXISTS geometry_qc jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE analysis.zone_current
    ADD COLUMN IF NOT EXISTS geometry_qc jsonb NOT NULL DEFAULT '{}'::jsonb;
