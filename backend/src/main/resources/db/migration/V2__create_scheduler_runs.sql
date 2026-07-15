CREATE TABLE scheduler_runs (
    id BIGINT NOT NULL AUTO_INCREMENT,
    job_name VARCHAR(50) NOT NULL,
    trigger_type VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL,
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    total_count INT NOT NULL DEFAULT 0,
    success_count INT NOT NULL DEFAULT 0,
    failed_count INT NOT NULL DEFAULT 0,
    failed_tickers TEXT,
    error_message TEXT,
    PRIMARY KEY (id),
    INDEX ix_scheduler_runs_job_started (job_name, started_at)
);
