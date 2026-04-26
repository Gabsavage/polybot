-- M9: CEX funding detection tables

CREATE TABLE IF NOT EXISTS cex_hot_wallets (
    address VARCHAR PRIMARY KEY,
    exchange_name VARCHAR NOT NULL,
    label VARCHAR,
    verified BOOLEAN DEFAULT TRUE,
    source VARCHAR,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cex_funding_map (
    wallet_address VARCHAR PRIMARY KEY,
    funded_by VARCHAR,
    funded_by_hop2 VARCHAR,
    cex_source VARCHAR,
    deposit_address VARCHAR,
    confidence DECIMAL(3,2),
    method VARCHAR CHECK (method IN ('direct_hot_wallet', 'hop2_hot_wallet', 'deposit_address_match')),
    traced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cex_funding_deposit ON cex_funding_map (deposit_address);
CREATE INDEX IF NOT EXISTS idx_cex_funding_source ON cex_funding_map (cex_source);
