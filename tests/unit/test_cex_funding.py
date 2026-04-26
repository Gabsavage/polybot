"""Tests for CEX funding indexer."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import httpx
import pytest

from polybot.db.migrations import apply_migrations


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


def _mock_rpc_response(data):
    return httpx.Response(200, json=data, request=httpx.Request("POST", "http://test"))


def _alchemy_transfers_response(transfers: list[dict]) -> dict:
    """Build a mock alchemy_getAssetTransfers response."""
    return {
        "jsonrpc": "2.0",
        "result": {"transfers": transfers},
        "id": 1,
    }


class TestFetchFirstUsdcTransfers:
    def test_returns_transfers(self):
        from polybot.indexers.cex_funding import fetch_first_usdc_transfers

        transfers = [
            {"from": "0xfunder1", "to": "0xwallet", "value": 1000.0, "blockNum": "0x100"},
            {"from": "0xfunder2", "to": "0xwallet", "value": 500.0, "blockNum": "0x200"},
        ]
        client = MagicMock()
        client.post.return_value = _mock_rpc_response(_alchemy_transfers_response(transfers))

        result = fetch_first_usdc_transfers(client, "http://test", "0xwallet")
        assert len(result) == 2
        assert result[0]["from"] == "0xfunder1"

    def test_returns_empty_on_no_transfers(self):
        from polybot.indexers.cex_funding import fetch_first_usdc_transfers

        client = MagicMock()
        client.post.return_value = _mock_rpc_response(_alchemy_transfers_response([]))

        result = fetch_first_usdc_transfers(client, "http://test", "0xwallet")
        assert result == []


class TestTraceFundingHops:
    def test_two_hops(self):
        from polybot.indexers.cex_funding import trace_funding_hops

        hop1_resp = _mock_rpc_response(
            _alchemy_transfers_response(
                [
                    {"from": "0xfunder", "to": "0xwallet", "value": 1000.0, "blockNum": "0x1"},
                ]
            )
        )
        hop2_resp = _mock_rpc_response(
            _alchemy_transfers_response(
                [
                    {"from": "0xoriginal", "to": "0xfunder", "value": 5000.0, "blockNum": "0x1"},
                ]
            )
        )

        client = MagicMock()
        client.post.side_effect = [hop1_resp, hop2_resp]

        with patch("polybot.indexers.cex_funding.time.sleep"):
            result = trace_funding_hops(client, "http://test", "0xwallet")

        assert result["funded_by"] == "0xfunder"
        assert result["funded_by_hop2"] == "0xoriginal"

    def test_no_usdc_funding(self):
        from polybot.indexers.cex_funding import trace_funding_hops

        empty_resp = _mock_rpc_response(_alchemy_transfers_response([]))

        client = MagicMock()
        client.post.return_value = empty_resp

        with patch("polybot.indexers.cex_funding.time.sleep"):
            result = trace_funding_hops(client, "http://test", "0xwallet")

        assert result["funded_by"] is None
        assert result["funded_by_hop2"] is None

    def test_one_hop_only(self):
        from polybot.indexers.cex_funding import trace_funding_hops

        hop1_resp = _mock_rpc_response(
            _alchemy_transfers_response(
                [
                    {"from": "0xfunder", "to": "0xwallet", "value": 1000.0, "blockNum": "0x1"},
                ]
            )
        )
        hop2_resp = _mock_rpc_response(_alchemy_transfers_response([]))

        client = MagicMock()
        client.post.side_effect = [hop1_resp, hop2_resp]

        with patch("polybot.indexers.cex_funding.time.sleep"):
            result = trace_funding_hops(client, "http://test", "0xwallet")

        assert result["funded_by"] == "0xfunder"
        assert result["funded_by_hop2"] is None


def _seed_trades(db_path: str, wallets_with_volume: list[tuple[str, float]]):
    """Insert fake trades into trades_all for testing."""
    con = duckdb.connect(db_path)
    for i, (wallet, vol) in enumerate(wallets_with_volume):
        con.execute(
            """
            INSERT INTO trades_all (
                tx_hash_log_idx, transaction_hash, log_index,
                proxy_wallet, size_usd, timestamp_ts
            ) VALUES (?, ?, ?, ?, ?, NOW())
            """,
            [f"hash_{wallet}_{i}", f"tx_{i}", i, wallet, vol],
        )
    con.close()


def _seed_cex_hot_wallet(db_path: str, address: str, exchange: str):
    """Insert a CEX hot wallet for testing."""
    con = duckdb.connect(db_path)
    con.execute(
        "INSERT INTO cex_hot_wallets (address, exchange_name) VALUES (?, ?)",
        [address.lower(), exchange],
    )
    con.close()


class TestIdentifyCex:
    def test_direct_hot_wallet(self, db_path):
        from polybot.indexers.cex_funding import identify_cex

        _seed_cex_hot_wallet(db_path, "0xbinance_hw", "Binance")

        result = identify_cex(db_path, "0xBINANCE_HW", None)
        assert result is not None
        assert result["cex_source"] == "Binance"
        assert result["method"] == "direct_hot_wallet"
        assert result["confidence"] == 1.0
        assert result["deposit_address"] is None

    def test_hop2_hot_wallet(self, db_path):
        from polybot.indexers.cex_funding import identify_cex

        _seed_cex_hot_wallet(db_path, "0xcoinbase_hw", "Coinbase")

        result = identify_cex(db_path, "0xdeposit_addr", "0xCOINBASE_HW")
        assert result is not None
        assert result["cex_source"] == "Coinbase"
        assert result["method"] == "hop2_hot_wallet"
        assert result["confidence"] == 0.9
        assert result["deposit_address"] == "0xdeposit_addr"

    def test_no_match(self, db_path):
        from polybot.indexers.cex_funding import identify_cex

        result = identify_cex(db_path, "0xrandom1", "0xrandom2")
        assert result is None

    def test_none_funded_by(self, db_path):
        from polybot.indexers.cex_funding import identify_cex

        result = identify_cex(db_path, None, None)
        assert result is None


class TestInsertMapping:
    def test_insert_with_cex(self, db_path):
        from polybot.indexers.cex_funding import insert_mapping

        hops = {"funded_by": "0xfunder", "funded_by_hop2": "0xhw"}
        cex_result = {
            "cex_source": "Binance",
            "method": "direct_hot_wallet",
            "deposit_address": None,
            "confidence": 1.0,
        }
        insert_mapping(db_path, "0xwallet1", hops, cex_result)

        con = duckdb.connect(db_path)
        row = con.execute(
            "SELECT wallet_address, cex_source, method, confidence "
            "FROM cex_funding_map WHERE wallet_address = '0xwallet1'"
        ).fetchone()
        con.close()
        assert row[1] == "Binance"
        assert row[2] == "direct_hot_wallet"
        assert float(row[3]) == 1.0

    def test_insert_no_cex(self, db_path):
        from polybot.indexers.cex_funding import insert_mapping

        hops = {"funded_by": "0xfunder", "funded_by_hop2": "0xrandom"}
        insert_mapping(db_path, "0xwallet2", hops, None)

        con = duckdb.connect(db_path)
        row = con.execute(
            "SELECT wallet_address, funded_by, cex_source, method "
            "FROM cex_funding_map WHERE wallet_address = '0xwallet2'"
        ).fetchone()
        con.close()
        assert row[1] == "0xfunder"
        assert row[2] is None
        assert row[3] is None

    def test_insert_no_usdc(self, db_path):
        from polybot.indexers.cex_funding import insert_mapping

        hops = {"funded_by": None, "funded_by_hop2": None}
        insert_mapping(db_path, "0xwallet3", hops, None)

        con = duckdb.connect(db_path)
        row = con.execute(
            "SELECT funded_by, cex_source, method "
            "FROM cex_funding_map WHERE wallet_address = '0xwallet3'"
        ).fetchone()
        con.close()
        assert row[0] is None
        assert row[1] is None
        assert row[2] is None

    def test_idempotent(self, db_path):
        from polybot.indexers.cex_funding import insert_mapping

        hops = {"funded_by": "0xf", "funded_by_hop2": None}
        insert_mapping(db_path, "0xwallet4", hops, None)
        insert_mapping(db_path, "0xwallet4", hops, None)

        con = duckdb.connect(db_path)
        count = con.execute(
            "SELECT COUNT(*) FROM cex_funding_map WHERE wallet_address = '0xwallet4'"
        ).fetchone()[0]
        con.close()
        assert count == 1


class TestGetUntracedWallets:
    def test_returns_untraced(self, db_path):
        from polybot.indexers.cex_funding import (
            get_untraced_wallets,
            insert_mapping,
        )

        _seed_trades(
            db_path,
            [
                ("0xw1", 10000.0),
                ("0xw2", 5000.0),
                ("0xw3", 3000.0),
            ],
        )
        insert_mapping(
            db_path,
            "0xw1",
            {"funded_by": "0xf", "funded_by_hop2": None},
            None,
        )

        result = get_untraced_wallets(db_path, max_wallets=10)
        assert "0xw1" not in result
        assert "0xw2" in result
        assert "0xw3" in result

    def test_priority_by_volume(self, db_path):
        from polybot.indexers.cex_funding import get_untraced_wallets

        _seed_trades(
            db_path,
            [
                ("0xsmall", 100.0),
                ("0xbig", 50000.0),
                ("0xmedium", 5000.0),
            ],
        )

        result = get_untraced_wallets(db_path, max_wallets=10)
        assert result[0] == "0xbig"
        assert result[1] == "0xmedium"
        assert result[2] == "0xsmall"

    def test_respects_limit(self, db_path):
        from polybot.indexers.cex_funding import get_untraced_wallets

        _seed_trades(db_path, [(f"0xw{i}", float(i * 100)) for i in range(10)])

        result = get_untraced_wallets(db_path, max_wallets=3)
        assert len(result) == 3


class TestRun:
    def test_end_to_end(self, db_path):
        """3 wallets: 1 Binance direct, 1 Coinbase hop2, 1 no USDC."""
        from polybot.indexers.cex_funding import run

        _seed_cex_hot_wallet(db_path, "0xbinance_hw", "Binance")
        _seed_cex_hot_wallet(db_path, "0xcoinbase_hw", "Coinbase")

        _seed_trades(
            db_path,
            [
                ("0xdirect", 10000.0),
                ("0xvia_deposit", 5000.0),
                ("0xno_usdc", 3000.0),
            ],
        )

        call_count = {"n": 0}

        def mock_post(url, **kwargs):
            body = kwargs.get("json", {})
            params = body.get("params", [{}])
            to_addr = params[0].get("toAddress", "") if params else ""
            call_count["n"] += 1

            if to_addr == "0xdirect":
                return _mock_rpc_response(
                    _alchemy_transfers_response(
                        [
                            {
                                "from": "0xbinance_hw",
                                "to": "0xdirect",
                                "value": 1000.0,
                                "blockNum": "0x1",
                            },
                        ]
                    )
                )
            if to_addr == "0xbinance_hw":
                return _mock_rpc_response(_alchemy_transfers_response([]))
            if to_addr == "0xvia_deposit":
                return _mock_rpc_response(
                    _alchemy_transfers_response(
                        [
                            {
                                "from": "0xmy_deposit",
                                "to": "0xvia_deposit",
                                "value": 500.0,
                                "blockNum": "0x1",
                            },
                        ]
                    )
                )
            if to_addr == "0xmy_deposit":
                return _mock_rpc_response(
                    _alchemy_transfers_response(
                        [
                            {
                                "from": "0xcoinbase_hw",
                                "to": "0xmy_deposit",
                                "value": 5000.0,
                                "blockNum": "0x1",
                            },
                        ]
                    )
                )
            # 0xno_usdc and anything else
            return _mock_rpc_response(_alchemy_transfers_response([]))

        with (
            patch("polybot.indexers.cex_funding.httpx.Client") as mock_cls,
            patch("polybot.indexers.cex_funding.time.sleep"),
        ):
            mock_client = MagicMock()
            mock_client.post.side_effect = mock_post
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_cls.return_value = mock_client

            count = run(db_path, "http://test", max_wallets=10)

        # count = wallets with CEX match
        assert count == 2

        con = duckdb.connect(db_path)
        rows = con.execute(
            "SELECT wallet_address, cex_source, method, deposit_address "
            "FROM cex_funding_map ORDER BY wallet_address"
        ).fetchall()
        con.close()

        assert len(rows) == 3
        mapped = {r[0]: r for r in rows}

        # 0xdirect → Binance direct
        assert mapped["0xdirect"][1] == "Binance"
        assert mapped["0xdirect"][2] == "direct_hot_wallet"

        # 0xno_usdc → no match
        assert mapped["0xno_usdc"][1] is None
        assert mapped["0xno_usdc"][2] is None

        # 0xvia_deposit → Coinbase via deposit
        assert mapped["0xvia_deposit"][1] == "Coinbase"
        assert mapped["0xvia_deposit"][2] == "hop2_hot_wallet"
        assert mapped["0xvia_deposit"][3] == "0xmy_deposit"

    def test_no_wallets_noop(self, db_path):
        """No untraced wallets → 0 count, state updated."""
        from polybot.indexers.cex_funding import run

        with patch("polybot.indexers.cex_funding.httpx.Client"):
            count = run(db_path, "http://test", max_wallets=10)
        assert count == 0

        con = duckdb.connect(db_path)
        row = con.execute(
            "SELECT last_run_status FROM indexer_state WHERE indexer_name = 'cex_funding'"
        ).fetchone()
        con.close()
        assert row[0] == "success"

    def test_skips_failed_wallet(self, db_path):
        """A wallet that raises RPCError is skipped, others continue."""
        from polybot.indexers.cex_funding import run

        _seed_cex_hot_wallet(db_path, "0xbinance_hw", "Binance")
        _seed_trades(
            db_path,
            [
                ("0xgood", 10000.0),
                ("0xbad", 5000.0),
            ],
        )

        def mock_post(url, **kwargs):
            body = kwargs.get("json", {})
            params = body.get("params", [{}])
            to_addr = params[0].get("toAddress", "") if params else ""

            if to_addr == "0xbad":
                return httpx.Response(429, request=httpx.Request("POST", "http://test"))
            if to_addr == "0xgood":
                return _mock_rpc_response(
                    _alchemy_transfers_response(
                        [
                            {
                                "from": "0xbinance_hw",
                                "to": "0xgood",
                                "value": 1000.0,
                                "blockNum": "0x1",
                            },
                        ]
                    )
                )
            return _mock_rpc_response(_alchemy_transfers_response([]))

        with (
            patch("polybot.indexers.cex_funding.httpx.Client") as mock_cls,
            patch("polybot.indexers.cex_funding.time.sleep"),
        ):
            mock_client = MagicMock()
            mock_client.post.side_effect = mock_post
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_cls.return_value = mock_client

            count = run(db_path, "http://test", max_wallets=10)

        assert count == 1

        con = duckdb.connect(db_path)
        total = con.execute("SELECT COUNT(*) FROM cex_funding_map").fetchone()[0]
        con.close()
        assert total == 1
