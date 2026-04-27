# M9-2 CEX Funding Indexer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trace 2-hop USDC funding paths for active wallets to identify CEX sources and populate `cex_funding_map`.

**Architecture:** Single module `src/polybot/indexers/cex_funding.py` with top-level functions following the proxy_factory pattern. Uses `alchemy_getAssetTransfers` for USDC transfer lookups, matches against `cex_hot_wallets` table, stores results in `cex_funding_map`. Scheduled hourly in daemon.py.

**Tech Stack:** DuckDB, httpx, structlog, pytest

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `src/polybot/indexers/cex_funding.py` | 2-hop USDC funding tracer + CEX identification |
| Modify | `src/polybot/daemon.py` | Add cex_funding to scheduled indexers |
| Create | `tests/unit/test_cex_funding.py` | Unit tests with mocked Alchemy |
| Create | `tests/integration/test_cex_funding_live.py` | Live integration test (skip without env) |

---

### Task 1: Core functions — `rpc_call`, `fetch_first_usdc_transfers`, `trace_funding_hops`

**Files:**
- Create: `src/polybot/indexers/cex_funding.py`
- Create: `tests/unit/test_cex_funding.py`

- [ ] **Step 1: Write tests for `fetch_first_usdc_transfers` and `trace_funding_hops`**

Create `tests/unit/test_cex_funding.py`:

```python
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
    return httpx.Response(
        200, json=data, request=httpx.Request("POST", "http://test")
    )


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
        client.post.return_value = _mock_rpc_response(
            _alchemy_transfers_response(transfers)
        )

        result = fetch_first_usdc_transfers(client, "http://test", "0xwallet")
        assert len(result) == 2
        assert result[0]["from"] == "0xfunder1"

    def test_returns_empty_on_no_transfers(self):
        from polybot.indexers.cex_funding import fetch_first_usdc_transfers

        client = MagicMock()
        client.post.return_value = _mock_rpc_response(
            _alchemy_transfers_response([])
        )

        result = fetch_first_usdc_transfers(client, "http://test", "0xwallet")
        assert result == []


class TestTraceFundingHops:
    def test_two_hops(self):
        from polybot.indexers.cex_funding import trace_funding_hops

        hop1_resp = _mock_rpc_response(_alchemy_transfers_response([
            {"from": "0xfunder", "to": "0xwallet", "value": 1000.0, "blockNum": "0x1"},
        ]))
        hop2_resp = _mock_rpc_response(_alchemy_transfers_response([
            {"from": "0xoriginal", "to": "0xfunder", "value": 5000.0, "blockNum": "0x1"},
        ]))

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

        hop1_resp = _mock_rpc_response(_alchemy_transfers_response([
            {"from": "0xfunder", "to": "0xwallet", "value": 1000.0, "blockNum": "0x1"},
        ]))
        hop2_resp = _mock_rpc_response(_alchemy_transfers_response([]))

        client = MagicMock()
        client.post.side_effect = [hop1_resp, hop2_resp]

        with patch("polybot.indexers.cex_funding.time.sleep"):
            result = trace_funding_hops(client, "http://test", "0xwallet")

        assert result["funded_by"] == "0xfunder"
        assert result["funded_by_hop2"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_cex_funding.py -v -k "TestFetch or TestTrace"`
Expected: FAIL — `ModuleNotFoundError: No module named 'polybot.indexers.cex_funding'`

- [ ] **Step 3: Implement the module skeleton with RPC + transfer functions**

Create `src/polybot/indexers/cex_funding.py`:

