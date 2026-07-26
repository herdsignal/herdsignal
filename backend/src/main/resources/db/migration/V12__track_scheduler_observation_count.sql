ALTER TABLE scheduler_runs
    ADD COLUMN observation_count INT NULL
    AFTER publish_status;
