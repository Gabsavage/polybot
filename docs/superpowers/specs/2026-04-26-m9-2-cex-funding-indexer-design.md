# M9-2 — CEX Funding Indexer

## Objective

Trace 2-hop USDC funding paths for active wallets on Polygon to identify CEX sources. This is the core signal for `shared_cex_deposit_ratio` — wallets sharing the same CEX deposit address are likely the same user (cluster detection).

## Architecture

Single module `src/polybot/indexers/cex_funding.py` with top-level functions following the existing indexer pattern (onchain_alchemy, proxy_factory). Scheduled hourly via `run_scheduled_indexer` in daemon.py.

**Data flow:**
1. Query `trades_all LEFT JOIN cex_funding_map` to find untraced wallets (by volume DESC)
2. For each wallet, call Alchemy `alchemy_getAssetTransfers` to find first USDC inflows (hop 1)
3. For the funder address, repeat to find hop 2
4. Match hop 1/hop 2 against `cex_hot_wallets` table
5. Store result in `cex_funding_map` (including "no USDC funding" to avoid re-tracing)

## Functions

### `get_untraced_wallets(db_path: str, max_wallets: int) -> list[str]`

```sql
SELECT DISTINCT ta.proxy_wallet, SUM(ta.size_usd) as total_vol
FROM trades_all ta
LEFT JOIN cex_funding_map cfm ON ta.proxy_wallet = cfm.wallet_address
WHERE cfm.wallet_address IS NULL AND ta.proxy_wallet IS NOT NULL
GROUP BY ta.proxy_wallet
ORDER BY total_vol DESC
LIMIT ?
```

Uses `db_read_with_retry`. Returns wallet addresses sorted by volume (highest-value wallets first).

### `rpc_call(client, url, method, params) -> dict`

Local copy of the RPC helper from proxy_factory.py (no shared import to avoid coupling). Retry on 429/5xx with exponential backoff (2^attempt seconds), timeout 15s, max 5 retries. Raises `RPCError` on exhaustion.

### `fetch_first_usdc_transfers(client: httpx.Client, alchemy_url: str, wallet: str, max_count: int = 5) -> list[dict]`

Calls `alchemy_getAssetTransfers` with:
- `toAddress`: wallet
- `category`: `["erc20"]`
- `contractAddresses`: both USDC addresses on Polygon
- `order`: `"asc"` (earliest first)
- `maxCount`: hex(max_count)
- `withMetadata`: True

Returns list of transfer dicts with `from`, `to`, `value`, `blockNum`. Returns empty list if no transfers found.

**USDC addresses:**
- Native USDC: `0x3c499c542cef5e3811e1192ce70d8cc03d5c3359`
- USDC.e bridged: `0x2791bca1f2de4661ed88a30c99a7a9449aa84174`

### `trace_funding_hops(client: httpx.Client, alchemy_url: str, wallet: str) -> dict`

1. Call `fetch_first_usdc_transfers(wallet)` → take first transfer's `from` = `funded_by`
2. If `funded_by` found, call `fetch_first_usdc_transfers(funded_by)` → take first transfer's `from` = `funded_by_hop2`
3. Return `{"funded_by": str | None, "funded_by_hop2": str | None}`

Sleep 100ms between calls for rate limiting.

### `identify_cex(db_path: str, funded_by: str | None, funded_by_hop2: str | None) -> dict | None`

Uses `db_read_with_retry`. Checks in order:

1. **Hop 1 direct:** `SELECT exchange_name FROM cex_hot_wallets WHERE address = funded_by.lower()`
   - Match → `{cex_source, method='direct_hot_wallet', deposit_address=None, confidence=1.0}`
2. **Hop 2 via deposit:** `SELECT exchange_name FROM cex_hot_wallets WHERE address = funded_by_hop2.lower()`
   - Match → `{cex_source, method='hop2_hot_wallet', deposit_address=funded_by.lower(), confidence=0.9}`
3. No match → `None`

### `insert_mapping(db_path: str, wallet: str, hops: dict, cex_result: dict | None) -> None`

Uses `db_write_with_retry`. Inserts into `cex_funding_map`:
- If `cex_result` is not None: use its fields
- If `cex_result` is None but hops exist: `method=NULL, confidence=0.0, cex_source=NULL`
- If no USDC transfers at all: `method=NULL, confidence=0.0, all fields NULL`

