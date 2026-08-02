CREATE TABLE operating_review_snapshots (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    reviewed_at DATETIME NOT NULL,
    observation_date DATE,
    reference_price_date DATE,
    reference_price DECIMAL(12, 4),
    decision_code VARCHAR(30) NOT NULL,
    action_authorized BOOLEAN NOT NULL,
    action_ratio DECIMAL(7, 6) NOT NULL,
    evidence_schema_version VARCHAR(30) NOT NULL,
    decision_model_version VARCHAR(50) NOT NULL,
    payload_json LONGTEXT NOT NULL,
    payload_sha256 CHAR(64) NOT NULL,
    PRIMARY KEY (id),
    INDEX ix_operating_review_user_ticker_time (user_id, ticker, reviewed_at),
    INDEX ix_operating_review_ticker_observation (ticker, observation_date)
);
