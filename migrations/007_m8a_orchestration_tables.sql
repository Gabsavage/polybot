-- M8-A: Recreate orchestration tables with correct schema
-- (existing tables are empty, safe to DROP)

DROP TABLE IF EXISTS kill_switches;
CREATE TABLE kill_switches (
    target       VARCHAR PRIMARY KEY,
    enabled      BOOLEAN DEFAULT FALSE,
    reason       VARCHAR,
    toggled_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    toggled_by   VARCHAR DEFAULT 'manual'
);

DROP TABLE IF EXISTS rate_limit_counters;
CREATE TABLE rate_limit_counters (
    component    VARCHAR,
    "window"     VARCHAR,
    count        INTEGER DEFAULT 0,
    window_start TIMESTAMP,
    PRIMARY KEY (component, "window")
);

DROP SEQUENCE IF EXISTS audit_log_seq;
DROP TABLE IF EXISTS audit_log;
CREATE SEQUENCE audit_log_seq START 1;
CREATE TABLE audit_log (
    id           BIGINT DEFAULT nextval('audit_log_seq') PRIMARY KEY,
    event_type   VARCHAR,
    target       VARCHAR,
    action       VARCHAR,
    reason       VARCHAR,
    actor        VARCHAR DEFAULT 'system',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
