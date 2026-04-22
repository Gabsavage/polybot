-- M2 schema alignment — realign tables with actual API sources
-- Ref: indexer_trades_spec.md, A_architecture_technique.md §3.2, ADR-013

-- 1A. trades: DROP + recreate (table is EMPTY in M1, safe to drop)
-- Old schema was designed for on-chain events (tx_hash + log_index PK).
-- Data API returns different fields (proxyWallet, transactionHash, no log_index).
DROP TABLE IF EXISTS trades;

CREATE TABLE trades (
    transaction_hash  VARCHAR PRIMARY KEY,
    proxy_wallet      VARCHAR NOT NULL,
    condition_id      VARCHAR NOT NULL,
    asset_id          VARCHAR NOT NULL,
    side              VARCHAR CHECK (side IN ('BUY', 'SELL')),
    size_usd          DECIMAL(18,2) NOT NULL,
    price             DECIMAL(6,4) NOT NULL,
    outcome           VARCHAR,
    outcome_index     INTEGER,
    timestamp_unix    BIGINT NOT NULL,
    timestamp_ts      TIMESTAMP NOT NULL,
    market_title      VARCHAR,
    market_slug       VARCHAR,
    event_slug        VARCHAR,
    wallet_name       VARCHAR,
    ingested_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_wallet_time ON trades (proxy_wallet, timestamp_ts DESC);
CREATE INDEX idx_trades_market_time ON trades (condition_id, timestamp_ts DESC);

-- 1B. markets: add columns available from Gamma API
ALTER TABLE markets ADD COLUMN IF NOT EXISTS title VARCHAR;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS slug VARCHAR;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS event_slug VARCHAR;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS volume_24h DECIMAL(18,2);
ALTER TABLE markets ADD COLUMN IF NOT EXISTS volume_1h DECIMAL(18,2);
ALTER TABLE markets ADD COLUMN IF NOT EXISTS end_date TIMESTAMP;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS start_date TIMESTAMP;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS active BOOLEAN;
ALTER TABLE markets ADD COLUMN IF NOT EXISTS resolved BOOLEAN;

-- 1C. tracked_wallets: add cursor column for trade indexer dedup
ALTER TABLE tracked_wallets ADD COLUMN IF NOT EXISTS last_seen_timestamp BIGINT DEFAULT 0;

-- 1D. indexer_state: cursor tracking for all indexers
CREATE TABLE IF NOT EXISTS indexer_state (
    indexer_name        VARCHAR PRIMARY KEY,
    last_synced_at      TIMESTAMP NOT NULL,
    last_block_number   BIGINT,
    last_cursor         VARCHAR,
    last_run_status     VARCHAR CHECK (last_run_status IN ('success', 'failed', 'running')),
    last_run_duration_ms INTEGER,
    last_error          VARCHAR,
    ingested_count      BIGINT DEFAULT 0,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