Note: `method` has a CHECK constraint allowing only `'direct_hot_wallet'`, `'hop2_hot_wallet'`, `'deposit_address_match'`. NULL passes the CHECK and signals "no CEX match" or "no USDC funding". We distinguish the two cases via `funded_by`: NULL = no USDC transfers, non-NULL = USDC transfers but no CEX match.

`ON CONFLICT (wallet_address) DO NOTHING` — append-only, never overwrite existing traces.

### `update_indexer_state(db_path: str, status: str, count: int, duration_ms: int, error: str | None = None) -> None`

Pattern from onchain_alchemy.py. INSERT OR REPLACE into `indexer_state` with `indexer_name='cex_funding'`.

### `run(db_path: str, alchemy_url: str, max_wallets: int = 100) -> int`

Main orchestration:
1. `get_untraced_wallets(db_path, max_wallets)`
2. Open `httpx.Client(timeout=15.0)`
3. For each wallet:
   - `trace_funding_hops(client, alchemy_url, wallet)`
   - `identify_cex(db_path, funded_by, funded_by_hop2)`
   - `insert_mapping(db_path, wallet, hops, cex_result)`
   - Log result
   - On exception: log warning, skip wallet, continue
4. `update_indexer_state(db_path, status, count, duration_ms, error)`
5. Return count of wallets mapped with a CEX source

## Daemon Integration

Add to `daemon.py`:

```python
from polybot.indexers.cex_funding import run as run_cex_funding

# In asyncio.gather, after onchain_alchemy:
run_scheduled_indexer(
    "cex_funding", run_cex_funding, 3600,
    db_executor, initial_delay=1200,
    db_path=db_path, alchemy_url=alchemy_url,
),
```

`initial_delay=1200` (20 min) so trades_all and proxy_factory have populated data first. `max_wallets` defaults to 100 in the `run` function signature.

## Rate Limiting

- 2 Alchemy calls per wallet (hop 1 + hop 2), ~300 CU each
- 100ms sleep between calls
- 100 wallets/run = ~30K CU, well within free tier
- Exponential backoff on 429 (handled by rpc_call)

## Error Handling

- **No USDC transfers:** Store with `method=NULL, funded_by=NULL` to skip on next run
- **Alchemy timeout/error:** Skip wallet, continue to next (logged as warning)
- **DuckDB lock:** Handled by `db_write_with_retry` with exponential backoff
- **All wallets fail:** `update_indexer_state` with status='failed' and error message

## Tests

### Unit tests (`tests/unit/test_cex_funding.py`)

All Alchemy calls mocked via monkeypatch on `rpc_call`.

| # | Test | What it verifies |
|---|------|-----------------|
| 1 | `test_identify_cex_direct_hot_wallet` | funded_by matches cex_hot_wallets → method='direct_hot_wallet', confidence=1.0 |
| 2 | `test_identify_cex_hop2` | funded_by_hop2 matches → method='hop2_hot_wallet', deposit_address set, confidence=0.9 |
| 3 | `test_identify_cex_no_match` | Neither hop matches → returns None |
| 4 | `test_trace_no_usdc_funding` | Empty Alchemy response → funded_by=NULL, method=NULL, row still inserted |
| 5 | `test_insert_mapping_idempotent` | Same wallet twice → 1 row (ON CONFLICT DO NOTHING) |
| 6 | `test_get_untraced_wallets` | 10 in trades_all, 3 already in cex_funding_map → returns 7 |
| 7 | `test_get_untraced_wallets_priority` | Wallets returned by volume DESC |
| 8 | `test_run_end_to_end` | Mock Alchemy, 3 wallets → correct cex_funding_map rows |

### Integration test (`tests/integration/test_cex_funding_live.py`)

Skip if `ALCHEMY_POLYGON_URL` not set. Trace 1 known Tier A wallet, verify hop 1 returns a result.

## Explicitly out of scope

- C2 modifications / shared_cex_deposit_ratio (M9 prompt 3)
- More than 2 hops of tracing
- MATIC/ETH transfer tracing (USDC only)
- VPS deployment
