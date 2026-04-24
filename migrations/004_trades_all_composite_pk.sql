-- M3 trades_all schema fix — composite PK for multiple events per tx
-- A single Polymarket transaction contains multiple OrderFilled events
-- (avg 2.7, up to 41). The old transaction_hash PK cannot store them all.

DROP TABLE IF EXISTS trades_all;

CREATE TABLE trades_all (
    tx_hash_log_idx VARCHAR PRIMARY KEY,   -- "{txHash}_{logIndex}"
    transaction_hash VARCHAR NOT NULL,
    log_index INTEGER NOT NULL,
    proxy_wallet VARCHAR,
    eoa_address VARCHAR,
    condition_id VARCHAR,
    side VARCHAR,
    size_usd DECIMAL(18,2),
    price DECIMAL(6,4),
    timestamp_ts TIMESTAMP,
    source VARCHAR DEFAULT 'alchemy',
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_all_wallet_time ON trades_all (proxy_wallet, timestamp_ts DESC);
CREATE INDEX IF NOT EXISTS idx_trades_all_market_time ON trades_all (condition_id, timestamp_ts DESC);
CREATE INDEX IF NOT EXISTS idx_trades_all_tx ON trades_all (transaction_hash);
