ALTER TABLE user_portfolio
    ADD COLUMN target_weight DECIMAL(5, 4) NULL;

ALTER TABLE investor_profiles
    ADD COLUMN rebalance_budget DECIMAL(15, 2) NOT NULL DEFAULT 1000.00;

ALTER TABLE investor_profiles
    ADD COLUMN cash_target_ratio DECIMAL(5, 4) NOT NULL DEFAULT 0.1000;

ALTER TABLE investor_profiles
    ADD COLUMN rebalance_mode VARCHAR(20) NOT NULL DEFAULT 'STANDARD';
