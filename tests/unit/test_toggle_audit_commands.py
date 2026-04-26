"""Tests for /toggle and /audit bot commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import duckdb
import pytest

from polybot.orchestrator.kill_switches import _invalidate_cache


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("""
        CREATE TABLE kill_switches (
            target VARCHAR PRIMARY KEY, enabled BOOLEAN DEFAULT FALSE,
            reason VARCHAR, toggled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
        CREATE TABLE alerts (
            alert_id VARCHAR PRIMARY KEY,
            component VARCHAR,
            emitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            condition_id VARCHAR,
            side VARCHAR,
            size_usd DECIMAL(18,2),
            price DECIMAL(6,4),
            size_suggested_usd DECIMAL(18,2),
            alignment_score INTEGER,
            score INTEGER
        )
    """)
    con.close()
    _invalidate_cache()
    return path


def _make_update_context(args):
    update = MagicMock()
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = args
    return update, context


class TestToggleCommand:
    @pytest.mark.asyncio
    async def test_toggle_c1_off(self, db_path):
        from polybot.telegram.bot import PolyBot

        with patch.object(PolyBot, "__init__", lambda self, s: None):
            bot = PolyBot.__new__(PolyBot)
            bot.settings = MagicMock()
            bot.db_path = db_path
            bot.send_alert = AsyncMock()

        update, context = _make_update_context(["c1", "off", "test", "reason"])
        await bot._cmd_toggle(update, context)

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "c1" in reply.lower()

        from polybot.orchestrator.kill_switches import is_component_enabled
        _invalidate_cache()
        assert is_component_enabled(db_path, "c1") is False


class TestAuditCommand:
    @pytest.mark.asyncio
    async def test_audit_shows_events(self, db_path):
        from polybot.orchestrator.audit_log import log_audit
        log_audit(db_path, "kill_switch", "c1", "on", reason="test", actor="manual")
        log_audit(db_path, "rate_limit", "c2", "exceeded", actor="system")

        from polybot.telegram.bot import PolyBot

        with patch.object(PolyBot, "__init__", lambda self, s: None):
            bot = PolyBot.__new__(PolyBot)
            bot.db_path = db_path
            bot.settings = MagicMock()

        update, context = _make_update_context([])
        await bot._cmd_audit(update, context)

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "c1" in reply
        assert "c2" in reply


class TestWeeklyCommand:
    @pytest.mark.asyncio
    async def test_weekly_returns_report(self, db_path):
        from polybot.telegram.bot import PolyBot

        with patch.object(PolyBot, "__init__", lambda self, s: None):
            bot = PolyBot.__new__(PolyBot)
            bot.db_path = db_path
            bot.settings = MagicMock()

        update, context = _make_update_context([])
        await bot._cmd_weekly(update, context)

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "Weekly Report" in reply or "Aucune alerte" in reply
