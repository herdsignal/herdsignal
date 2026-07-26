ALTER TABLE portfolio_ledger_entries
    ADD COLUMN split_ratio DECIMAL(18, 8) NULL AFTER unit_price;
