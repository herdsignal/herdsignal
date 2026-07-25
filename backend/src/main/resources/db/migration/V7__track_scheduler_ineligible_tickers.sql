ALTER TABLE scheduler_runs
    ADD COLUMN skipped_count INT NOT NULL DEFAULT 0;

ALTER TABLE scheduler_runs
    ADD COLUMN skipped_tickers TEXT NULL;