```python
"""Trace CEX funding source for wallets via USDC transfers on Polygon."""

import time

import httpx
import structlog

from polybot.config import Settings
from polybot.logging import setup_logging

logger = structlog.get_logger()

# --- Constants ---

REQUEST_TIMEOUT = 15.0
MAX_RPC_RETRIES = 5
RATE_LIMIT_SLEEP = 0.1

USDC_POLYGON = "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"
USDC_E_POLYGON = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"


# --- RPC helpers ---


class RPCError(Exception):
    pass


def rpc_call(
    client: httpx.Client,
    url: str,
    method: str,
    params: list | None = None,
) -> dict:
    """JSON-RPC call with retry on 429/5xx."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RPC_RETRIES):
        try:
            resp = client.post(
                url,
                json={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params or [],
                    "id": 1,
                },
            )
            if resp.status_code == 429:
                delay = 2**attempt
                logger.warning("rpc_429", method=method, retry_in=delay)
                time.sleep(delay)
                continue
            if resp.status_code >= 500:
                logger.warning("rpc_5xx", status=resp.status_code)
                time.sleep(2)
                continue
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RPCError(data["error"].get("message", "unknown"))
            return data
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exc = e
            delay = 2**attempt
            logger.warning(
                "rpc_network_error", error=str(e)[:100], retry_in=delay
            )
            time.sleep(delay)

    msg = f"RPC {method} failed after {MAX_RPC_RETRIES} retries"
    raise RPCError(msg) from last_exc


# --- Transfer lookups ---


def fetch_first_usdc_transfers(
    client: httpx.Client,
    alchemy_url: str,
    wallet: str,
    max_count: int = 5,
) -> list[dict]:
    """Fetch earliest USDC transfers into a wallet via Alchemy."""
    data = rpc_call(
        client,
        alchemy_url,
        "alchemy_getAssetTransfers",
        [{
            "toAddress": wallet,
            "category": ["erc20"],
            "contractAddresses": [USDC_POLYGON, USDC_E_POLYGON],
            "order": "asc",
            "maxCount": hex(max_count),
            "withMetadata": True,
        }],
    )
    return data.get("result", {}).get("transfers", [])


def trace_funding_hops(
    client: httpx.Client,
    alchemy_url: str,
    wallet: str,
) -> dict:
    """Trace 2 hops of USDC funding for a wallet."""
    transfers = fetch_first_usdc_transfers(client, alchemy_url, wallet)
    if not transfers:
        return {"funded_by": None, "funded_by_hop2": None}

    funded_by = transfers[0]["from"].lower()

    time.sleep(RATE_LIMIT_SLEEP)

    hop2_transfers = fetch_first_usdc_transfers(
        client, alchemy_url, funded_by
    )
    funded_by_hop2 = (
        hop2_transfers[0]["from"].lower() if hop2_transfers else None
    )

    return {"funded_by": funded_by, "funded_by_hop2": funded_by_hop2}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_cex_funding.py -v -k "TestFetch or TestTrace"`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/polybot/indexers/cex_funding.py tests/unit/test_cex_funding.py
git commit -m "feat(M9): add cex_funding indexer — RPC helpers + USDC transfer tracing"
```

---

### Task 2: DB functions — `get_untraced_wallets`, `identify_cex`, `insert_mapping`, `update_indexer_state`

**Files:**
- Modify: `src/polybot/indexers/cex_funding.py`
- Modify: `tests/unit/test_cex_funding.py`

- [ ] **Step 1: Write tests for DB functions**

Append to `tests/unit/test_cex_funding.py`:

```python
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
            "SELECT COUNT(*) FROM cex_funding_map "
            "WHERE wallet_address = '0xwallet4'"
        ).fetchone()[0]
        con.close()
        assert count == 1


class TestGetUntracedWallets:
    def test_returns_untraced(self, db_path):
        from polybot.indexers.cex_funding import (
            get_untraced_wallets,
            insert_mapping,
        )

        _seed_trades(db_path, [
            ("0xw1", 10000.0),
            ("0xw2", 5000.0),
            ("0xw3", 3000.0),
        ])
        insert_mapping(
            db_path, "0xw1",
            {"funded_by": "0xf", "funded_by_hop2": None}, None,
        )

        result = get_untraced_wallets(db_path, max_wallets=10)
        assert "0xw1" not in result
        assert "0xw2" in result
        assert "0xw3" in result

    def test_priority_by_volume(self, db_path):
        from polybot.indexers.cex_funding import get_untraced_wallets

        _seed_trades(db_path, [
            ("0xsmall", 100.0),
            ("0xbig", 50000.0),
            ("0xmedium", 5000.0),
        ])

        result = get_untraced_wallets(db_path, max_wallets=10)
        assert result[0] == "0xbig"
        assert result[1] == "0xmedium"
        assert result[2] == "0xsmall"

    def test_respects_limit(self, db_path):
        from polybot.indexers.cex_funding import get_untraced_wallets

        _seed_trades(db_path, [(f"0xw{i}", float(i * 100)) for i in range(10)])

        result = get_untraced_wallets(db_path, max_wallets=3)
        assert len(result) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_cex_funding.py -v -k "TestIdentify or TestInsert or TestGetUntraced"`
Expected: FAIL — `ImportError: cannot import name 'identify_cex'`

- [ ] **Step 3: Implement DB functions**

Append to `src/polybot/indexers/cex_funding.py`:

```python
# --- DB operations ---


