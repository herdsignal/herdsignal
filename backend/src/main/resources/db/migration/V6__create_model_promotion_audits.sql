CREATE TABLE model_promotion_audits (
    id BIGINT NOT NULL AUTO_INCREMENT,
    candidate_id VARCHAR(80) NOT NULL,
    model_version VARCHAR(80),
    artifact_sha256 CHAR(64),
    ticker VARCHAR(10),
    requested_action VARCHAR(10),
    requested_ratio DECIMAL(6, 4),
    decision VARCHAR(20) NOT NULL,
    reason_code VARCHAR(80) NOT NULL,
    policy_version VARCHAR(40),
    reviewer VARCHAR(100),
    approval_file_sha256 CHAR(64),
    approved_at DATETIME,
    requested_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_model_promotion_audits_decision
        CHECK (decision IN ('GRANTED', 'REJECTED')),
    CONSTRAINT ck_model_promotion_audits_ratio
        CHECK (
            requested_ratio IS NULL
            OR (requested_ratio >= 0 AND requested_ratio <= 1)
        ),
    INDEX ix_model_promotion_audits_candidate_time
        (candidate_id, requested_at)
);
