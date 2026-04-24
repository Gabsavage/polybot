-- M3 enrichment tables — proxy mapping, resolutions, broad trades
-- Ref: m3_enrichment_spec.md, ADR-011, ADR-014

-- 1. proxy_eoa_map: proxy wallet → EOA owner mapping
CREATE TABLE IF NOT EXISTS proxy_eoa_map (
    proxy_address VARCHAR PRIMARY KEY,
    eoa_address VARCHAR NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    method VARCHAR CHECK (method IN ('direct_factory', 'first_tx', 'heuristic', 'manual')),
    first_seen_block BIGINT,
    first_seen_ts TIMESTAMP,
    factory_contract VARCHAR,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_proxy_eoa ON proxy_eoa_map (eoa_address);

-- 2. resolutions: market resolution tracking via UMA Oracle
CREATE TABLE IF NOT EXISTS resolutions (
    condition_id VARCHAR PRIMARY KEY,
    question_id VARCHAR,
    proposed_at TIMESTAMP,
    proposed_price DECIMAL(18,6),
    proposer VARCHAR,
    disputed BOOLEAN DEFAULT FALSE,
    dispute_count INTEGER DEFAULT 0,
    settled_at TIMESTAMP,
    final_price DECIMAL(18,6),
    settled_outcome VARCHAR,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. trades_all: broad on-chain trades via Goldsky subgraph
CREATE TABLE IF NOT EXISTS trades_all (
    transaction_hash VARCHAR PRIMARY KEY,
    proxy_wallet VARCHAR,
    eoa_address VARCHAR,
    condition_id VARCHAR,
    side VARCHAR,
    size_usd DECIMAL(18,2),
    price DECIMAL(6,4),
    timestamp_ts TIMESTAMP,
    source VARCHAR DEFAULT 'goldsky',
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_all_wallet_time ON trades_all (proxy_wallet, timestamp_ts DESC);
CREATE INDEX IF NOT EXISTS idx_trades_all_market_time ON trades_all (condition_id, timestamp_ts DESC);