def get_untraced_wallets(db_path: str, max_wallets: int) -> list[str]:
    """Find wallets in trades_all not yet traced in cex_funding_map."""
    from polybot.db.connection import db_read_with_retry

    def _do(con):
        rows = con.execute(
            """
            SELECT ta.proxy_wallet, SUM(ta.size_usd) as total_vol
            FROM trades_all ta
            LEFT JOIN cex_funding_map cfm
                ON ta.proxy_wallet = cfm.wallet_address
            WHERE cfm.wallet_address IS NULL
              AND ta.proxy_wallet IS NOT NULL
            GROUP BY ta.proxy_wallet
            ORDER BY total_vol DESC
            LIMIT ?
            """,
            [max_wallets],
        ).fetchall()
        return [r[0] for r in rows]

    return db_read_with_retry(db_path, _do)


def identify_cex(
    db_path: str,
    funded_by: str | None,
    funded_by_hop2: str | None,
) -> dict | None:
    """Match funding hops against cex_hot_wallets."""
    if funded_by is None:
        return None

    from polybot.db.connection import db_read_with_retry

    def _do(con):
        # Hop 1: direct hot wallet
        row = con.execute(
            "SELECT exchange_name FROM cex_hot_wallets WHERE address = ?",
            [funded_by.lower()],
        ).fetchone()
        if row:
            return {
                "cex_source": row[0],
                "method": "direct_hot_wallet",
                "deposit_address": None,
                "confidence": 1.0,
            }

        # Hop 2: via deposit address
        if funded_by_hop2 is not None:
            row = con.execute(
                "SELECT exchange_name FROM cex_hot_wallets WHERE address = ?",
                [funded_by_hop2.lower()],
            ).fetchone()
            if row:
                return {
                    "cex_source": row[0],
                    "method": "hop2_hot_wallet",
                    "deposit_address": funded_by.lower(),
                    "confidence": 0.9,
                }

        return None

    return db_read_with_retry(db_path, _do)


def insert_mapping(
    db_path: str,
    wallet: str,
    hops: dict,
    cex_result: dict | None,
) -> None:
    """Insert wallet funding mapping. ON CONFLICT DO NOTHING."""
    from polybot.db.connection import db_write_with_retry

    if cex_result:
        params = [
            wallet.lower(),
            hops["funded_by"],
            hops["funded_by_hop2"],
            cex_result["cex_source"],
            cex_result["deposit_address"],
            cex_result["confidence"],
            cex_result["method"],
        ]
    else:
        params = [
            wallet.lower(),
            hops["funded_by"],
            hops["funded_by_hop2"],
            None,
            None,
            0.0,
            None,
        ]

    def _do(con):
        con.execute(
            """
            INSERT INTO cex_funding_map (
                wallet_address, funded_by, funded_by_hop2,
                cex_source, deposit_address, confidence, method
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (wallet_address) DO NOTHING
            """,
            params,
        )

    db_write_with_retry(db_path, _do)


def update_indexer_state(
    db_path: str,
    status: str,
    count: int,
    duration_ms: int,
    error: str | None = None,
) -> None:
    """Update indexer_state for 'cex_funding'."""
    from polybot.db.connection import db_write_with_retry

    def _do(con):
        con.execute(
            """
            INSERT OR REPLACE INTO indexer_state (
                indexer_name, last_synced_at, last_run_status,
                last_run_duration_ms, ingested_count, last_error, updated_at
            ) VALUES ('cex_funding', NOW(), ?, ?, ?, ?, NOW())
            """,
            [status, duration_ms, count, error],
        )

    db_write_with_retry(db_path, _do)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_cex_funding.py -v -k "TestIdentify or TestInsert or TestGetUntraced"`
Expected: 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/polybot/indexers/cex_funding.py tests/unit/test_cex_funding.py
git commit -m "feat(M9): add cex_funding DB functions — identify_cex, insert_mapping, get_untraced"
```

---

### Task 3: `run()` orchestration + end-to-end test

**Files:**
- Modify: `src/polybot/indexers/cex_funding.py`
- Modify: `tests/unit/test_cex_funding.py`

- [ ] **Step 1: Write end-to-end test**

Append to `tests/unit/test_cex_funding.py`:

