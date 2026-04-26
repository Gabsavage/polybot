"""Tests for weekly report module."""

from datetime import datetime, timezone

import duckdb
import pytest

from polybot.components.weekly_report import generate_weekly_report


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("""
        CREATE TABLE alerts (
            alert_id VARCHAR PRIMARY KEY,
            component VARCHAR,
            emitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            trade_hash VARCHAR,
            wallet_address VARCHAR,
            condition_id VARCHAR,
            side VARCHAR,
            size_usd DECIMAL(18,2),
            price DECIMAL(6,4),
            size_suggested_usd DECIMAL(18,2),
            resolution_risk_score DECIMAL(3,2),
            resolution_risk_category VARCHAR,
            telegram_message_id BIGINT,
            alignment_score INTEGER,
            score INTEGER,
            features_passed VARCHAR,
            momentum_4h DECIMAL(6,4)
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
        CREATE TABLE tracked_wallets (
            address VARCHAR PRIMARY KEY,
            tier VARCHAR,
            active BOOLEAN,
            source VARCHAR,
            added_at TIMESTAMP,
            last_reviewed_at TIMESTAMP,
            honeypot_flag BOOLEAN,
            honeypot_score DECIMAL(3,2),
            notes TEXT,
            last_seen_timestamp BIGINT DEFAULT 0
        )
    """)
    con.execute("""
        CREATE TABLE trades (
            transaction_hash VARCHAR PRIMARY KEY,
            proxy_wallet VARCHAR NOT NULL,
            condition_id VARCHAR NOT NULL,
            asset_id VARCHAR NOT NULL,
            side VARCHAR,
            size_usd DECIMAL(18,2) NOT NULL,
            price DECIMAL(6,4) NOT NULL,
            outcome VARCHAR,
            outcome_index INTEGER,
            timestamp_unix BIGINT NOT NULL,
            timestamp_ts TIMESTAMP NOT NULL,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("CREATE SEQUENCE audit_log_seq START 1")
    con.execute("""
        CREATE TABLE audit_log (
            id BIGINT DEFAULT nextval('audit_log_seq') PRIMARY KEY,
            event_type VARCHAR, target VARCHAR, action VARCHAR,
            reason VARCHAR, actor VARCHAR DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        CREATE TABLE resolution_risk_cache (
            condition_id VARCHAR PRIMARY KEY,
            llm_score DECIMAL(3,2),
            llm_reasons TEXT[],
            llm_red_flags TEXT[],
            llm_model_version VARCHAR,
            computed_at TIMESTAMP
        )
    """)
    con.close()
    return path


def _seed_data(db_path):
    """Insert test data: C1 + C2 alerts, outcomes, wallets, trades, audit events, LLM cache."""
    con = duckdb.connect(db_path)
    # C1 alerts
    for i in range(8):
        con.execute(
            "INSERT INTO alerts (alert_id, component, side, emitted_at, condition_id, size_usd) "
            "VALUES (?, 'C1', ?, CURRENT_TIMESTAMP - INTERVAL 1 DAY, ?, 500)",
            [f"AL_C1_{i}", "BUY" if i < 6 else "SELL", f"cond_c1_{i}"],
        )
    # C2 alerts
    for i in range(3):
        con.execute(
            "INSERT INTO alerts (alert_id, component, score, emitted_at, condition_id, alignment_score) "
            "VALUES (?, 'C2', ?, CURRENT_TIMESTAMP - INTERVAL 2 DAY, ?, ?)",
            [f"AL_C2_{i}", 4 + i, f"cond_c2_{i}", [1, -1, 0][i]],
        )
    # Outcomes (5 resolved, 6 pending)
    for i in range(5):
        con.execute(
            "INSERT INTO alert_outcomes (alert_id, condition_id, resolution_outcome, was_direction_correct, shadow_pnl_simulated) "
            "VALUES (?, ?, 'YES', ?, ?)",
            [f"AL_C1_{i}", f"cond_c1_{i}", i < 4, 25.0 if i < 4 else -12.60],
        )
    # Wallets (15 tier A, 11 active with trades, 4 silent)
    for i in range(15):
        con.execute(
            "INSERT INTO tracked_wallets (address, tier, active, notes) VALUES (?, 'A', TRUE, ?)",
            [f"0xwallet_{i}", f"wallet_{i}"],
        )
    # Trades for 11 wallets
    for i in range(11):
        for j in range(3):
            con.execute(
                "INSERT INTO trades (transaction_hash, proxy_wallet, condition_id, asset_id, "
                "side, size_usd, price, timestamp_unix, timestamp_ts) "
                "VALUES (?, ?, 'cond_x', 'asset_x', 'BUY', 100, 0.65, 1714100000, CURRENT_TIMESTAMP - INTERVAL 1 DAY)",
                [f"tx_{i}_{j}", f"0xwallet_{i}"],
            )
    # Audit events
    con.execute(
        "INSERT INTO audit_log (event_type, target, action) VALUES ('rate_limit', 'c2', 'exceeded')"
    )
    # Indexer errors
    con.execute(
        "INSERT INTO indexer_state (indexer_name, last_synced_at, last_run_status) VALUES ('markets_gamma', CURRENT_TIMESTAMP, 'failed')"
    )
    con.execute(
        "INSERT INTO indexer_state (indexer_name, last_synced_at, last_run_status) VALUES ('onchain_alchemy', CURRENT_TIMESTAMP, 'success')"
    )
    # LLM cache
    for i in range(50):
        con.execute(
            "INSERT INTO resolution_risk_cache (condition_id, llm_score, computed_at) VALUES (?, 0.5, CURRENT_TIMESTAMP)",
            [f"risk_{i}"],
        )
    con.close()


class TestWeeklyReportFormat:
    def test_all_sections_present(self, db_path):
        _seed_data(db_path)
        report = generate_weekly_report(db_path, weeks=1)

        assert "Weekly Report" in report
        assert "Alertes" in report
        assert "C1" in report
        assert "C2" in report
        assert "Performance shadow" in report
        assert "Performance cumul" in report
        assert "Wallets Tier A" in report
        assert "Alignment" in report
        assert "Orchestrateur" in report
        assert "Co" in report  # Coûts (accented char)

    def test_c1_count_correct(self, db_path):
        _seed_data(db_path)
        report = generate_weekly_report(db_path, weeks=1)
        assert "8 alertes" in report

    def test_shadow_pnl_present(self, db_path):
        _seed_data(db_path)
        report = generate_weekly_report(db_path, weeks=1)
        assert "$" in report
        assert "4/5" in report or "80%" in report


class TestWeeklyReportEmpty:
    def test_no_alerts_short_message(self, db_path):
        report = generate_weekly_report(db_path, weeks=1)
        assert "Aucune alerte" in report


class TestWeeklyReportCosts:
    def test_llm_cost_shown(self, db_path):
        _seed_data(db_path)
        report = generate_weekly_report(db_path, weeks=1)
        assert "$0.05" in report or "0.05" in report
        assert "50" in report  # 50 calls
