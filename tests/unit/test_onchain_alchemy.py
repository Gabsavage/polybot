"""Tests for indexer_onchain_alchemy."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import httpx
import pytest

from polybot.db.migrations import apply_migrations
from polybot.indexers.onchain_alchemy import (
    CTF_EXCHANGE,
    NEG_RISK_EXCHANGE,
    ORDER_FILLED_TOPIC,
    get_last_scanned_block,
    insert_trades,
    parse_order_filled,
    run,
    update_indexer_state,
)


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


def _make_order_filled_event(
    maker: str = "0x" + "aa" * 20,
    taker: str = "0x" + "bb" * 20,
    maker_asset_id: int = 0,  # USDC
    taker_asset_id: int = 12345678901234567890,
    maker_amount: int = 5_000_000,  # $5 USDC
    taker_amount: int = 10_000_000,  # 10 tokens
    fee: int = 50_000,
    block_number: int = 85_000_000,
    log_index: int = 1,
    tx_hash: str = "0x" + "ff" * 32,
) -> dict:
    """Build a mock OrderFilled event log."""
    data = "0x"
    data += f"{maker_asset_id:064x}"
    data += f"{taker_asset_id:064x}"
    data += f"{maker_amount:064x}"
    data += f"{taker_amount:064x}"
    data += f"{fee:064x}"

    return {
        "topics": [
            ORDER_FILLED_TOPIC,
            "0x" + "cc" * 32,  # orderHash
            "0x" + maker[2:].rjust(64, "0"),
            "0x" + taker[2:].rjust(64, "0"),
        ],
        "data": data,
        "blockNumber": hex(block_number),
        "logIndex": hex(log_index),
        "transactionHash": tx_hash,
    }


class TestEventParsing:
    def test_parse_sell_event(self):
        """Maker pays USDC (assetId=0) → taker SELLS tokens."""
        event = _make_order_filled_event(
            maker_asset_id=0,
            taker_asset_id=99999,
            maker_amount=5_000_000,
            taker_amount=10_000_000,
        )
        parsed = parse_order_filled(event)
        assert parsed is not None
        assert parsed["side"] == "SELL"
        assert parsed["size_usd"] == 5.0
        assert parsed["price"] == 0.5
        assert parsed["condition_id"] == "99999"
        assert parsed["proxy_wallet"] == ("0x" + "bb" * 20).lower()

    def test_parse_buy_event(self):
        """Taker pays USDC (assetId=0) → taker BUYS tokens."""
        event = _make_order_filled_event(
            maker_asset_id=99999,
            taker_asset_id=0,
            maker_amount=10_000_000,
            taker_amount=7_000_000,
        )
        parsed = parse_order_filled(event)
        assert parsed is not None
        assert parsed["side"] == "BUY"
        assert parsed["size_usd"] == 7.0
        assert parsed["price"] == 0.7

    def test_parse_neither_usdc_returns_none(self):
        """Both sides are tokens → skip."""
        event = _make_order_filled_event(
            maker_asset_id=111, taker_asset_id=222
        )
        parsed = parse_order_filled(event)
        assert parsed is None

    def test_filter_exchange_as_taker(self):
        """Events where taker = CTFExchange are internal routing → skip."""
        event = _make_order_filled_event(taker=CTF_EXCHANGE)
        parsed = parse_order_filled(event)
        assert parsed is None

    def test_filter_neg_risk_exchange_as_taker(self):
        event = _make_order_filled_event(taker=NEG_RISK_EXCHANGE)
        parsed = parse_order_filled(event)
        assert parsed is None

    def test_parse_short_data_returns_none(self):
        event = _make_order_filled_event()
        event["data"] = "0x1234"
        parsed = parse_order_filled(event)
        assert parsed is None

    def test_parse_missing_topics_returns_none(self):
        event = {"topics": [ORDER_FILLED_TOPIC], "data": "0x" + "0" * 320,
                 "blockNumber": "0x1", "logIndex": "0x0",
                 "transactionHash": "0x" + "aa" * 32}
        parsed = parse_order_filled(event)
        assert parsed is None

    def test_tx_hash_log_idx_format(self):
        tx = "0xdeadbeef" + "00" * 28
        event = _make_order_filled_event(tx_hash=tx, log_index=42)
        parsed = parse_order_filled(event)
        assert parsed["tx_hash_log_idx"] == f"{tx}_42"
        assert parsed["log_index"] == 42

    def test_price_calculation(self):
        """$6.50 USDC for 10 tokens → price 0.65."""
        event = _make_order_filled_event(
            maker_asset_id=0,
            maker_amount=6_500_000,
            taker_amount=10_000_000,
        )
        parsed = parse_order_filled(event)
        assert parsed["price"] == 0.65


class TestInsertTrades:
    def test_insert_new_trade(self, db_path: str):
        trade = {
            "tx_hash_log_idx": "0xabc_1",
            "transaction_hash": "0xabc",
            "log_index": 1,
            "proxy_wallet": "0xwallet",
            "condition_id": "12345",
            "side": "BUY",
            "size_usd": 100.0,
            "price": 0.65,
            "timestamp_ts": None,
        }
        count = insert_trades(db_path, [trade])
        assert count == 1

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT tx_hash_log_idx, side, size_usd FROM trades_all"
        ).fetchone()
        con.close()
        assert row[0] == "0xabc_1"
        assert row[1] == "BUY"
        assert float(row[2]) == 100.0

    def test_dedup_same_tx_log_idx(self, db_path: str):
        trade = {
            "tx_hash_log_idx": "0xabc_1",
            "transaction_hash": "0xabc",
            "log_index": 1,
            "proxy_wallet": "0xwallet",
            "condition_id": "12345",
            "side": "BUY",
            "size_usd": 100.0,
            "price": 0.65,
            "timestamp_ts": None,
        }
        count1 = insert_trades(db_path, [trade])
        count2 = insert_trades(db_path, [trade])
        assert count1 == 1
        assert count2 == 0

    def test_multiple_events_same_tx(self, db_path: str):
        """Multiple OrderFilled events from same tx → all inserted."""
        trades = [
            {
                "tx_hash_log_idx": "0xabc_1",
                "transaction_hash": "0xabc",
                "log_index": 1,
                "proxy_wallet": "0xw1",
                "condition_id": "111",
                "side": "BUY",
                "size_usd": 50.0,
                "price": 0.5,
                "timestamp_ts": None,
            },
            {
                "tx_hash_log_idx": "0xabc_2",
                "transaction_hash": "0xabc",
                "log_index": 2,
                "proxy_wallet": "0xw2",
                "condition_id": "222",
                "side": "SELL",
                "size_usd": 75.0,
                "price": 0.75,
                "timestamp_ts": None,
            },
        ]
        count = insert_trades(db_path, trades)
        assert count == 2

    def test_empty_list(self, db_path: str):
        assert insert_trades(db_path, []) == 0


class TestIncrementalMode:
    def test_resumes_from_last_cursor(self, db_path: str):
        con = duckdb.connect(db_path)
        con.execute(
            """
            INSERT INTO indexer_state
                (indexer_name, last_synced_at, last_cursor,
                 last_run_status, last_run_duration_ms, ingested_count)
            VALUES ('onchain_alchemy', NOW(), '85000000',
                    'success', 100, 0)
            """
        )
        con.close()
        assert get_last_scanned_block(db_path) == 85_000_000

    def test_returns_none_when_no_state(self, db_path: str):
        assert get_last_scanned_block(db_path) is None


class TestUpdateIndexerState:
    def test_writes_state(self, db_path: str):
        update_indexer_state(db_path, 85_500_000, "success", 1234, 5000)

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT last_cursor, last_run_status, ingested_count "
            "FROM indexer_state WHERE indexer_name = 'onchain_alchemy'"
        ).fetchone()
        con.close()
        assert row[0] == "85500000"
        assert row[1] == "success"
        assert row[2] == 1234


class TestRunIntegration:
    def test_run_with_mocked_rpc(self, db_path: str):
        """End-to-end: 1 batch, 2 events (1 real + 1 filtered exchange taker)."""
        head = 85_130_001
        block_resp = {"jsonrpc": "2.0", "result": hex(head), "id": 1}

        real_event = _make_order_filled_event(
            taker="0x" + "bb" * 20,
            block_number=85_130_000,
            log_index=5,
            tx_hash="0x" + "dd" * 32,
        )
        exchange_event = _make_order_filled_event(
            taker=CTF_EXCHANGE,
            block_number=85_130_000,
            log_index=6,
            tx_hash="0x" + "dd" * 32,
        )
        logs_resp = {
            "jsonrpc": "2.0",
            "result": [real_event, exchange_event],
            "id": 1,
        }
        logs_empty = {"jsonrpc": "2.0", "result": [], "id": 1}
        block_ts = {
            "jsonrpc": "2.0",
            "result": {"timestamp": hex(1700000000)},
            "id": 1,
        }

        call_log: list[str] = []

        def mock_post(url, **kwargs):
            body = kwargs.get("json", {})
            method = body.get("method", "")
            call_log.append(method)
            if method == "eth_blockNumber":
                return httpx.Response(
                    200, json=block_resp,
                    request=httpx.Request("POST", url),
                )
            if method == "eth_getLogs":
                # First call returns events, subsequent empty
                resp = logs_resp if call_log.count("eth_getLogs") == 1 else logs_empty
                return httpx.Response(
                    200, json=resp,
                    request=httpx.Request("POST", url),
                )
            if method == "eth_getBlockByNumber":
                return httpx.Response(
                    200, json=block_ts,
                    request=httpx.Request("POST", url),
                )
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "result": [], "id": 1},
                request=httpx.Request("POST", url),
            )

        with (
            patch("polybot.indexers.onchain_alchemy.httpx.Client") as mock_cls,
            patch("polybot.indexers.onchain_alchemy.time.sleep"),
        ):
            mock_client = MagicMock()
            mock_client.post.side_effect = mock_post
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_cls.return_value = mock_client

            count = run(db_path, "http://test-alchemy")

        # Only 1 trade inserted (exchange taker filtered out)
        assert count == 1

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT tx_hash_log_idx, side, source FROM trades_all"
        ).fetchone()
        con.close()
        assert "_5" in row[0]  # log_index 5
        assert row[1] == "SELL"
        assert row[2] == "alchemy"
