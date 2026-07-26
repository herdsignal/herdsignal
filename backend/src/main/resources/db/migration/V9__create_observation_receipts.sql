CREATE TABLE user_observation_receipts (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    seen_through_date DATE NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_observation_receipt_user_ticker
        UNIQUE (user_id, ticker),
    INDEX ix_observation_receipt_user (user_id)
);
