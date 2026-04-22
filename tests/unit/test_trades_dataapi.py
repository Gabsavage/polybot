"""Tests for indexer_trades_dataapi."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import duckdb
import httpx
import pytest

from polybot.db.migrations import apply_migrations
from polybot.indexers.trades_dataapi import (
    fetch_wallet_trades,
    filter_new_trades,
    insert_trades,
    map_trade,
    poll_once,
    update_wallet_cursor,
)

_FAKE_REQUEST = httpx.Request("GET", "https://data-api.polymarket.com/trades")


def _make_trade(tx_hash: str, timestamp: int = 1000, **overrides) -> dict:
    """Build a minimal Data API trade dict."""
    base = {
        "transactionHash": tx_hash,
        "proxyWallet": "0xaaaa",
        "conditionId": "cond_1",
        "asset": "token_yes",
        "side": "BUY",
        "size": 500.0,
        "price": 0.65,
        "outcome": "Yes",
        "outcomeIndex": 0,
        "timestamp": timestamp,
        "title": "Will X happen?",
        "slug": "will-x-happen",
        "eventSlug": "event-x",
        "name": "TestTrader",
    }
    base.update(overrides)
    return base


def _seed_wallet(db_path: str, address: str = "0xaaaa", last_seen: int = 0):
    con = duckdb.connect(db_path)
    con.execute(
        "INSERT OR REPLACE INTO tracked_wallets "
        "(address, tier, active, last_seen_timestamp) "
        "VALUES (?, 'A', true, ?)",
        [address, last_seen],
    )
    con.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


class TestDedup:
    def test_duplicate_hash_not_inserted_twice(self, db_path: str):
        trade = _make_trade("0xhash1", timestamp=2000)
        count1 = insert_trades(db_path, [trade])
        count2 = insert_trades(db_path, [trade])
        assert count1 == 1
        assert count2 == 0

        con = duckdb.connect(db_path, read_only=True)
        total = con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        con.close()
        assert total == 1


class TestTimestampFilter:
    def test_filters_by_last_seen(self):
        trades = [
            _make_trade("tx1", timestamp=500),
            _make_trade("tx2", timestamp=1000),
            _make_trade("tx3", timestamp=1500),
            _make_trade("tx4", timestamp=2000),
            _make_trade("tx5", timestamp=2500),
        ]
        new = filter_new_trades(trades, last_seen_ts=1000)
        assert len(new) == 3
        hashes = {t["transactionHash"] for t in new}
        assert hashes == {"tx3", "tx4", "tx5"}

    def test_all_old_returns_empty(self):
        trades = [_make_trade("tx1", timestamp=500)]
        assert filter_new_trades(trades, last_seen_ts=1000) == []


class TestMapping:
    def test_map_trade_all_fields(self, db_path: str):
        trade = _make_trade("0xfull", timestamp=1700000000, size=1234.56, price=0.75)
        row = map_trade(trade)

        assert row[0] == "0xfull"  # transaction_hash
        assert row[1] == "0xaaaa"  # proxy_wallet
        assert row[2] == "cond_1"  # condition_id
        assert row[3] == "token_yes"  # asset_id
        assert row[4] == "BUY"  # side
        assert row[5] == 1234.56  # size_usd
        assert row[6] == 0.75  # price
        assert row[7] == "Yes"  # outcome
        assert row[8] == 0  # outcome_index
        assert row[9] == 1700000000  # timestamp_unix
        assert row[10].year == 2023  # timestamp_ts
        assert row[11] == "Will X happen?"  # market_title
        assert row[14] == "TestTrader"  # wallet_name

    def test_insert_populates_all_columns(self, db_path: str):
        trade = _make_trade("0xcheck", timestamp=1700000000)
        insert_trades(db_path, [trade])

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT transaction_hash, proxy_wallet, condition_id, asset_id, "
            "side, size_usd, price, outcome, outcome_index, "
            "timestamp_unix, market_title, wallet_name "
            "FROM trades WHERE transaction_hash = '0xcheck'"
        ).fetchone()
        con.close()

        assert row[0] == "0xcheck"
        assert row[1] == "0xaaaa"
        assert row[4] == "BUY"
        assert float(row[5]) == 500.0
        assert float(row[6]) == 0.65
        assert row[11] == "TestTrader"


class TestWalletCursor:
    def test_cursor_updates_to_max_timestamp(self, db_path: str):
        _seed_wallet(db_path, "0xaaaa", last_seen=0)

        trades = [
            _make_trade("tx1", timestamp=1000),
            _make_trade("tx2", timestamp=3000),
            _make_trade("tx3", timestamp=2000),
        ]
        insert_trades(db_path, trades)
        max_ts = max(int(t["timestamp"]) for t in trades)
        update_wallet_cursor(db_path, "0xaaaa", max_ts)

        con = duckdb.connect(db_path, read_only=True)
        cursor = con.execute(
            "SELECT last_seen_timestamp FROM tracked_wallets WHERE address = '0xaaaa'"
        ).fetchone()[0]
        con.close()
        assert cursor == 3000


class TestBackoff429:
    def test_retries_then_succeeds(self):
        trades = [_make_trade("tx1")]
        responses = [
            httpx.Response(429, request=_FAKE_REQUEST),
            httpx.Response(429, request=_FAKE_REQUEST),
            httpx.Response(200, json=trades, request=_FAKE_REQUEST),
        ]
        call_idx = 0

        async def mock_get(url, **kwargs):
            nonlocal call_idx
            resp = responses[call_idx]
            call_idx += 1
            return resp

        async def run():
            client = AsyncMock()
            client.get = mock_get
            with patch("polybot.indexers.trades_dataapi.asyncio.sleep"):
                result = await fetch_wallet_trades(client, "0xaaaa")
            return result

        result = asyncio.new_event_loop().run_until_complete(run())
        assert len(result) == 1
        assert result[0]["transactionHash"] == "tx1"


class TestWalletIsolation:
    def test_error_one_wallet_doesnt_affect_other(self, db_path: str):
        _seed_wallet(db_path, "0xfail_wallet", last_seen=0)
        _seed_wallet(db_path, "0xgood_wallet", last_seen=0)

        good_trades = [
            _make_trade("txgood", timestamp=5000, proxyWallet="0xgood_wallet")
        ]

        async def mock_get(url, **kwargs):
            address = kwargs.get("params", {}).get("user", "")
            if address == "0xfail_wallet":
                raise httpx.ConnectError("connection refused")
            return httpx.Response(200, json=good_trades, request=_FAKE_REQUEST)

        async def run():
            client = AsyncMock()
            client.get = mock_get
            count = await poll_once(db_path, client)
            return count

        count = asyncio.new_event_loop().run_until_complete(run())
        assert count == 1

        con = duckdb.connect(db_path, read_only=True)
        total = con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        con.close()
        assert total == 1


class TestEmptyWallet:
    def test_no_trades_no_crash(self, db_path: str):
        _seed_wallet(db_path, "0xempty", last_seen=0)

        async def run():
            client = AsyncMock()
            client.get = AsyncMock(
                return_value=httpx.Response(200, json=[], request=_FAKE_REQUEST)
            )
            count = await poll_once(db_path, client)
            return count

        count = asyncio.new_event_loop().run_until_complete(run())
        assert count == 0

        con = duckdb.connect(db_path, read_only=True)
        cursor = con.execute(
            "SELECT last_seen_timestamp FROM tracked_wallets WHERE address = '0xempty'"
        ).fetchone()[0]
        con.close()
        assert cursor == 0
