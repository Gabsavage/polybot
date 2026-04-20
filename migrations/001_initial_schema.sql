-- M1 initial schema — 10 tables + snapshot_universe
-- Ref: A_architecture_technique.md §3.2 + B_plan_developpement.md §3

CREATE TABLE IF NOT EXISTS markets (
    condition_id           VARCHAR PRIMARY KEY,
    question_id            VARCHAR,
    question_text          TEXT,
    description            TEXT,
    category               VARCHAR,
    tags                   VARCHAR[],
    outcomes               VARCHAR[],
    neg_risk               BOOLEAN,
    resolution_source      TEXT,
    resolution_date        TIMESTAMP,
    created_at             TIMESTAMP,
    closed_at              TIMESTAMP,
    volume_cumulative_usd  DECIMAL(18,2),
    liquidity_usd          DECIMAL(18,2),
    status                 VARCHAR,
    last_synced_at         TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trades (
    tx_hash                VARCHAR,
    log_index              INTEGER,
    block_number           BIGINT,
    block_timestamp        TIMESTAMP,
    condition_id           VARCHAR,
    token_id               VARCHAR,
    outcome_index          INTEGER,
    maker                  VARCHAR,
    taker                  VARCHAR,
    side                   VARCHAR,
    price                  DECIMAL(6,4),
    size_tokens            DECIMAL(18,6),
    size_usd               DECIMAL(18,2),
    fee                    DECIMAL(18,6),
    exchange               VARCHAR,
    PRIMARY KEY (tx_hash, log_index)
);

CREATE TABLE IF NOT EXISTS wallets (
    address                VARCHAR PRIMARY KEY,
    first_seen_at          TIMESTAMP,
    last_active_at         TIMESTAMP,
    total_trades           INTEGER,
    total_volume_usd       DECIMAL(18,2),
    is_proxy               BOOLEAN,
    resolved_eoa           VARCHAR,
    cluster_id             VARCHAR
);

CREATE TABLE IF NOT EXISTS tracked_wallets (
    address                VARCHAR PRIMARY KEY,
    tier                   VARCHAR,
    active                 BOOLEAN,
    source                 VARCHAR,
    added_at               TIMESTAMP,
    last_reviewed_at       TIMESTAMP,
    honeypot_flag          BOOLEAN,
    honeypot_score         DECIMAL(3,2),
    tier_a_confidence      DECIMAL(3,2),
    notes                  TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id               VARCHAR PRIMARY KEY,
    component              VARCHAR,
    emitted_at             TIMESTAMP,
    condition_id           VARCHAR,
    token_id               VARCHAR,
    side                   VARCHAR,
    price_at_alert         DECIMAL(6,4),
    size_recommended_usd   DECIMAL(18,2),
    bankroll_snapshot      DECIMAL(18,2),
    signal_source          VARCHAR,
    features               JSON,
    resolution_risk_score  DECIMAL(3,2),
    resolution_risk_label  VARCHAR,
    telegram_message_id    VARCHAR
);

CREATE TABLE IF NOT EXISTS kill_switches (
    component              VARCHAR PRIMARY KEY,
    state                  VARCHAR,
    set_at                 TIMESTAMP,
    reason                 TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id                 BIGINT PRIMARY KEY,
    timestamp              TIMESTAMP,
    level                  VARCHAR,
    component              VARCHAR,
    event                  VARCHAR,
    details                JSON
);

CREATE SEQUENCE IF NOT EXISTS audit_log_seq START 1;

CREATE TABLE IF NOT EXISTS rate_limit_counters (
    component              VARCHAR,
    hour_bucket            TIMESTAMP,
    count                  INTEGER,
    PRIMARY KEY (component, hour_bucket)
);

CREATE TABLE IF NOT EXISTS bankroll_state (
    updated_at             TIMESTAMP PRIMARY KEY,
    amount_eur             DECIMAL(18,2),
    note                   TEXT
);

CREATE TABLE IF NOT EXISTS resolution_risk_cache (
    condition_id           VARCHAR PRIMARY KEY,
    llm_score              DECIMAL(3,2),
    llm_reasons            TEXT[],
    llm_red_flags          TEXT[],
    llm_model_version      VARCHAR,
    computed_at            TIMESTAMP
);

-- Snapshot universe: which markets to snapshot hourly
CREATE TABLE IF NOT EXISTS snapshot_universe (
    condition_id           VARCHAR PRIMARY KEY,
    token_id_yes           VARCHAR,
    token_id_no            VARCHAR,
    question_text          TEXT,
    volume_24h_usd         DECIMAL(18,2),
    refreshed_at           TIMESTAMP
);
