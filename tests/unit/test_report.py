"""Tests for daily report generation — C1 + C2 + alert_outcomes."""

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
    component: str = "C1",
    condition_id: str = "cond1",
    price: float = 0.65,
    size_suggested: float = 20.0,
    score: int | None = None,
    alignment_score: int | None = None,
):
    con = duckdb.connect(db_path)
    con.execute(
        """INSERT INTO alerts (
            alert_id, component, emitted_at, wallet_address,
            condition_id, side, size_usd, price,
            size_suggested_usd, shadow_mode, score, alignment_score
        ) VALUES (?, ?, CURRENT_TIMESTAMP, '0xw1', ?, 'BUY', 2000, ?, ?, TRUE, ?, ?)""",
        [alert_id, component, condition_id, price, size_suggested, score, alignment_score],
    )
    con.close()


def _seed_outcome(
    db_path: str,
    alert_id: str,
    condition_id: str = "cond1",
    outcome: str = "YES",
    was_correct: bool = True,
    pnl: float = 10.0,
):
    con = duckdb.connect(db_path)
    con.execute(
        """INSERT OR REPLACE INTO alert_outcomes
        (alert_id, condition_id, resolution_outcome,
         was_direction_correct, shadow_pnl_simulated)
        VALUES (?, ?, ?, ?, ?)""",
        [alert_id, condition_id, outcome, was_correct, pnl],
    )
    con.close()


# --- Empty report ---


class TestReportEmpty:
    def test_no_alerts(self, db_path):
        report = generate_report(db_path, days=1)
        assert "Aucune alerte C1" in report
        assert "Aucune alerte C2" in report
        assert "Daily Report" in report

    def test_contains_system_section(self, db_path):
        report = generate_report(db_path, days=1)
        assert "Système" in report


# --- C1 section ---


class TestReportC1:
    def test_alert_stats(self, db_path):
        _seed_wallet(db_path)
        _seed_alert(db_path, "AL_001")
        _seed_alert(db_path, "AL_002")
        _seed_alert(db_path, "AL_003")

        report = generate_report(db_path, days=1)
        assert "<b>3</b>" in report
        assert "C1 Sharp Money" in report


# --- C2 section ---


class TestReportC2:
    def test_c2_stats(self, db_path):
        """3 C2 alerts with varying scores → avg displayed."""
        _seed_alert(db_path, "AL_C2_1", component="C2", score=4)
        _seed_alert(db_path, "AL_C2_2", component="C2", score=5)
        _seed_alert(db_path, "AL_C2_3", component="C2", score=6)

        report = generate_report(db_path, days=1)
        assert "C2 Informed Trading" in report
        assert "<b>3</b>" in report
        assert "5/7" in report  # avg of 4,5,6 = 5

    def test_c2_empty(self, db_path):
        report = generate_report(db_path, days=1)
        assert "Aucune alerte C2" in report


# --- Wallets ---


class TestReportWallets:
    def test_wallets_silent(self, db_path):
        _seed_wallet(db_path, "0xw1")
        _seed_wallet(db_path, "0xw2")
        _seed_wallet(db_path, "0xw3")
        _seed_trade(db_path, "tx1", "0xw1")

        report = generate_report(db_path, days=1)
        assert "2/3" in report  # 2 silent out of 3


# --- Shadow performance ---


class TestShadowPerformance:
    def test_shadow_with_outcomes(self, db_path):
        """2 correct + 1 incorrect → 67% win rate, positive P&L."""
        _seed_wallet(db_path)
        _seed_alert(db_path, "AL_S1", condition_id="c1")
        _seed_alert(db_path, "AL_S2", condition_id="c2")
        _seed_alert(db_path, "AL_S3", condition_id="c3")

        _seed_outcome(db_path, "AL_S1", "c1", "YES", True, 10.77)
        _seed_outcome(db_path, "AL_S2", "c2", "YES", True, 8.50)
        _seed_outcome(db_path, "AL_S3", "c3", "NO", False, -20.0)

        report = generate_report(db_path, days=1)
        assert "67%" in report  # 2/3
        assert "2/3" in report
        assert "trop tôt" in report  # < 30

    def test_shadow_no_resolved(self, db_path):
        _seed_wallet(db_path)
        _seed_alert(db_path, "AL_P1")
        _seed_outcome(db_path, "AL_P1", "cond1", "PENDING", False, 0)

        report = generate_report(db_path, days=1)
        assert "Aucune alerte résolue" in report

    def test_shadow_no_alerts(self, db_path):
        report = generate_report(db_path, days=1)
        assert "Aucune alerte (30j)" in report


# --- Alignment ---


class TestAlignment:
    def test_alignment_distribution(self, db_path):
        _seed_alert(db_path, "AL_A1", component="C2", alignment_score=1)
        _seed_alert(db_path, "AL_A2", component="C2", alignment_score=1)
        _seed_alert(db_path, "AL_A3", component="C2", alignment_score=-1)
        _seed_alert(db_path, "AL_A4", component="C2", alignment_score=0)

        report = generate_report(db_path, days=1)
        assert "Alignment C2" in report
        assert "suit mouvement" in report
        assert "contrariant" in report

    def test_alignment_hidden_when_empty(self, db_path):
        report = generate_report(db_path, days=1)
        assert "Alignment" not in report


# --- System ---


class TestReportSystem:
    def test_uptime_displayed(self, db_path):
        start = datetime.now(UTC) - timedelta(hours=18, minutes=32)
        report = generate_report(db_path, days=1, bot_start=start)
        assert "18h" in report

    def test_db_size_displayed(self, db_path):
        report = generate_report(db_path, days=1)
        assert "DB :" in report
        assert "MB" in report
