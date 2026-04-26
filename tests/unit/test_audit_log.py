"""Tests for audit log module."""

import duckdb
import pytest

from polybot.orchestrator.audit_log import log_audit


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("CREATE SEQUENCE audit_log_seq START 1")
    con.execute("""
        CREATE TABLE audit_log (
            id BIGINT DEFAULT nextval('audit_log_seq') PRIMARY KEY,
            event_type VARCHAR,
            target VARCHAR,
            action VARCHAR,
            reason VARCHAR,
            actor VARCHAR DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.close()
    return path


class TestLogAudit:
    def test_inserts_event(self, db_path):
        log_audit(db_path, "kill_switch", "c1", "on", reason="maintenance", actor="manual")

        con = duckdb.connect(db_path)
        rows = con.execute("SELECT event_type, target, action, reason, actor FROM audit_log").fetchall()
        con.close()

        assert len(rows) == 1
        assert rows[0] == ("kill_switch", "c1", "on", "maintenance", "manual")

    def test_default_actor_is_system(self, db_path):
        log_audit(db_path, "rate_limit", "c2", "exceeded")

        con = duckdb.connect(db_path)
        row = con.execute("SELECT actor FROM audit_log").fetchone()
        con.close()

        assert row[0] == "system"

    def test_multiple_events_get_sequential_ids(self, db_path):
        log_audit(db_path, "kill_switch", "c1", "on")
        log_audit(db_path, "kill_switch", "c1", "off")

        con = duckdb.connect(db_path)
        ids = [r[0] for r in con.execute("SELECT id FROM audit_log ORDER BY id").fetchall()]
        con.close()

        assert ids == [1, 2]
