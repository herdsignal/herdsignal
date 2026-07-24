CREATE TABLE herd_observations (
    id BIGINT NOT NULL AUTO_INCREMENT,
    ticker VARCHAR(10) NOT NULL,
    schema_version VARCHAR(60) NOT NULL,
    state_model_version VARCHAR(40) NOT NULL,
    transition_model_version VARCHAR(40) NOT NULL,
    observation_date DATE NOT NULL,
    last_observed_session DATE NOT NULL,
    generated_at DATETIME NOT NULL,
    source_scope VARCHAR(30) NOT NULL,
    display_label VARCHAR(100),
    claim_code VARCHAR(60),
    state_score DECIMAL(7, 4) NOT NULL,
    herd_stage VARCHAR(20) NOT NULL,
    transition_code VARCHAR(30) NOT NULL,
    raw_transition_code VARCHAR(30) NOT NULL,
    transition_event BOOLEAN NOT NULL DEFAULT FALSE,
    delta_4w DECIMAL(8, 4) NOT NULL,
    delta_13w DECIMAL(8, 4) NOT NULL,
    price_extension DECIMAL(7, 4) NOT NULL,
    trend_position DECIMAL(7, 4) NOT NULL,
    relative_position DECIMAL(7, 4) NOT NULL,
    participation DECIMAL(7, 4) NOT NULL,
    downside_risk_context DECIMAL(7, 4) NOT NULL,
    sector_etf VARCHAR(10) NOT NULL,
    reference_coverage_fraction DECIMAL(7, 6),
    direction_prediction BOOLEAN NOT NULL DEFAULT FALSE,
    operational_action VARCHAR(10) NOT NULL DEFAULT 'HOLD',
    operational_action_ratio DECIMAL(6, 4) NOT NULL DEFAULT 0.0000,
    survivorship_safe BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_herd_observations_model_date
        UNIQUE (ticker, state_model_version, observation_date),
    CONSTRAINT ck_herd_observations_state_score
        CHECK (state_score >= 0 AND state_score <= 100),
    CONSTRAINT ck_herd_observations_state_only
        CHECK (
            direction_prediction = FALSE
            AND operational_action = 'HOLD'
            AND operational_action_ratio = 0
            AND survivorship_safe = FALSE
        ),
    INDEX ix_herd_observations_ticker_latest
        (ticker, state_model_version, observation_date),
    INDEX ix_herd_observations_generated_at (generated_at)
);