```python
class TestRun:
    def test_end_to_end(self, db_path):
        """3 wallets: 1 Binance direct, 1 Coinbase hop2, 1 no USDC."""
        from polybot.indexers.cex_funding import run

        _seed_cex_hot_wallet(db_path, "0xbinance_hw", "Binance")
        _seed_cex_hot_wallet(db_path, "0xcoinbase_hw", "Coinbase")

        _seed_trades(db_path, [
            ("0xdirect", 10000.0),
            ("0xvia_deposit", 5000.0),
            ("0xno_usdc", 3000.0),
        ])

        call_count = {"n": 0}

        def mock_post(url, **kwargs):
            body = kwargs.get("json", {})
            params = body.get("params", [{}])
            to_addr = params[0].get("toAddress", "") if params else ""
            call_count["n"] += 1

            if to_addr == "0xdirect":
                return _mock_rpc_response(_alchemy_transfers_response([
                    {"from": "0xbinance_hw", "to": "0xdirect",
                     "value": 1000.0, "blockNum": "0x1"},
                ]))
            if to_addr == "0xbinance_hw":
                return _mock_rpc_response(_alchemy_transfers_response([]))
            if to_addr == "0xvia_deposit":
                return _mock_rpc_response(_alchemy_transfers_response([
                    {"from": "0xmy_deposit", "to": "0xvia_deposit",
                     "value": 500.0, "blockNum": "0x1"},
                ]))
            if to_addr == "0xmy_deposit":
                return _mock_rpc_response(_alchemy_transfers_response([
                    {"from": "0xcoinbase_hw", "to": "0xmy_deposit",
                     "value": 5000.0, "blockNum": "0x1"},
                ]))
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
            "SELECT last_run_status FROM indexer_state "
            "WHERE indexer_name = 'cex_funding'"
        ).fetchone()
        con.close()
        assert row[0] == "success"

    def test_skips_failed_wallet(self, db_path):
        """A wallet that raises RPCError is skipped, others continue."""
        from polybot.indexers.cex_funding import run

        _seed_cex_hot_wallet(db_path, "0xbinance_hw", "Binance")
        _seed_trades(db_path, [
            ("0xgood", 10000.0),
            ("0xbad", 5000.0),
        ])

        def mock_post(url, **kwargs):
            body = kwargs.get("json", {})
            params = body.get("params", [{}])
            to_addr = params[0].get("toAddress", "") if params else ""

            if to_addr == "0xbad":
                return httpx.Response(
                    429, request=httpx.Request("POST", "http://test")
                )
            if to_addr == "0xgood":
                return _mock_rpc_response(_alchemy_transfers_response([
                    {"from": "0xbinance_hw", "to": "0xgood",
                     "value": 1000.0, "blockNum": "0x1"},
                ]))
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_cex_funding.py::TestRun -v`
Expected: FAIL — `ImportError: cannot import name 'run'`

- [ ] **Step 3: Implement `run()` and `main()`**

Append to `src/polybot/indexers/cex_funding.py`:

```python
# --- Main run ---


def run(
    db_path: str, alchemy_url: str, max_wallets: int = 100
) -> int:
    """Trace funding for untraced wallets, identify CEX sources."""
    start_time = time.monotonic()

    wallets = get_untraced_wallets(db_path, max_wallets)
    if not wallets:
        logger.info("cex_funding_no_untraced")
        duration_ms = int((time.monotonic() - start_time) * 1000)
        update_indexer_state(db_path, "success", 0, duration_ms)
        return 0

    logger.info("cex_funding_starting", untraced=len(wallets))
    cex_matched = 0
    traced = 0

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for wallet in wallets:
            try:
                hops = trace_funding_hops(client, alchemy_url, wallet)
                cex_result = identify_cex(
                    db_path, hops["funded_by"], hops["funded_by_hop2"]
                )
                insert_mapping(db_path, wallet, hops, cex_result)
                traced += 1
                if cex_result:
                    cex_matched += 1
                logger.info(
                    "cex_funding_traced",
                    wallet=wallet[:12],
                    cex=cex_result["cex_source"] if cex_result else None,
                    method=cex_result["method"] if cex_result else None,
                )
            except Exception as e:
                logger.warning(
                    "cex_funding_wallet_error",
                    wallet=wallet[:12],
                    error=str(e)[:200],
                )

    duration_ms = int((time.monotonic() - start_time) * 1000)
    update_indexer_state(db_path, "success", cex_matched, duration_ms)
    logger.info(
        "cex_funding_complete",
        traced=traced,
        cex_matched=cex_matched,
        duration_ms=duration_ms,
    )
    return cex_matched


def main():
    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    logger.info("cex_funding_indexer_starting")
    count = run(
        db_path=str(settings.DUCKDB_PATH),
        alchemy_url=settings.ALCHEMY_POLYGON_URL,
    )
    print(f"CEX funding indexer complete: {count} wallets matched to CEX")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `uv run pytest tests/unit/test_cex_funding.py -v`
Expected: All 19 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/polybot/indexers/cex_funding.py tests/unit/test_cex_funding.py
git commit -m "feat(M9): add cex_funding run() orchestration with error recovery"
```

