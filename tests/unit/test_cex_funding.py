"""Tests for CEX funding indexer."""

from pathlib import Path
from unittest.mock import MagicMock, patch

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
