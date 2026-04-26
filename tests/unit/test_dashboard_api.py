"""Tests for the dashboard API endpoints."""

import duckdb
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("CREATE SEQUENCE audit_log_seq START 1")
    con.execute("""
        CREATE TABLE kill_switches (
            target VARCHAR PRIMARY KEY,
            enabled BOOLEAN DEFAULT FALSE,
            reason VARCHAR,
            toggled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            toggled_by VARCHAR DEFAULT 'manual'
        )
    """)
    con.execute("""
        CREATE TABLE rate_limit_counters (
            component VARCHAR,
            "window" VARCHAR,
            count INTEGER DEFAULT 0,
            window_start TIMESTAMP,
            PRIMARY KEY (component, "window")
        )
    """)
    con.execute("""
        CREATE TABLE indexer_state (
            indexer_name VARCHAR PRIMARY KEY,
            last_synced_at TIMESTAMP,
            last_block_number BIGINT,
            last_cursor VARCHAR,
            last_run_status VARCHAR,
            last_run_duration_ms INTEGER,
            last_error VARCHAR,
            ingested_count BIGINT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE audit_log (
            id BIGINT DEFAULT nextval('audit_log_seq') PRIMARY KEY,
            event_type VARCHAR, target VARCHAR, action VARCHAR,
            reason VARCHAR, actor VARCHAR DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE alerts (
            alert_id VARCHAR PRIMARY KEY,
            component VARCHAR,
            emitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            trade_hash VARCHAR, wallet_address VARCHAR,
            condition_id VARCHAR, side VARCHAR,
            size_usd DECIMAL(18,2), price DECIMAL(6,4),
            size_suggested_usd DECIMAL(18,2),
            resolution_risk_score DECIMAL(3,2),
            telegram_message_id BIGINT,
            alignment_score INTEGER, score INTEGER,
            features_passed VARCHAR, momentum_4h DECIMAL(6,4),
            shadow_mode BOOLEAN DEFAULT TRUE,
            dedup_hash VARCHAR, tags VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE alert_outcomes (
            alert_id VARCHAR PRIMARY KEY,
            condition_id VARCHAR NOT NULL,
            resolved_at TIMESTAMP,
            resolution_outcome VARCHAR,
            direction_traded VARCHAR,
            was_direction_correct BOOLEAN,
            price_at_alert DECIMAL(6,4),
            price_at_resolution DECIMAL(6,4),
            shadow_pnl_simulated DECIMAL(18,2),
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE markets (
            condition_id VARCHAR PRIMARY KEY,
            title VARCHAR, slug VARCHAR, event_slug VARCHAR,
            volume_24h DECIMAL(18,2), liquidity_usd DECIMAL(18,2),
            end_date TIMESTAMP, active BOOLEAN DEFAULT TRUE,
            volume_cumulative_usd DECIMAL(18,2),
            category VARCHAR, status VARCHAR,
            last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE tracked_wallets (
            address VARCHAR PRIMARY KEY,
            tier VARCHAR, active BOOLEAN, source VARCHAR,
            added_at TIMESTAMP, last_reviewed_at TIMESTAMP,
            honeypot_flag BOOLEAN, honeypot_score DECIMAL(3,2),
            tier_a_confidence DECIMAL(3,2),
            notes TEXT, last_seen_timestamp BIGINT DEFAULT 0
        )
    """)
    con.execute("""
        CREATE TABLE trades (
            transaction_hash VARCHAR PRIMARY KEY,
            proxy_wallet VARCHAR NOT NULL,
            condition_id VARCHAR NOT NULL,
            asset_id VARCHAR NOT NULL,
            side VARCHAR, size_usd DECIMAL(18,2) NOT NULL,
            price DECIMAL(6,4) NOT NULL,
            outcome VARCHAR, outcome_index INTEGER,
            timestamp_unix BIGINT NOT NULL,
            timestamp_ts TIMESTAMP NOT NULL,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE resolution_risk_cache (
            condition_id VARCHAR PRIMARY KEY,
            llm_score DECIMAL(3,2),
            llm_reasons TEXT[], llm_red_flags TEXT[],
            llm_model_version VARCHAR,
            computed_at TIMESTAMP
        )
    """)
    con.close()
    return path


@pytest.fixture
def client(db_path):
    from polybot.dashboard.api import app, get_db

    def override_db():
        con = duckdb.connect(db_path, read_only=True)
        try:
            yield con
        finally:
            con.close()

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestStatusEndpoint:
    def test_status_returns_all_sections(self, client, db_path):
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO kill_switches (target, enabled, reason) VALUES ('c1', TRUE, 'test')"
        )
        con.execute(
            'INSERT INTO rate_limit_counters (component, "window", count, window_start) '
            "VALUES ('c1', 'hourly', 5, CURRENT_TIMESTAMP)"
        )
        con.execute(
            "INSERT INTO indexer_state (indexer_name, last_synced_at, last_run_status, "
            "last_run_duration_ms, ingested_count) "
            "VALUES ('markets_gamma', CURRENT_TIMESTAMP, 'success', 1500, 46000)"
        )
        con.close()

        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["kill_switches"]) == 1
        assert data["kill_switches"][0]["target"] == "c1"
        assert len(data["rate_limits"]) == 1
        assert data["rate_limits"][0]["component"] == "c1"
        assert len(data["indexers"]) == 1
        assert data["indexers"][0]["name"] == "markets_gamma"
        assert data["indexers"][0]["ingested_count"] == 46000
