# M10-2 — Clustering Victor (Production)

## Objective

Build wallet clusters from `shared_funded_by` signal, expose as C2 bonus feature `cluster_co_presence`. Validated in session 1: Theo 4/4, Iran 6/6, 0 false clusters in negative control.

## Architecture

Three components:
1. **Migration 009** — `wallet_clusters` + `wallet_cluster_members` tables
2. **Indexer `clustering_victor`** — daily batch job, groups wallets by `funded_by`, builds clusters
3. **C2 bonus feature** — `cluster_co_presence` counts same-cluster wallets in top-10 traders, adds +1 to score if >= 3

## Migration 009

**File:** `migrations/009_m10_wallet_clusters.sql`

```sql
CREATE TABLE IF NOT EXISTS wallet_clusters (
    cluster_id VARCHAR PRIMARY KEY,
    funded_by VARCHAR NOT NULL,
    cex_source VARCHAR,
    size INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wallet_cluster_members (
    wallet_address VARCHAR PRIMARY KEY,
    cluster_id VARCHAR NOT NULL,
    funded_by VARCHAR NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cluster_members_cluster ON wallet_cluster_members (cluster_id);
```

`cluster_id` = `hashlib.sha256(funded_by.encode()).hexdigest()[:12]` — deterministic, stable.

## Indexer: `clustering_victor.py`

**File:** `src/polybot/indexers/clustering_victor.py`

**Schedule:** daily via `run_scheduled_indexer`, `interval=86400`, `initial_delay=1800`.

### `run(db_path: str) -> int`

Algorithm:
1. Query `cex_funding_map` grouped by `funded_by`, excluding:
   - NULL `funded_by`
   - `funded_by` addresses that exist in `cex_hot_wallets` (known hot wallets are many-to-one, not clusters)
2. Filter groups: `size >= 2` (singletons not clusters) and `size <= 50` (too large = undetected hot wallet, log warning)
3. For each valid group:
   - `cluster_id = hashlib.sha256(funded_by.encode()).hexdigest()[:12]`
   - Lookup `cex_source` from any member's `cex_funding_map` row
   - Upsert into `wallet_clusters` (ON CONFLICT update size, cex_source, updated_at)
   - Upsert members into `wallet_cluster_members` (ON CONFLICT update cluster_id)
4. Update `indexer_state` for `'clustering_victor'`
5. Return number of clusters created/updated

**Connection pattern:** Direct `duckdb.connect(db_path)` (write needed), matching `insert_mapping` in cex_funding.py. Uses `db_write_with_retry` for the indexer_state update.

### `update_indexer_state(db_path, status, count, duration_ms, error=None)`

Same pattern as `cex_funding.py`.

### `main()`

Entry point for standalone execution, same pattern as cex_funding.

## Daemon Integration

**File:** `src/polybot/daemon.py`

```python
from polybot.indexers.clustering_victor import run as run_clustering

# In asyncio.gather:
run_scheduled_indexer(
    "clustering_victor",
    run_clustering,
    86400,
    db_executor,
    initial_delay=1800,
    db_path=db_path,
),
```

## C2 Feature: `cluster_co_presence`

**File:** `src/polybot/components/c2_informed_trading.py`

### New method: `compute_cluster_co_presence(self, condition_id: str) -> int`

Returns the max number of wallets from the same cluster among the top-10 traders (by volume) in the last hour. Returns 0 if < 2 from any cluster.

```sql
-- Step 1: Get top-10 traders by 1h volume
SELECT proxy_wallet
FROM trades_all
WHERE condition_id = ? AND timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
GROUP BY proxy_wallet
ORDER BY SUM(size_usd) DESC
LIMIT 10

-- Step 2: Find largest cluster overlap
SELECT cluster_id, COUNT(*) as cnt
FROM wallet_cluster_members
WHERE wallet_address IN (top10 wallets)
GROUP BY cluster_id
HAVING COUNT(*) >= 2
ORDER BY cnt DESC
LIMIT 1
```

### Score integration

This is a **bonus**, not a standard boolean feature. The 8 boolean features stay unchanged. After computing the base score:

```python
cluster_count = self.compute_cluster_co_presence(condition_id)
cluster_bonus = cluster_count >= 3
if cluster_bonus:
    score += 1
    features_passed.append("cluster_co_presence")
```

Add to `raw_values`:
```python
"cluster_co_presence": cluster_count,
```

Score label stays `/8` (the bonus is additive, not part of the denominator). Threshold stays `>= 4`.

### Alert format

If `"cluster_co_presence"` in `features_passed`:
```
  ✓ Cluster détecté : {count} wallets même source{src_str}
```
Where `src_str` is ` (Binance)` if a cex_source is found for the cluster.

To get the cex_source for the alert, query:
```sql
SELECT wc.cex_source FROM wallet_cluster_members wcm
JOIN wallet_clusters wc ON wcm.cluster_id = wc.cluster_id
WHERE wcm.wallet_address IN (top10) AND wc.cex_source IS NOT NULL
LIMIT 1
```

This can be done inside `compute_cluster_co_presence` by returning `tuple[int, str | None]` instead of just `int`.

**Updated signature:** `compute_cluster_co_presence(self, condition_id: str) -> tuple[int, str | None]`
Returns `(count, cex_source)`.

## Tests

**File:** `tests/unit/test_clustering_victor.py`

| # | Test | Verifies |
|---|------|----------|
| 1 | `test_basic_clustering` | 5 wallets, 3 share funded_by → 1 cluster size 3 |
| 2 | `test_singleton_excluded` | 1 wallet alone → no cluster |
| 3 | `test_large_cluster_skipped` | 60 wallets same funded_by → warning logged, no cluster |
| 4 | `test_hot_wallet_excluded` | funded_by = known hot wallet in cex_hot_wallets → no cluster |
| 5 | `test_idempotent` | run() twice → same cluster count, no duplicates |
| 6 | `test_cluster_id_deterministic` | Same funded_by always gives same cluster_id |

**File:** `tests/unit/test_c2_informed_trading.py` (add to existing)

| # | Test | Verifies |
|---|------|----------|
| 7 | `test_cluster_co_presence_fires` | 3 wallets from same cluster in top-10 → returns 3 |
| 8 | `test_cluster_co_presence_below_threshold` | 1 wallet from cluster → returns 0 |
| 9 | `test_cluster_bonus_in_score` | cluster_count >= 3 → score += 1, in features_passed |

## Explicitly Out of Scope

- Grid search / amount_diff / block_diff (validated unnecessary in session 1)
- Changing the C2 alert threshold from 4
- More than 2 hops of tracing
- Real-time clustering (batch is sufficient for daily refreshed funding data)
- Removing wallets from clusters (append-only, clusters only grow)