---

### Task 4: Daemon integration

**Files:**
- Modify: `src/polybot/daemon.py:22` (imports)
- Modify: `src/polybot/daemon.py:192-201` (asyncio.gather block)

- [ ] **Step 1: Add import to daemon.py**

At line 22 of `src/polybot/daemon.py`, after the existing indexer imports, add:

```python
from polybot.indexers.cex_funding import run as run_cex_funding
```

The imports section will look like:

```python
from polybot.indexers.markets_gamma import run as run_markets
from polybot.indexers.onchain_alchemy import run as run_onchain
from polybot.indexers.proxy_factory import run as run_proxy
from polybot.indexers.cex_funding import run as run_cex_funding
from polybot.indexers.resolutions_uma import run as run_resolutions
from polybot.indexers.trades_dataapi import run_forever as run_trades
```

- [ ] **Step 2: Add scheduled indexer to asyncio.gather**

In the `asyncio.gather(...)` block, after the `onchain_alchemy` entry (line 196), add:

```python
                run_scheduled_indexer(
                    "cex_funding", run_cex_funding, 3600,
                    db_executor, initial_delay=1200,
                    db_path=db_path, alchemy_url=alchemy_url,
                ),
```

- [ ] **Step 3: Verify import works**

Run: `uv run python -c "from polybot.indexers.cex_funding import run; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest tests/unit/ -v`
Expected: All tests PASS

- [ ] **Step 5: Run lint**

Run: `uv run ruff check src/polybot/indexers/cex_funding.py src/polybot/daemon.py tests/unit/test_cex_funding.py && uv run ruff format --check src/polybot/indexers/cex_funding.py src/polybot/daemon.py tests/unit/test_cex_funding.py`
Expected: Clean

- [ ] **Step 6: Commit**

```bash
git add src/polybot/daemon.py
git commit -m "feat(M9): integrate cex_funding indexer into daemon (hourly, 20min delay)"
```

---

### Task 5: Integration test + final verification

**Files:**
- Create: `tests/integration/test_cex_funding_live.py`

- [ ] **Step 1: Write integration test**

Create `tests/integration/test_cex_funding_live.py`:

```python
"""Live integration test for CEX funding tracer.

Requires ALCHEMY_POLYGON_URL environment variable.
"""

import os

import httpx
import pytest

from polybot.indexers.cex_funding import (
    REQUEST_TIMEOUT,
    fetch_first_usdc_transfers,
    trace_funding_hops,
)

ALCHEMY_URL = os.environ.get("ALCHEMY_POLYGON_URL", "")

pytestmark = pytest.mark.skipif(
    not ALCHEMY_URL, reason="ALCHEMY_POLYGON_URL not set"
)


# Known active Tier A wallet (Domer)
TIER_A_WALLET = "0x9d84ce0306f8551e02efef1680475fc0f1dc1344"


class TestLiveFunding:
    def test_fetch_transfers(self):
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            transfers = fetch_first_usdc_transfers(
                client, ALCHEMY_URL, TIER_A_WALLET, max_count=3
            )
        assert len(transfers) > 0
        assert "from" in transfers[0]
        assert "value" in transfers[0]

    def test_trace_hops(self):
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            result = trace_funding_hops(client, ALCHEMY_URL, TIER_A_WALLET)
        assert result["funded_by"] is not None
        assert result["funded_by"].startswith("0x")
```

- [ ] **Step 2: Run integration test (if ALCHEMY_POLYGON_URL available)**

Run: `uv run pytest tests/integration/test_cex_funding_live.py -v`
Expected: PASS (or SKIP if no env var)

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/unit/ -v`
Expected: All tests PASS (202 existing + 19 new = 221 total)

- [ ] **Step 4: Run lint on all changed files**

Run: `uv run ruff check src/polybot/indexers/cex_funding.py src/polybot/daemon.py tests/unit/test_cex_funding.py tests/integration/test_cex_funding_live.py && uv run ruff format --check src/polybot/indexers/cex_funding.py src/polybot/daemon.py tests/unit/test_cex_funding.py tests/integration/test_cex_funding_live.py`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_cex_funding_live.py
git commit -m "test(M9): add live integration test for cex_funding indexer"
```
