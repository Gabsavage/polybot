-- M4 alerts + bankroll_state schema — align with C1 spec
-- Both tables are empty in prod, safe to DROP + recreate.

DROP TABLE IF EXISTS alerts;

CREATE TABLE alerts (
    alert_id VARCHAR PRIMARY KEY,
    component VARCHAR CHECK (component IN ('C1', 'C2', 'C3_manual')),
    emitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trade_hash VARCHAR,
    wallet_address VARCHAR,
    condition_id VARCHAR,
    side VARCHAR,
    size_usd DECIMAL(18,2),
    price DECIMAL(6,4),
    size_suggested_usd DECIMAL(18,2),
    resolution_risk_score DECIMAL(3,2),
    tags VARCHAR,
    telegram_message_id BIGINT,
    shadow_mode BOOLEAN DEFAULT TRUE,
    alignment_score INTEGER,
    outcome_known BOOLEAN DEFAULT FALSE,
    was_direction_correct BOOLEAN,
    realized_pnl_simulated DECIMAL(18,2),
    dedup_hash VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_alerts_wallet_market ON alerts (wallet_address, condition_id, emitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_dedup ON alerts (dedup_hash);

DROP TABLE IF EXISTS bankroll_state;

CREATE TABLE bankroll_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    amount DECIMAL(18,2) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (id = 1)
);
