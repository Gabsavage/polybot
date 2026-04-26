"""Tests for kill switches module."""

import time
from unittest.mock import patch

import duckdb
import pytest

from polybot.orchestrator.kill_switches import (
    is_component_enabled,
    set_kill_switch,
    _invalidate_cache,
)


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
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
    con.close()
    _invalidate_cache()
    return path


class TestKillSwitchOnOff:
    def test_component_enabled_by_default(self, db_path):
        assert is_component_enabled(db_path, "c1") is True

    def test_activate_disables_component(self, db_path):
        set_kill_switch(db_path, "c1", enabled=True, reason="test")
        assert is_component_enabled(db_path, "c1") is False

    def test_deactivate_re_enables_component(self, db_path):
        set_kill_switch(db_path, "c1", enabled=True)
        set_kill_switch(db_path, "c1", enabled=False)
        assert is_component_enabled(db_path, "c1") is True


class TestKillSwitchAllAlerts:
    def test_all_alerts_disables_c1_and_c2(self, db_path):
        set_kill_switch(db_path, "all_alerts", enabled=True)
        assert is_component_enabled(db_path, "c1") is False
        assert is_component_enabled(db_path, "c2") is False

    def test_all_alerts_does_not_affect_indexers(self, db_path):
        set_kill_switch(db_path, "all_alerts", enabled=True)
        assert is_component_enabled(db_path, "trades") is True


class TestKillSwitchCache:
    def test_cache_avoids_repeated_db_reads(self, db_path):
        is_component_enabled(db_path, "c1")
        # Insert directly into DB — cache should NOT see it within TTL
        con = duckdb.connect(db_path)
        con.execute("INSERT INTO kill_switches (target, enabled) VALUES ('c1', TRUE)")
        con.close()
        # Within TTL, still returns True (cached)
        assert is_component_enabled(db_path, "c1") is True

    def test_cache_refreshes_after_ttl(self, db_path):
        is_component_enabled(db_path, "c1")
        con = duckdb.connect(db_path)
        con.execute("INSERT INTO kill_switches (target, enabled) VALUES ('c1', TRUE)")
        con.close()
        # Force cache expiry
        _invalidate_cache()
        assert is_component_enabled(db_path, "c1") is False


class TestKillSwitchAuditIntegration:
    def test_set_kill_switch_logs_to_audit(self, db_path):
        set_kill_switch(db_path, "c1", enabled=True, reason="maintenance", actor="manual")
        con = duckdb.connect(db_path)
        row = con.execute(
            "SELECT event_type, target, action, reason, actor FROM audit_log"
        ).fetchone()
        con.close()
        assert row == ("kill_switch", "c1", "on", "maintenance", "manual")
