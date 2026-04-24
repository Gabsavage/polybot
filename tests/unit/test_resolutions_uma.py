"""Tests for indexer_resolutions_uma."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import httpx
import pytest

from polybot.db.migrations import apply_migrations
from polybot.indexers.resolutions_uma import (
    CONDITION_RESOLUTION_TOPIC,
    _interpret_payouts,
    get_last_scanned_block,
    parse_condition_resolution,
    run,
    update_indexer_state,
    upsert_resolutions,
)


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


def _make_resolution_event(
    condition_id: str = "0x" + "aa" * 32,
    question_id: str = "0x" + "bb" * 32,
    oracle: str = "0x" + "00" * 12 + "cc" * 20,
    payouts: list[int] | None = None,
    block_number: int = 50_000_000,
    tx_hash: str = "0xdeadbeef",
) -> dict:
    """Build a mock ConditionResolution event."""
    if payouts is None:
        payouts = [1, 0]  # YES by default

    # Build data: outcomeSlotCount + offset + arr_len + payouts
    slot_count = len(payouts)
    offset = 64  # 0x40
    data = "0x"
    data += f"{slot_count:064x}"
    data += f"{offset:064x}"
    data += f"{len(payouts):064x}"
    for p in payouts:
        data += f"{p:064x}"

    return {
        "topics": [
            CONDITION_RESOLUTION_TOPIC,
            condition_id,
            oracle,
            question_id,
        ],
        "data": data,
        "blockNumber": hex(block_number),
        "transactionHash": tx_hash,
        "logIndex": "0x1",
    }


class TestPayoutInterpretation:
    def test_yes(self):
        outcome, price = _interpret_payouts([1, 0])
        assert outcome == "YES"
        assert price == 1.0

    def test_no(self):
        outcome, price = _interpret_payouts([0, 1])
        assert outcome == "NO"
        assert price == 0.0

    def test_invalid(self):
        outcome, price = _interpret_payouts([1, 1])
        assert outcome == "INVALID"
        assert price == 0.5

    def test_unknown(self):
        outcome, price = _interpret_payouts([2, 1, 0])
        assert outcome == "UNKNOWN"
        assert price == -1.0


class TestEventParsing:
    def test_parse_yes_resolution(self):
        event = _make_resolution_event(payouts=[1, 0])
        result = parse_condition_resolution(event)
        assert result is not None
        assert result["condition_id"] == "0x" + "aa" * 32
        assert result["question_id"] == "0x" + "bb" * 32
        assert result["settled_outcome"] == "YES"
        assert result["final_price"] == 1.0

    def test_parse_no_resolution(self):
        event = _make_resolution_event(payouts=[0, 1])
        result = parse_condition_resolution(event)
        assert result["settled_outcome"] == "NO"
        assert result["final_price"] == 0.0

    def test_parse_invalid_resolution(self):
        event = _make_resolution_event(payouts=[1, 1])
        result = parse_condition_resolution(event)
        assert result["settled_outcome"] == "INVALID"
        assert result["final_price"] == 0.5

    def test_parse_missing_topics_returns_none(self):
        event = {"topics": [CONDITION_RESOLUTION_TOPIC], "data": "0x", "blockNumber": "0x1"}
        result = parse_condition_resolution(event)
        assert result is None

    def test_parse_short_data_returns_none(self):
        event = _make_resolution_event()
        event["data"] = "0x1234"
        result = parse_condition_resolution(event)
        assert result is None


class TestUpsertResolutions:
    def test_insert_new_resolution(self, db_path: str):
        res = {
            "condition_id": "0xcond1",
            "question_id": "0xq1",
            "settled_at": None,
            "final_price": 1.0,
            "settled_outcome": "YES",
        }
        count = upsert_resolutions(db_path, [res])
        assert count == 1

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT condition_id, settled_outcome FROM resolutions"
        ).fetchone()
        con.close()
        assert row[0] == "0xcond1"
        assert row[1] == "YES"

    def test_upsert_updates_existing(self, db_path: str):
        res1 = {
            "condition_id": "0xcond1",
            "question_id": "0xq1",
            "settled_at": None,
            "final_price": 1.0,
            "settled_outcome": "YES",
        }
        upsert_resolutions(db_path, [res1])

        # Same condition_id, different outcome (re-resolution)
        res2 = {
            "condition_id": "0xcond1",
            "question_id": "0xq1",
            "settled_at": None,
            "final_price": 0.0,
            "settled_outcome": "NO",
        }
        upsert_resolutions(db_path, [res2])

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT settled_outcome FROM resolutions WHERE condition_id = '0xcond1'"
        ).fetchone()
        total = con.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0]
        con.close()
        assert row[0] == "NO"
        assert total == 1

    def test_multiple_resolutions(self, db_path: str):
        resolutions = [
            {
                "condition_id": f"0xcond{i}",
                "question_id": f"0xq{i}",
                "settled_at": None,
                "final_price": 1.0,
                "settled_outcome": "YES",
            }
            for i in range(5)
        ]
        count = upsert_resolutions(db_path, resolutions)
        assert count == 5

    def test_empty_list(self, db_path: str):
        count = upsert_resolutions(db_path, [])
        assert count == 0


class TestIncrementalMode:
    def test_resumes_from_last_cursor(self, db_path: str):
        con = duckdb.connect(db_path)
        con.execute(
            """
            INSERT INTO indexer_state
                (indexer_name, last_synced_at, last_cursor, last_run_status,
                 last_run_duration_ms, ingested_count)
            VALUES ('resolutions_uma', NOW(), '70000000', 'success', 200, 0)
            """
        )
        con.close()

        last = get_last_scanned_block(db_path)
        assert last == 70_000_000

    def test_returns_none_when_no_state(self, db_path: str):
        last = get_last_scanned_block(db_path)
        assert last is None


class TestUpdateIndexerState:
    def test_writes_state(self, db_path: str):
        update_indexer_state(db_path, 80_000_000, "success", 100, 5000)

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT last_cursor, last_run_status, ingested_count "
            "FROM indexer_state WHERE indexer_name = 'resolutions_uma'"
        ).fetchone()
        con.close()

        assert row[0] == "80000000"
        assert row[1] == "success"
        assert row[2] == 100


class TestRunIntegration:
    def test_run_with_mocked_rpc(self, db_path: str):
        """End-to-end run with mocked RPC — 1 batch with 2 resolution events."""
        block_resp = {"jsonrpc": "2.0", "result": hex(11_005_000), "id": 1}
        event_yes = _make_resolution_event(
            condition_id="0x" + "11" * 32,
            question_id="0x" + "aa" * 32,
            payouts=[1, 0],
            block_number=11_001_000,
        )
        event_no = _make_resolution_event(
            condition_id="0x" + "22" * 32,
            question_id="0x" + "bb" * 32,
            payouts=[0, 1],
            block_number=11_002_000,
        )
        logs_resp = {"jsonrpc": "2.0", "result": [event_yes, event_no], "id": 1}
        logs_empty = {"jsonrpc": "2.0", "result": [], "id": 1}
        block_ts_resp = {
            "jsonrpc": "2.0",
            "result": {"timestamp": hex(1700000000)},
            "id": 1,
        }

        responses_map: dict[str, list] = {
            "eth_blockNumber": [block_resp],
            "eth_getLogs": [logs_resp, logs_empty],
            "eth_getBlockByNumber": [block_ts_resp, block_ts_resp],
        }

        def mock_post(url, **kwargs):
            body = kwargs.get("json", {})
            method = body.get("method", "")
            resps = responses_map.get(method, [])
            resp_data = (
                resps.pop(0)
                if resps
                else {"jsonrpc": "2.0", "result": [], "id": 1}
            )
            return httpx.Response(
                200, json=resp_data, request=httpx.Request("POST", url)
            )

        with (
            patch(
                "polybot.indexers.resolutions_uma.httpx.Client"
            ) as mock_cls,
            patch("polybot.indexers.resolutions_uma.time.sleep"),
        ):
            mock_client = MagicMock()
            mock_client.post.side_effect = mock_post
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_cls.return_value = mock_client

            count = run(db_path, "http://test-alchemy")

        assert count == 2

        con = duckdb.connect(db_path, read_only=True)
        rows = con.execute(
            "SELECT condition_id, settled_outcome "
            "FROM resolutions ORDER BY condition_id"
        ).fetchall()
        con.close()

        assert len(rows) == 2
        # 0x1111... < 0x2222...
        assert rows[0][1] == "YES"
        assert rows[1][1] == "NO"
