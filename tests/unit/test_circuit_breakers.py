"""Tests for circuit breakers module."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import duckdb
import pytest

from polybot.orchestrator.circuit_breakers import CircuitBreaker


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("""
        CREATE TABLE indexer_state (
            indexer_name VARCHAR PRIMARY KEY,
            last_synced_at TIMESTAMP,
            last_block_number BIGINT,
            last_cursor VARCHAR,
            last_run_status VARCHAR CHECK (last_run_status IN ('success', 'failed', 'running')),
            last_run_duration_ms INTEGER,
            last_error VARCHAR,
            ingested_count BIGINT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE kill_switches (
            target VARCHAR PRIMARY KEY,
            enabled BOOLEAN DEFAULT FALSE,
            reason VARCHAR,
            toggled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            toggled_by VARCHAR DEFAULT 'manual'
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
        CREATE TABLE resolution_risk_cache (
            condition_id VARCHAR PRIMARY KEY,
            ambiguity_score DOUBLE,
            reasons JSON,
            red_flags JSON,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.close()
    return path


class TestCircuitBreakerIndexer:
    def test_three_consecutive_failures_triggers_kill_switch(self, db_path):
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO indexer_state (indexer_name, last_synced_at, last_run_status) "
            "VALUES ('onchain_alchemy', CURRENT_TIMESTAMP, 'failed')"
        )
        con.close()

        cb = CircuitBreaker(db_path)
        # Simulate 3 consecutive checks seeing 'failed'
        cb.check_indexer_health()
        cb.check_indexer_health()
        cb.check_indexer_health()

        from polybot.orchestrator.kill_switches import is_component_enabled, _invalidate_cache
        _invalidate_cache()
        assert is_component_enabled(db_path, "onchain") is False

    def test_success_resets_failure_count(self, db_path):
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO indexer_state (indexer_name, last_synced_at, last_run_status) "
            "VALUES ('onchain_alchemy', CURRENT_TIMESTAMP, 'failed')"
        )
        con.close()

        cb = CircuitBreaker(db_path)
        cb.check_indexer_health()
        cb.check_indexer_health()

        # Now flip to success
        con = duckdb.connect(db_path)
        con.execute("UPDATE indexer_state SET last_run_status = 'success' WHERE indexer_name = 'onchain_alchemy'")
        con.close()

        cb.check_indexer_health()
        assert cb._indexer_failures.get("onchain_alchemy", 0) == 0


class TestCircuitBreakerLLMCost:
    def test_high_cost_triggers_c3_kill(self, db_path):
        con = duckdb.connect(db_path)
        for i in range(3500):
            con.execute(
                "INSERT INTO resolution_risk_cache (condition_id, ambiguity_score, computed_at) "
                "VALUES (?, 0.5, CURRENT_TIMESTAMP)",
                [f"cond_{i}"],
            )
        con.close()

        cb = CircuitBreaker(db_path)
        cb.check_llm_cost()

        from polybot.orchestrator.kill_switches import is_component_enabled, _invalidate_cache
        _invalidate_cache()
        assert is_component_enabled(db_path, "c3") is False


class TestCircuitBreakerDisk:
    def test_high_disk_usage_logs_warning(self, db_path):
        mock_stat = MagicMock()
        mock_stat.f_blocks = 1000
        mock_stat.f_bavail = 100  # 90% used

        cb = CircuitBreaker(db_path)
        with patch("os.statvfs", return_value=mock_stat):
            cb.check_disk_usage()

        assert cb._disk_warning_sent is True
