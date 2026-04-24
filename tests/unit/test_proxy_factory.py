"""Tests for indexer_proxy_factory (targeted EOA resolution)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import httpx
import pytest

from polybot.db.migrations import apply_migrations
from polybot.indexers.proxy_factory import (
    get_unresolved_wallets,
    resolve_eoa,
    rpc_call,
    run,
    update_indexer_state,
    upsert_mapping,
)


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


def _seed_wallet(db_path: str, address: str = "0xwallet1"):
    con = duckdb.connect(db_path)
    con.execute(
        "INSERT OR REPLACE INTO tracked_wallets "
        "(address, tier, active, last_seen_timestamp) "
        "VALUES (?, 'A', TRUE, 0)",
        [address],
    )
    con.close()


def _mock_rpc_response(data):
    return httpx.Response(
        200, json=data, request=httpx.Request("POST", "http://test")
    )


class TestResolveEOA:
    def test_self_eoa_no_code(self):
        """Wallet with no contract code → self-mapping."""
        client = MagicMock()
        client.post.return_value = _mock_rpc_response(
            {"jsonrpc": "2.0", "result": "0x", "id": 1}
        )
        eoa, method, conf = resolve_eoa(client, "http://test", "0xABC123")
        assert eoa == "0xabc123"
        assert method == "manual"
        assert conf == 1.0

    def test_gnosis_safe_get_owners(self):
        """Contract with getOwners() → owner is EOA."""
        # First call: eth_getCode returns contract code
        code_resp = _mock_rpc_response(
            {"jsonrpc": "2.0", "result": "0x1234abcd", "id": 1}
        )
        # Second call: eth_call getOwners() returns 1 owner
        owner_addr = "deadbeef" * 5  # 20 bytes
        owners_data = (
            "0x"
            + "0" * 64  # offset to array
            + "0" * 63 + "1"  # array length = 1
            + "0" * 24 + owner_addr  # padded address
        )
        # Fix: offset should be 0x20 = 32
        owners_data = (
            "0x"
            + f"{32:064x}"  # offset
            + f"{1:064x}"  # length
            + "0" * 24 + owner_addr
        )
        owners_resp = _mock_rpc_response(
            {"jsonrpc": "2.0", "result": owners_data, "id": 1}
        )

        client = MagicMock()
        client.post.side_effect = [code_resp, owners_resp]

        eoa, method, conf = resolve_eoa(client, "http://test", "0xproxy")
        assert eoa == "0x" + owner_addr
        assert method == "direct_factory"
        assert conf == 1.0

    def test_first_tx_fallback(self):
        """Contract without getOwners → fallback to first incoming tx."""
        code_resp = _mock_rpc_response(
            {"jsonrpc": "2.0", "result": "0x1234", "id": 1}
        )
        # getOwners fails (short result)
        owners_resp = _mock_rpc_response(
            {"jsonrpc": "2.0", "result": "0x", "id": 1}
        )
        # alchemy_getAssetTransfers returns first tx
        transfers_resp = _mock_rpc_response(
            {
                "jsonrpc": "2.0",
                "result": {
                    "transfers": [{"from": "0xSENDER", "blockNum": "0x100"}]
                },
                "id": 1,
            }
        )

        client = MagicMock()
        client.post.side_effect = [code_resp, owners_resp, transfers_resp]

        eoa, method, conf = resolve_eoa(client, "http://test", "0xproxy2")
        assert eoa == "0xsender"
        assert method == "first_tx"
        assert conf == 0.8


class TestUpsertMapping:
    def test_insert_new(self, db_path):
        upsert_mapping(db_path, "0xproxy", "0xeoa", 1.0, "direct_factory")
        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT eoa_address, confidence FROM proxy_eoa_map "
            "WHERE proxy_address = '0xproxy'"
        ).fetchone()
        con.close()
        assert row[0] == "0xeoa"
        assert float(row[1]) == 1.0

    def test_upsert_updates(self, db_path):
        upsert_mapping(db_path, "0xproxy", "0xeoa1", 0.8, "first_tx")
        upsert_mapping(db_path, "0xproxy", "0xeoa2", 1.0, "direct_factory")
        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT eoa_address, confidence FROM proxy_eoa_map "
            "WHERE proxy_address = '0xproxy'"
        ).fetchone()
        con.close()
        assert row[0] == "0xeoa2"
        assert float(row[1]) == 1.0


class TestGetUnresolved:
    def test_finds_unresolved(self, db_path):
        _seed_wallet(db_path, "0xw1")
        _seed_wallet(db_path, "0xw2")
        upsert_mapping(db_path, "0xw1", "0xeoa1", 1.0, "manual")
        # 0xw2 has no mapping
        unresolved = get_unresolved_wallets(db_path)
        assert unresolved == ["0xw2"]

    def test_all_resolved(self, db_path):
        _seed_wallet(db_path, "0xw1")
        upsert_mapping(db_path, "0xw1", "0xeoa1", 1.0, "manual")
        assert get_unresolved_wallets(db_path) == []

    def test_empty(self, db_path):
        assert get_unresolved_wallets(db_path) == []


class TestBackoff429:
    def test_retries_on_429(self):
        responses = [
            httpx.Response(429, request=httpx.Request("POST", "http://test")),
            _mock_rpc_response({"jsonrpc": "2.0", "result": "0x1000", "id": 1}),
        ]
        client = MagicMock()
        client.post.side_effect = responses

        with patch("polybot.indexers.proxy_factory.time.sleep"):
            result = rpc_call(client, "http://test", "eth_blockNumber")
        assert result["result"] == "0x1000"


class TestUpdateIndexerState:
    def test_writes_state(self, db_path):
        update_indexer_state(db_path, "success", 15, 500)
        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT last_run_status, ingested_count "
            "FROM indexer_state WHERE indexer_name = 'proxy_factory'"
        ).fetchone()
        con.close()
        assert row[0] == "success"
        assert row[1] == 15


class TestRunIntegration:
    def test_resolves_unresolved_wallets(self, db_path):
        """End-to-end: 2 wallets, 1 self-EOA + 1 Gnosis Safe."""
        _seed_wallet(db_path, "0xbare_eoa")
        _seed_wallet(db_path, "0xsafe_proxy")

        call_idx = {"n": 0}

        def mock_post(url, **kwargs):
            body = kwargs.get("json", {})
            method = body.get("method", "")
            call_idx["n"] += 1

            if method == "eth_getCode":
                address = body["params"][0]
                if "bare" in address:
                    return _mock_rpc_response(
                        {"jsonrpc": "2.0", "result": "0x", "id": 1}
                    )
                # safe_proxy has code
                return _mock_rpc_response(
                    {"jsonrpc": "2.0", "result": "0xabcdef", "id": 1}
                )

            if method == "eth_call":
                # getOwners returns 1 owner
                owner = "1234567890" * 4
                data = "0x" + f"{32:064x}" + f"{1:064x}" + "0" * 24 + owner
                return _mock_rpc_response(
                    {"jsonrpc": "2.0", "result": data, "id": 1}
                )

            return _mock_rpc_response(
                {"jsonrpc": "2.0", "result": "0x", "id": 1}
            )

        with (
            patch("polybot.indexers.proxy_factory.httpx.Client") as mock_cls,
            patch("polybot.indexers.proxy_factory.time.sleep"),
        ):
            mock_client = MagicMock()
            mock_client.post.side_effect = mock_post
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_cls.return_value = mock_client

            count = run(db_path, "http://test")

        assert count == 2

        con = duckdb.connect(db_path, read_only=True)
        rows = con.execute(
            "SELECT proxy_address, method FROM proxy_eoa_map "
            "ORDER BY proxy_address"
        ).fetchall()
        con.close()
        assert len(rows) == 2
        methods = {r[0]: r[1] for r in rows}
        assert methods["0xbare_eoa"] == "manual"
        assert methods["0xsafe_proxy"] == "direct_factory"

    def test_no_unresolved_is_noop(self, db_path):
        """No unresolved wallets → 0 resolved, state updated."""
        with patch("polybot.indexers.proxy_factory.httpx.Client"):
            count = run(db_path, "http://test")
        assert count == 0
