"""Tests for C1 Sharp Money + sizing + alert formatting."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import duckdb
import pytest

from polybot.components.c1_sharp_money import (
    SharpMoneyDetector,
    _dedup_hash,
    _format_alert,
    _next_alert_id,
)
from polybot.components.sizing import compute_size
from polybot.config import Settings
from polybot.db.migrations import apply_migrations


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        R2_ACCESS_KEY_ID="test",
        R2_SECRET_ACCESS_KEY="test",
        R2_ENDPOINT="https://test.r2.cloudflarestorage.com",
        TELEGRAM_BOT_TOKEN="fake:token",
        TELEGRAM_CHAT_ID=-1001234,
        TELEGRAM_TOPIC_OPS=123,
    )


def _seed_wallet(db_path: str, address: str = "0xwallet1", confidence: float = 0.95):
    con = duckdb.connect(db_path)
    con.execute(
        "INSERT OR REPLACE INTO tracked_wallets "
        "(address, tier, active, tier_a_confidence, last_seen_timestamp) "
        "VALUES (?, 'A', TRUE, ?, 0)",
        [address, confidence],
    )
    con.close()


def _seed_bankroll(db_path: str, amount: float = 2000.0, days_ago: int = 0):
    con = duckdb.connect(db_path)
    ts = datetime.now(UTC) - timedelta(days=days_ago)
    con.execute(
        "INSERT OR REPLACE INTO bankroll_state (id, amount, updated_at) VALUES (1, ?, ?)",
        [amount, ts],
    )
    con.close()


def _seed_market(db_path: str, condition_id: str = "cond1", liquidity: float = 5000.0):
    con = duckdb.connect(db_path)
    con.execute(
        "INSERT OR REPLACE INTO markets (condition_id, liquidity_usd, status) "
        "VALUES (?, ?, 'active')",
        [condition_id, liquidity],
    )
    con.close()


def _insert_trade(
    db_path: str,
    tx_hash: str = "0xtx1",
    wallet: str = "0xwallet1",
    condition_id: str = "cond1",
    side: str = "BUY",
    size_usd: float = 2000.0,
    price: float = 0.65,
    ts: datetime | None = None,
):
    if ts is None:
        ts = datetime.now(UTC)
    con = duckdb.connect(db_path)
    con.execute(
        """INSERT OR REPLACE INTO trades (
            transaction_hash, proxy_wallet, condition_id, asset_id,
            side, size_usd, price, outcome, outcome_index,
            timestamp_unix, timestamp_ts, market_title, market_slug,
            event_slug, wallet_name
        ) VALUES (?, ?, ?, 'token1', ?, ?, ?, 'Yes', 0, ?, ?, 'Test Market',
                  'test-market', 'test-event', 'SharpTrader')""",
        [tx_hash, wallet, condition_id, side, size_usd, price,
         int(ts.timestamp()), ts],
    )
    con.close()


# --- Sizing tests ---


class TestSizing:
    def test_a1_sizing(self, settings):
        size = compute_size(2000.0, 0.95, settings)
        assert size == 20.0  # 2000 * 0.25 * 0.04 * 1.0

    def test_a2_sizing(self, settings):
        # 2000 * 0.25 * 0.02 * 0.6 = $6 < $10 min → None
        assert compute_size(2000.0, 0.80, settings) is None
        # With larger bankroll: 10000 * 0.25 * 0.02 * 0.6 = $30
        size = compute_size(10_000.0, 0.80, settings)
        assert size == 30.0

    def test_below_minimum_returns_none(self, settings):
        size = compute_size(100.0, 0.95, settings)
        # 100 * 0.25 * 0.04 * 1.0 = 1.0 < 10 min
        assert size is None

    def test_capped_at_max_pct(self, settings):
        # bankroll $200, A1: 200*0.25*0.04*1.0 = $2. Cap = 200*0.05 = $10
        # $2 < $10 min → None
        size = compute_size(200.0, 0.95, settings)
        assert size is None

    def test_large_bankroll(self, settings):
        size = compute_size(100_000.0, 0.95, settings)
        # 100000 * 0.25 * 0.04 * 1.0 = 1000
        # Cap: 100000 * 0.05 = 5000, so not capped
        assert size == 1000.0


# --- Filter tests ---


class TestFilterSize:
    def test_below_minimum_no_alert(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_bankroll(db_path)
        _seed_market(db_path)
        _insert_trade(db_path, size_usd=500.0)  # Below $1000

        bot = MagicMock()
        c1 = SharpMoneyDetector(bot=bot, settings=settings)
        c1.db_path = db_path
        c1.last_check_ts = datetime.now(UTC) - timedelta(minutes=5)

        import asyncio
        count = asyncio.new_event_loop().run_until_complete(c1.poll_once())
        assert count == 0

    def test_above_minimum_triggers(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_bankroll(db_path)
        _seed_market(db_path)
        _insert_trade(db_path, size_usd=1500.0)

        bot = MagicMock()
        bot.send_alert = AsyncMock(return_value=999)
        c1 = SharpMoneyDetector(bot=bot, settings=settings)
        c1.db_path = db_path
        c1.last_check_ts = datetime.now(UTC) - timedelta(minutes=5)

        import asyncio
        count = asyncio.new_event_loop().run_until_complete(c1.poll_once())
        assert count == 1
        bot.send_alert.assert_called_once()


class TestFilterBuyOnly:
    def test_sell_filtered(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_bankroll(db_path)
        _seed_market(db_path)
        _insert_trade(db_path, side="SELL", size_usd=5000.0)

        bot = MagicMock()
        c1 = SharpMoneyDetector(bot=bot, settings=settings)
        c1.db_path = db_path
        c1.last_check_ts = datetime.now(UTC) - timedelta(minutes=5)

        import asyncio
        count = asyncio.new_event_loop().run_until_complete(c1.poll_once())
        assert count == 0


class TestFilterRateLimit:
    def test_rate_limited(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_bankroll(db_path)
        _seed_market(db_path)

        # Insert an existing alert for same wallet+market within 3h
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO alerts (alert_id, component, wallet_address, "
            "condition_id, emitted_at, side, size_usd, price, "
            "size_suggested_usd, shadow_mode) "
            "VALUES ('AL_20260424_0001', 'C1', '0xwallet1', 'cond1', "
            "CURRENT_TIMESTAMP, 'BUY', 1000, 0.65, 20, TRUE)"
        )
        con.close()

        _insert_trade(db_path, tx_hash="0xtx2", size_usd=2000.0)

        bot = MagicMock()
        c1 = SharpMoneyDetector(bot=bot, settings=settings)
        c1.db_path = db_path
        c1.last_check_ts = datetime.now(UTC) - timedelta(minutes=5)

        import asyncio
        count = asyncio.new_event_loop().run_until_complete(c1.poll_once())
        assert count == 0


class TestFilterLiquidity:
    def test_illiquid_market_blocked(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_bankroll(db_path)
        _seed_market(db_path, liquidity=300.0)  # Below $500
        _insert_trade(db_path, size_usd=2000.0)

        bot = MagicMock()
        c1 = SharpMoneyDetector(bot=bot, settings=settings)
        c1.db_path = db_path
        c1.last_check_ts = datetime.now(UTC) - timedelta(minutes=5)

        import asyncio
        count = asyncio.new_event_loop().run_until_complete(c1.poll_once())
        assert count == 0


# --- Alert ID ---


class TestAlertId:
    def test_sequential_ids(self, db_path):
        con = duckdb.connect(db_path)
        id1 = _next_alert_id(con)
        con.execute(
            "INSERT INTO alerts (alert_id, component, shadow_mode) "
            "VALUES (?, 'C1', TRUE)", [id1]
        )
        id2 = _next_alert_id(con)
        con.close()

        assert id1.endswith("_0001")
        assert id2.endswith("_0002")


# --- Dedup hash ---


class TestDedupHash:
    def test_same_bucket_same_hash(self):
        h1 = _dedup_hash("w", "c", "BUY", 1000, 300)
        h2 = _dedup_hash("w", "c", "BUY", 1100, 300)  # same 300s bucket
        assert h1 == h2

    def test_different_bucket_different_hash(self):
        h1 = _dedup_hash("w", "c", "BUY", 1000, 300)
        h2 = _dedup_hash("w", "c", "BUY", 1500, 300)  # different bucket
        assert h1 != h2


# --- Format ---


class TestAlertFormat:
    def test_contains_all_fields(self):
        msg = _format_alert(
            wallet_name="SharpTrader",
            tier_label="A1",
            market_title="Will X happen?",
            outcome="Yes",
            price=0.65,
            size_usd=2000.0,
            size_suggested=20.0,
            bankroll=2000.0,
            alert_id="AL_20260424_0001",
            tags=[],
        )
        assert "C1 Sharp Money" in msg
        assert "SharpTrader" in msg
        assert "Tier A1" in msg
        assert "Will X happen?" in msg
        assert "BUY Yes" in msg
        assert "$20" in msg
        assert "AL_20260424_0001" in msg

    def test_low_liquidity_tag(self):
        msg = _format_alert(
            wallet_name="W", tier_label="A1", market_title="M",
            outcome="Yes", price=0.5, size_usd=1000, size_suggested=100,
            bankroll=2000, alert_id="AL_TEST",
            tags=["⚠️ low_liquidity"],
        )
        assert "low_liquidity" in msg


# --- Bankroll ---


class TestBankroll:
    def test_bankroll_stale_tag(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_bankroll(db_path, days_ago=20)
        _seed_market(db_path)
        _insert_trade(db_path, size_usd=2000.0)

        bot = MagicMock()
        bot.send_alert = AsyncMock(return_value=999)
        c1 = SharpMoneyDetector(bot=bot, settings=settings)
        c1.db_path = db_path
        c1.last_check_ts = datetime.now(UTC) - timedelta(minutes=5)

        import asyncio
        asyncio.new_event_loop().run_until_complete(c1.poll_once())

        # Check alert was stored with bankroll_stale tag
        con = duckdb.connect(db_path, read_only=True)
        row = con.execute("SELECT tags FROM alerts LIMIT 1").fetchone()
        con.close()
        assert row and "bankroll_stale" in (row[0] or "")
