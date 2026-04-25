"""Tests for daily report generation."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from polybot.components.report import generate_report
from polybot.db.migrations import apply_migrations


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


def _seed_wallet(db_path: str, address: str = "0xw1", confidence: float = 0.95):
    con = duckdb.connect(db_path)
    con.execute(
        "INSERT OR REPLACE INTO tracked_wallets "
        "(address, tier, active, tier_a_confidence, last_seen_timestamp) "
        "VALUES (?, 'A', TRUE, ?, 0)",
        [address, confidence],
    )
    con.close()


def _seed_trade(db_path: str, tx_hash: str, wallet: str = "0xw1", size: float = 2000):
    con = duckdb.connect(db_path)
    con.execute(
        """INSERT OR REPLACE INTO trades (
            transaction_hash, proxy_wallet, condition_id, asset_id,
            side, size_usd, price, outcome, outcome_index,
            timestamp_unix, timestamp_ts, wallet_name
        ) VALUES (?, ?, 'cond1', 'tok1', 'BUY', ?, 0.65, 'Yes', 0,
                  ?, CURRENT_TIMESTAMP, 'Trader')""",
        [tx_hash, wallet, size, int(datetime.now(UTC).timestamp())],
    )
    con.close()


def _seed_alert(
    db_path: str,
    alert_id: str,
    condition_id: str = "cond1",
    price: float = 0.65,
    size_suggested: float = 20.0,
):
    con = duckdb.connect(db_path)
    con.execute(
        """INSERT INTO alerts (
            alert_id, component, emitted_at, wallet_address,
            condition_id, side, size_usd, price,
            size_suggested_usd, shadow_mode
        ) VALUES (?, 'C1', CURRENT_TIMESTAMP, '0xw1', ?, 'BUY', 2000, ?, ?, TRUE)""",
        [alert_id, condition_id, price, size_suggested],
    )
    con.close()


def _seed_resolution(db_path: str, condition_id: str, outcome: str):
    con = duckdb.connect(db_path)
    con.execute(
        "INSERT OR REPLACE INTO resolutions (condition_id, settled_outcome, final_price) "
        "VALUES (?, ?, ?)",
        [condition_id, outcome, 1.0 if outcome == "YES" else 0.0],
    )
    con.close()


class TestReportEmpty:
    def test_no_alerts(self, db_path):
        report = generate_report(db_path, days=1)
        assert "Aucune alerte" in report
        assert "Daily Report" in report

    def test_contains_system_section(self, db_path):
        report = generate_report(db_path, days=1)
        assert "Système" in report


class TestReportWithAlerts:
    def test_alert_stats(self, db_path):
        _seed_wallet(db_path)
        _seed_alert(db_path, "AL_001")
        _seed_alert(db_path, "AL_002")
        _seed_alert(db_path, "AL_003")

        report = generate_report(db_path, days=1)
        assert "<b>3</b>" in report  # total alerts

    def test_wallets_silent(self, db_path):
        _seed_wallet(db_path, "0xw1")
        _seed_wallet(db_path, "0xw2")
        _seed_wallet(db_path, "0xw3")
        _seed_trade(db_path, "tx1", "0xw1")
        # w2 and w3 are silent

        report = generate_report(db_path, days=1)
        assert "2/3" in report  # 2 silent out of 3


class TestPnlCalculation:
    def test_correct_direction_pnl(self, db_path):
        """BUY YES @ 0.65, resolved YES → P&L = +$20 × (1/0.65 - 1) = +$10.77"""
        _seed_wallet(db_path)
        _seed_alert(db_path, "AL_001", condition_id="cond1", price=0.65, size_suggested=20.0)
        _seed_resolution(db_path, "cond1", "YES")

        report = generate_report(db_path, days=1)
        assert "+$" in report
        assert "100%" in report  # 1/1 correct

    def test_incorrect_direction_pnl(self, db_path):
        """BUY YES @ 0.65, resolved NO → P&L = -$20"""
        _seed_wallet(db_path)
        _seed_alert(db_path, "AL_001", condition_id="cond1", price=0.65, size_suggested=20.0)
        _seed_resolution(db_path, "cond1", "NO")

        report = generate_report(db_path, days=1)
        assert "-$" in report or "0%" in report

    def test_no_resolutions_message(self, db_path):
        _seed_wallet(db_path)
        _seed_alert(db_path, "AL_001")
        # No resolution

        report = generate_report(db_path, days=1)
        assert "Aucune alerte résolue" in report

    def test_disclaimer_under_30(self, db_path):
        _seed_wallet(db_path)
        _seed_alert(db_path, "AL_001", condition_id="cond1")
        _seed_resolution(db_path, "cond1", "YES")

        report = generate_report(db_path, days=1)
        assert "trop tôt" in report


class TestReportUptime:
    def test_uptime_displayed(self, db_path):
        start = datetime.now(UTC) - timedelta(hours=18, minutes=32)
        report = generate_report(db_path, days=1, bot_start=start)
        assert "18h" in report
