-- M6 C2 Informed Trading — alert_outcomes table + alerts C2 columns

-- 1. New table: alert_outcomes (post-resolution tracking for calibration)
CREATE TABLE IF NOT EXISTS alert_outcomes (
    alert_id VARCHAR PRIMARY KEY,
    condition_id VARCHAR NOT NULL,
    resolved_at TIMESTAMP,
    resolution_outcome VARCHAR CHECK (resolution_outcome IN ('YES', 'NO', 'INVALID', 'PENDING')),
    direction_traded VARCHAR,
    was_direction_correct BOOLEAN,
    price_at_alert DECIMAL(6,4),
    price_at_resolution DECIMAL(6,4),
    shadow_pnl_simulated DECIMAL(18,2),
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alert_outcomes_market ON alert_outcomes (condition_id);

-- 2. Add C2-specific columns to alerts
-- alignment_score already exists from migration 005
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS score INTEGER;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS features_passed VARCHAR;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS momentum_4h DECIMAL(6,4);
