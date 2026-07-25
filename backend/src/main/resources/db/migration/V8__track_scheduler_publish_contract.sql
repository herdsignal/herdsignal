ALTER TABLE scheduler_runs
    ADD COLUMN universe_sha256 CHAR(64) NULL;

ALTER TABLE scheduler_runs
    ADD COLUMN publish_status VARCHAR(30) NULL;
