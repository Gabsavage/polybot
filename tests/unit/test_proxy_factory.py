"""Tests for indexer_proxy_factory."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import httpx
import pytest

from polybot.db.migrations import apply_migrations
from polybot.indexers.proxy_factory import (
    GNOSIS_SAFE_FACTORY,
    POLYMARKET_FACTORY,
    PROXY_CREATION_TOPIC,
    LogResponseTooLarge,
    RPCError,
    get_last_scanned_block,
    get_tx_sender,
    insert_mappings,
    parse_proxy_from_event,
    process_events,
    rpc_call,
    run,
    update_indexer_state,
)


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


def _make_event(
    proxy_hex: str = "ed9bec5dd51856fd4e6d351701db77967ac8534e",
    singleton_hex: str = "3e5c63644e683549055b9be8653de26e0b4cd36e",
    block_number: int = 50_000_000,
    tx_hash: str = "0xabc123",
) -> dict:
    """Build a mock ProxyCreation event log."""
    data = (
        "0x"
        + proxy_hex.rjust(64, "0")
        + singleton_hex.rjust(64, "0")
    )
    return {
        "topics": [PROXY_CREATION_TOPIC],
        "data": data,
        "blockNumber": hex(block_number),
        "transactionHash": tx_hash,
        "logIndex": "0x1",
    }


class TestEventParsing:
    def test_parse_proxy_from_event(self):
        event = _make_event(proxy_hex="ed9bec5dd51856fd4e6d351701db77967ac8534e")
        proxy = parse_proxy_from_event(event)
        assert proxy == "0xed9bec5dd51856fd4e6d351701db77967ac8534e"

    def test_parse_proxy_short_data_raises(self):
        event = {"data": "0x1234"}
        with pytest.raises(ValueError, match="too short"):
            parse_proxy_from_event(event)

    def test_parse_proxy_different_address(self):
        event = _make_event(proxy_hex="1111111111111111111111111111111111111111")
        proxy = parse_proxy_from_event(event)
        assert proxy == "0x1111111111111111111111111111111111111111"


class TestEOAExtraction:
    def test_get_tx_sender(self):
        client = MagicMock()
        client.post.return_value = httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "result": {
                    "from": "0xaaaa",
                    "to": GNOSIS_SAFE_FACTORY,
                    "hash": "0xabc",
                },
                "id": 1,
            },
            request=httpx.Request("POST", "http://test"),
        )
        sender = get_tx_sender(client, "http://test", "0xabc")
        assert sender == "0xaaaa"

    def test_get_tx_sender_missing_tx_raises(self):
        client = MagicMock()
        client.post.return_value = httpx.Response(
            200,
            json={"jsonrpc": "2.0", "result": None, "id": 1},
            request=httpx.Request("POST", "http://test"),
        )
        with pytest.raises(RPCError, match="No tx found"):
            get_tx_sender(client, "http://test", "0xmissing")


class TestInsertIdempotent:
    def test_duplicate_proxy_not_inserted_twice(self, db_path: str):
        mapping = {
            "proxy_address": "0xproxy1",
            "eoa_address": "0xeoa1",
            "confidence": 0.8,
            "first_seen_block": 50_000_000,
            "first_seen_ts": None,
            "factory_contract": GNOSIS_SAFE_FACTORY,
        }
        count1 = insert_mappings(db_path, [mapping])
        count2 = insert_mappings(db_path, [mapping])
        assert count1 == 1
        assert count2 == 0

        con = duckdb.connect(db_path, read_only=True)
        total = con.execute("SELECT COUNT(*) FROM proxy_eoa_map").fetchone()[0]
        con.close()
        assert total == 1

    def test_different_proxies_both_inserted(self, db_path: str):
        m1 = {
            "proxy_address": "0xproxy_a",
            "eoa_address": "0xeoa1",
            "confidence": 0.8,
            "first_seen_block": 50_000_000,
            "first_seen_ts": None,
            "factory_contract": GNOSIS_SAFE_FACTORY,
        }
        m2 = {
            "proxy_address": "0xproxy_b",
            "eoa_address": "0xeoa2",
            "confidence": 1.0,
            "first_seen_block": 50_000_100,
            "first_seen_ts": None,
            "factory_contract": POLYMARKET_FACTORY,
        }
        count = insert_mappings(db_path, [m1, m2])
        assert count == 2


class TestConfidenceScoring:
    def test_gnosis_confidence_08(self):
        client = MagicMock()
        # Mock get_tx_sender via rpc_call
        client.post.return_value = httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "result": {"from": "0xeoa_gnosis", "to": GNOSIS_SAFE_FACTORY, "hash": "0x1"},
                "id": 1,
            },
            request=httpx.Request("POST", "http://test"),
        )
        events = [_make_event(tx_hash="0x1")]
        mappings = process_events(client, "http://test", events, GNOSIS_SAFE_FACTORY)
        assert len(mappings) == 1
        assert mappings[0]["confidence"] == 0.8

    def test_polymarket_confidence_10(self):
        client = MagicMock()
        client.post.return_value = httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "result": {"from": "0xeoa_poly", "to": POLYMARKET_FACTORY, "hash": "0x2"},
                "id": 1,
            },
            request=httpx.Request("POST", "http://test"),
        )
        events = [_make_event(tx_hash="0x2")]
        mappings = process_events(client, "http://test", events, POLYMARKET_FACTORY)
        assert len(mappings) == 1
        assert mappings[0]["confidence"] == 1.0


class TestBackoff429:
    def test_retries_on_429_then_succeeds(self):
        responses = [
            httpx.Response(
                429,
                request=httpx.Request("POST", "http://test"),
            ),
            httpx.Response(
                200,
                json={"jsonrpc": "2.0", "result": "0x1000", "id": 1},
                request=httpx.Request("POST", "http://test"),
            ),
        ]
        client = MagicMock()
        client.post.side_effect = responses

        with patch("polybot.indexers.proxy_factory.time.sleep"):
            result = rpc_call(client, "http://test", "eth_blockNumber")
        assert result["result"] == "0x1000"
        assert client.post.call_count == 2


class TestLogResponseTooLarge:
    def test_raises_on_log_size_exceeded(self):
        client = MagicMock()
        client.post.return_value = httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": "Log response size exceeded"},
                "id": 1,
            },
            request=httpx.Request("POST", "http://test"),
        )
        with pytest.raises(LogResponseTooLarge):
            rpc_call(client, "http://test", "eth_getLogs", [{}])


class TestIncrementalMode:
    def test_resumes_from_last_cursor(self, db_path: str):
        # Seed indexer_state with a last_cursor
        con = duckdb.connect(db_path)
        con.execute(
            """
            INSERT INTO indexer_state
                (indexer_name, last_synced_at, last_cursor, last_run_status,
                 last_run_duration_ms, ingested_count)
            VALUES ('proxy_factory', NOW(), '50000000', 'success', 100, 0)
            """
        )
        con.close()

        last = get_last_scanned_block(db_path)
        assert last == 50_000_000

    def test_returns_none_when_no_state(self, db_path: str):
        last = get_last_scanned_block(db_path)
        assert last is None


class TestUpdateIndexerState:
    def test_writes_state(self, db_path: str):
        update_indexer_state(db_path, 60_000_000, "success", 42, 1500)

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT last_cursor, last_run_status, ingested_count "
            "FROM indexer_state WHERE indexer_name = 'proxy_factory'"
        ).fetchone()
        con.close()

        assert row[0] == "60000000"
        assert row[1] == "success"
        assert row[2] == 42


class TestRunIntegration:
    def test_run_with_mocked_rpc(self, db_path: str):
        """End-to-end run with mocked RPC — simulates 1 batch with 1 event."""
        block_resp = {"jsonrpc": "2.0", "result": hex(11_002_000), "id": 1}
        event = _make_event(
            proxy_hex="aaaa000000000000000000000000000000000001",
            block_number=11_000_500,
            tx_hash="0xtx1",
        )
        logs_resp_with_events = {"jsonrpc": "2.0", "result": [event], "id": 1}
        logs_resp_empty = {"jsonrpc": "2.0", "result": [], "id": 1}
        tx_resp = {
            "jsonrpc": "2.0",
            "result": {"from": "0xeoa_test", "to": GNOSIS_SAFE_FACTORY, "hash": "0xtx1"},
            "id": 1,
        }

        responses_map: dict[str, list] = {
            "eth_blockNumber": [block_resp],
            "eth_getLogs": [logs_resp_with_events, logs_resp_empty],
            "eth_getTransactionByHash": [tx_resp],
        }

        def mock_post(url, **kwargs):
            body = kwargs.get("json", {})
            method = body.get("method", "")
            resps = responses_map.get(method, [])
            resp_data = resps.pop(0) if resps else {"jsonrpc": "2.0", "result": [], "id": 1}
            return httpx.Response(
                200, json=resp_data, request=httpx.Request("POST", url)
            )

        with (
            patch("polybot.indexers.proxy_factory.httpx.Client") as mock_client_cls,
            patch("polybot.indexers.proxy_factory.time.sleep"),
        ):
            mock_client = MagicMock()
            mock_client.post.side_effect = mock_post
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            count = run(db_path, "http://test-alchemy")

        assert count == 1

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT proxy_address, eoa_address, confidence, method "
            "FROM proxy_eoa_map"
        ).fetchone()
        con.close()

        assert row[0].startswith("0x")
        assert len(row[0]) == 42
        assert row[1] == "0xeoa_test"
        assert float(row[2]) == 0.8
        assert row[3] == "direct_factory"
