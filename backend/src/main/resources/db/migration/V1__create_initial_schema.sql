CREATE TABLE IF NOT EXISTS app_users (
    id VARCHAR(36) NOT NULL,
    provider VARCHAR(20) NOT NULL,
    provider_subject VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    profile_image_url VARCHAR(1000),
    role VARCHAR(20) NOT NULL DEFAULT 'USER',
    created_at DATETIME NOT NULL,
    last_login_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uk_app_users_provider_subject UNIQUE (provider, provider_subject),
    INDEX ix_app_users_email (email)
);

CREATE TABLE IF NOT EXISTS stocks (
    id BIGINT NOT NULL AUTO_INCREMENT,
    ticker VARCHAR(10) NOT NULL,
    name VARCHAR(100),
    sector VARCHAR(50),
    logo_url VARCHAR(300),
    market_cap_category VARCHAR(20),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uk_stocks_ticker UNIQUE (ticker)
);

CREATE TABLE IF NOT EXISTS herd_scores (
    id BIGINT NOT NULL AUTO_INCREMENT,
    ticker VARCHAR(10) NOT NULL,
    score_date DATE NOT NULL,
    herd_score DECIMAL(5, 2) NOT NULL,
    herd_stage VARCHAR(20) NOT NULL,
    `signal` VARCHAR(20),
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_herd_scores_ticker_date UNIQUE (ticker, score_date),
    INDEX ix_herd_scores_ticker_date_desc (ticker, score_date)
);

CREATE TABLE IF NOT EXISTS herd_indicators (
    id BIGINT NOT NULL AUTO_INCREMENT,
    ticker VARCHAR(10) NOT NULL,
    score_date DATE NOT NULL,
    weekly_rsi DECIMAL(5, 2),
    monthly_rsi DECIMAL(5, 2),
    position_52w DECIMAL(5, 2),
    ma200_deviation DECIMAL(5, 2),
    volume_strength DECIMAL(5, 2),
    ma200_weekly DECIMAL(5, 2),
    herd_base DECIMAL(5, 2),
    eps_multiplier DECIMAL(5, 2),
    sector_multiplier DECIMAL(5, 2),
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_herd_indicators_ticker_date UNIQUE (ticker, score_date)
);

CREATE TABLE IF NOT EXISTS daily_prices (
    id BIGINT NOT NULL AUTO_INCREMENT,
    ticker VARCHAR(10) NOT NULL,
    price_date DATE NOT NULL,
    open_price DECIMAL(12, 4),
    high_price DECIMAL(12, 4),
    low_price DECIMAL(12, 4),
    close_price DECIMAL(12, 4),
    volume BIGINT,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_daily_prices_ticker_date UNIQUE (ticker, price_date),
    INDEX ix_daily_prices_ticker_date_desc (ticker, price_date)
);

CREATE TABLE IF NOT EXISTS user_portfolio (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL DEFAULT 'local',
    ticker VARCHAR(10) NOT NULL,
    avg_price DECIMAL(12, 4),
    quantity DECIMAL(12, 4),
    memo VARCHAR(200),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_portfolio_user_ticker UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS investor_profiles (
    user_id VARCHAR(50) NOT NULL,
    strategy VARCHAR(30) NOT NULL DEFAULT 'EXISTING_HOLDER',
    risk_tolerance VARCHAR(20) NOT NULL DEFAULT 'BALANCED',
    time_horizon_years INT NOT NULL DEFAULT 10,
    liquidity_buffer_months INT NOT NULL DEFAULT 6,
    max_action_ratio DECIMAL(5, 4) NOT NULL DEFAULT 0.1500,
    target_equity_ratio DECIMAL(5, 4) NOT NULL DEFAULT 0.7000,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS user_watchlist (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL DEFAULT 'local',
    ticker VARCHAR(10) NOT NULL,
    memo VARCHAR(200),
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_watchlist_user_ticker UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS user_cash_balance (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    cash_amount DECIMAL(15, 2) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_user_cash_balance_user UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS user_cash_history (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    snapshot_date DATE NOT NULL,
    cash_amount DECIMAL(15, 2) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_user_cash_history_user_date UNIQUE (user_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS portfolio_history (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    snapshot_date DATE NOT NULL,
    total_value DECIMAL(15, 2) NOT NULL,
    total_cost DECIMAL(15, 2) NOT NULL,
    total_return_pct DECIMAL(8, 4) NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_portfolio_history_user_date UNIQUE (user_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS signal_journal (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL DEFAULT 'local',
    ticker VARCHAR(10) NOT NULL,
    action_type VARCHAR(20) NOT NULL,
    action_label VARCHAR(50),
    score_date DATE,
    herd_score DECIMAL(5, 2),
    herd_stage VARCHAR(20),
    `signal` VARCHAR(20),
    signal_label VARCHAR(100),
    action_ratio DECIMAL(6, 4),
    signal_duration_days BIGINT,
    stage_duration_days BIGINT,
    price DECIMAL(12, 4),
    quantity DECIMAL(12, 4),
    amount DECIMAL(15, 2),
    profit_pct DECIMAL(8, 4),
    memo VARCHAR(1000),
    recorded_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    INDEX ix_signal_journal_user_recorded (user_id, recorded_at),
    INDEX ix_signal_journal_user_ticker_recorded (user_id, ticker, recorded_at)
);
