CREATE TABLE portfolio_ledger_entries (
    id BIGINT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(50) NOT NULL,
    entry_type VARCHAR(20) NOT NULL,
    ticker VARCHAR(10),
    occurred_on DATE NOT NULL,
    quantity DECIMAL(18, 6),
    unit_price DECIMAL(16, 6),
    gross_amount DECIMAL(18, 2) NOT NULL,
    fee_amount DECIMAL(16, 2) NOT NULL DEFAULT 0,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    source VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    note VARCHAR(200),
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    INDEX ix_portfolio_ledger_user_date (user_id, occurred_on, id),
    INDEX ix_portfolio_ledger_user_ticker_date (user_id, ticker, occurred_on)
);
