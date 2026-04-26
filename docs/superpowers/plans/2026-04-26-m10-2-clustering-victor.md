# M10-2 Clustering Victor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build wallet clusters from `shared_funded_by` signal and expose as C2 bonus feature `cluster_co_presence`.

**Architecture:** Migration creates `wallet_clusters` + `wallet_cluster_members` tables. Daily indexer groups wallets by `funded_by` (excluding hot wallets), builds clusters of size 2–50. C2 bonus feature checks if >= 3 top-10 traders share a cluster, adding +1 to score.

**Tech Stack:** DuckDB, Python 3.12, pytest, structlog

---

## File Structure

| File | Responsibility |
|------|---------------|
| `migrations/009_m10_wallet_clusters.sql` | Create tables + index |
| `src/polybot/indexers/clustering_victor.py` | Daily batch indexer: group by funded_by, build clusters |
| `src/polybot/daemon.py` | Register clustering_victor in asyncio.gather |
| `src/polybot/components/c2_informed_trading.py` | Add `compute_cluster_co_presence` + bonus scoring |
| `tests/unit/test_clustering_victor.py` | 6 tests for indexer |
| `tests/unit/test_c2_informed_trading.py` | 3 tests for C2 integration |

---

### Task 1: Migration 009

**Files:**
- Create: `migrations/009_m10_wallet_clusters.sql`

- [ ] **Step 1: Write migration SQL**

```sql
-- M10: Wallet clustering tables

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

- [ ] **Step 2: Verify migration applies cleanly**

Run: `python -c "from polybot.db.migrations import apply_migrations; apply_migrations('/tmp/test_m009.duckdb', 'migrations'); print('OK')"`
Expected: OK (no errors)

- [ ] **Step 3: Commit**

```bash
git add migrations/009_m10_wallet_clusters.sql
git commit -m "feat(M10-2): add migration 009 — wallet_clusters tables"
```

---

### Task 2: Clustering Victor Indexer + Tests

**Files:**
- Create: `src/polybot/indexers/clustering_victor.py`
- Create: `tests/unit/test_clustering_victor.py`

- [ ] **Step 1: Write all 6 failing tests**

File: `tests/unit/test_clustering_victor.py`

```python
"""Tests for clustering_victor indexer."""

import hashlib
from pathlib import Path

import duckdb
import pytest

from polybot.db.migrations import apply_migrations


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


def _seed_funding(db_path: str, wallets: list[tuple[str, str]]):
    """Insert (wallet_address, funded_by) rows into cex_funding_map."""
    con = duckdb.connect(db_path)
    for wallet, funded_by in wallets:
        con.execute(
            """INSERT INTO cex_funding_map (wallet_address, funded_by, funded_by_hop2,
               cex_source, deposit_address, confidence, method)
               VALUES (?, ?, NULL, NULL, NULL, 0.0, NULL)
               ON CONFLICT DO NOTHING""",
            [wallet, funded_by],
        )
    con.close()


def _seed_hot_wallet(db_path: str, address: str, exchange: str = "Binance"):
    """Insert a hot wallet into cex_hot_wallets."""
    con = duckdb.connect(db_path)
    con.execute(
        "INSERT INTO cex_hot_wallets (address, exchange_name) VALUES (?, ?)",
        [address, exchange],
    )
    con.close()


class TestBasicClustering:
    def test_basic_clustering(self, db_path):
        """5 wallets, 3 share funded_by → 1 cluster size 3."""
        from polybot.indexers.clustering_victor import run

        _seed_funding(db_path, [
            ("0xaaa1", "0xfunder_a"),
            ("0xaaa2", "0xfunder_a"),
            ("0xaaa3", "0xfunder_a"),
            ("0xbbb1", "0xfunder_b"),
            ("0xccc1", "0xfunder_c"),
        ])
        count = run(db_path)
        assert count == 1

        con = duckdb.connect(db_path, read_only=True)
        clusters = con.execute("SELECT * FROM wallet_clusters").fetchall()
        assert len(clusters) == 1
        assert clusters[0][3] == 3  # size column

        members = con.execute(
            "SELECT wallet_address FROM wallet_cluster_members ORDER BY wallet_address"
        ).fetchall()
        assert [r[0] for r in members] == ["0xaaa1", "0xaaa2", "0xaaa3"]
        con.close()

    def test_singleton_excluded(self, db_path):
        """1 wallet alone → no cluster."""
        from polybot.indexers.clustering_victor import run

        _seed_funding(db_path, [("0xaaa1", "0xfunder_solo")])
        count = run(db_path)
        assert count == 0

    def test_large_cluster_skipped(self, db_path):
        """60 wallets same funded_by → warning logged, no cluster."""
        from polybot.indexers.clustering_victor import run

        wallets = [(f"0xwallet_{i:03d}", "0xfunder_big") for i in range(60)]
        _seed_funding(db_path, wallets)
        count = run(db_path)
        assert count == 0

        con = duckdb.connect(db_path, read_only=True)
        clusters = con.execute("SELECT * FROM wallet_clusters").fetchall()
        assert len(clusters) == 0
        con.close()

    def test_hot_wallet_excluded(self, db_path):
        """funded_by = known hot wallet → no cluster."""
        from polybot.indexers.clustering_victor import run

        hot = "0xhot_wallet_binance"
        _seed_hot_wallet(db_path, hot)
        _seed_funding(db_path, [
            ("0xaaa1", hot),
            ("0xaaa2", hot),
            ("0xaaa3", hot),
        ])
        count = run(db_path)
        assert count == 0

    def test_idempotent(self, db_path):
        """run() twice → same cluster count, no duplicates."""
        from polybot.indexers.clustering_victor import run

        _seed_funding(db_path, [
            ("0xaaa1", "0xfunder_a"),
            ("0xaaa2", "0xfunder_a"),
        ])
        run(db_path)
        run(db_path)

        con = duckdb.connect(db_path, read_only=True)
        clusters = con.execute("SELECT * FROM wallet_clusters").fetchall()
        assert len(clusters) == 1
        members = con.execute("SELECT * FROM wallet_cluster_members").fetchall()
        assert len(members) == 2
        con.close()

    def test_cluster_id_deterministic(self, db_path):
        """Same funded_by always gives same cluster_id."""
        from polybot.indexers.clustering_victor import run

        funded_by = "0xfunder_deterministic"
        expected_id = hashlib.sha256(funded_by.encode()).hexdigest()[:12]

        _seed_funding(db_path, [
            ("0xaaa1", funded_by),
            ("0xaaa2", funded_by),
        ])
        run(db_path)

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute("SELECT cluster_id FROM wallet_clusters").fetchone()
        assert row[0] == expected_id
        con.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_clustering_victor.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'polybot.indexers.clustering_victor')

- [ ] **Step 3: Write the indexer implementation**

File: `src/polybot/indexers/clustering_victor.py`

```python
"""Build wallet clusters from shared_funded_by signal."""

import hashlib
import time

import duckdb
import structlog

from polybot.db.connection import db_write_with_retry

logger = structlog.get_logger()

MAX_CLUSTER_SIZE = 50


def run(db_path: str) -> int:
    """Group wallets by funded_by, build clusters of size 2-50."""
    start_time = time.monotonic()

    con = duckdb.connect(db_path)

    rows = con.execute(
        """
        SELECT cfm.funded_by, COUNT(*) AS cnt,
               (SELECT cex_source FROM cex_funding_map cfm2
                WHERE cfm2.funded_by = cfm.funded_by AND cfm2.cex_source IS NOT NULL
                LIMIT 1) AS cex_source
        FROM cex_funding_map cfm
        WHERE cfm.funded_by IS NOT NULL
          AND cfm.funded_by NOT IN (SELECT address FROM cex_hot_wallets)
        GROUP BY cfm.funded_by
        HAVING COUNT(*) >= 2
        """
    ).fetchall()

    clusters_created = 0

    for funded_by, size, cex_source in rows:
        if size > MAX_CLUSTER_SIZE:
            logger.warning(
                "clustering_oversized_group",
                funded_by=funded_by[:16],
                size=size,
            )
            continue

        cluster_id = hashlib.sha256(funded_by.encode()).hexdigest()[:12]

        con.execute(
            """
            INSERT INTO wallet_clusters (cluster_id, funded_by, cex_source, size, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (cluster_id) DO UPDATE SET
                size = EXCLUDED.size,
                cex_source = EXCLUDED.cex_source,
                updated_at = CURRENT_TIMESTAMP
            """,
            [cluster_id, funded_by, cex_source, size],
        )

        members = con.execute(
            "SELECT wallet_address FROM cex_funding_map WHERE funded_by = ?",
            [funded_by],
        ).fetchall()

        for (wallet,) in members:
            con.execute(
                """
                INSERT INTO wallet_cluster_members (wallet_address, cluster_id, funded_by)
                VALUES (?, ?, ?)
                ON CONFLICT (wallet_address) DO UPDATE SET
                    cluster_id = EXCLUDED.cluster_id
                """,
                [wallet, cluster_id, funded_by],
            )

        clusters_created += 1

    con.close()

    duration_ms = int((time.monotonic() - start_time) * 1000)
    update_indexer_state(db_path, "success", clusters_created, duration_ms)
    logger.info("clustering_victor_complete", clusters=clusters_created, duration_ms=duration_ms)
    return clusters_created


def update_indexer_state(
    db_path: str,
    status: str,
    count: int,
    duration_ms: int,
    error: str | None = None,
) -> None:
    """Update indexer_state for 'clustering_victor'."""

    def _do(con):
        con.execute(
            """
            INSERT OR REPLACE INTO indexer_state (
                indexer_name, last_synced_at, last_run_status,
                last_run_duration_ms, ingested_count, last_error, updated_at
            ) VALUES ('clustering_victor', NOW(), ?, ?, ?, ?, NOW())
            """,
            [status, duration_ms, count, error],
        )

    db_write_with_retry(db_path, _do)


def main():
    from polybot.config import Settings
    from polybot.logging import setup_logging

    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    logger.info("clustering_victor_starting")
    count = run(db_path=str(settings.DUCKDB_PATH))
    print(f"Clustering Victor complete: {count} clusters")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_clustering_victor.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/polybot/indexers/clustering_victor.py tests/unit/test_clustering_victor.py
git commit -m "feat(M10-2): add clustering_victor indexer with tests"
```

---

### Task 3: C2 Bonus Feature `cluster_co_presence` + Tests

**Files:**
- Modify: `src/polybot/components/c2_informed_trading.py`
- Modify: `tests/unit/test_c2_informed_trading.py`

- [ ] **Step 1: Write 3 failing tests**

Add to `tests/unit/test_c2_informed_trading.py`:

```python
def _seed_cluster(db_path: str, cluster_id: str, funded_by: str, wallets: list[str], cex_source: str | None = None):
    """Insert a cluster with members."""
    con = duckdb.connect(db_path)
    con.execute(
        "INSERT INTO wallet_clusters (cluster_id, funded_by, cex_source, size) VALUES (?, ?, ?, ?)",
        [cluster_id, funded_by, cex_source, len(wallets)],
    )
    for w in wallets:
        con.execute(
            "INSERT INTO wallet_cluster_members (wallet_address, cluster_id, funded_by) VALUES (?, ?, ?)",
            [w, cluster_id, funded_by],
        )
    con.close()


class TestClusterCoPresence:
    def test_cluster_co_presence_fires(self, c2, db_path):
        """3 wallets from same cluster in top-10 → returns (3, cex_source)."""
        _seed_market(db_path, "cond_cluster")
        con = duckdb.connect(db_path)
        now = datetime.now(UTC)
        # Insert 5 trades: 3 from clustered wallets with high volume
        for i, wallet in enumerate(["0xw1", "0xw2", "0xw3"]):
            con.execute(
                "INSERT INTO trades_all (condition_id, proxy_wallet, size_usd, price, timestamp_ts, side) "
                "VALUES (?, ?, ?, 0.5, ?, 'BUY')",
                ["cond_cluster", wallet, 1000.0 * (i + 1), now - timedelta(minutes=10)],
            )
        # 2 non-cluster wallets
        for wallet in ["0xw4", "0xw5"]:
            con.execute(
                "INSERT INTO trades_all (condition_id, proxy_wallet, size_usd, price, timestamp_ts, side) "
                "VALUES (?, ?, ?, 0.5, ?, 'BUY')",
                ["cond_cluster", wallet, 100.0, now - timedelta(minutes=10)],
            )
        con.close()

        _seed_cluster(db_path, "clust_abc", "0xfunder_x", ["0xw1", "0xw2", "0xw3"], "Binance")

        count, source = c2.compute_cluster_co_presence("cond_cluster")
        assert count == 3
        assert source == "Binance"

    def test_cluster_co_presence_below_threshold(self, c2, db_path):
        """1 wallet from cluster in top-10 → returns (0, None)."""
        _seed_market(db_path, "cond_low")
        con = duckdb.connect(db_path)
        now = datetime.now(UTC)
        # Only 1 clustered wallet
        con.execute(
            "INSERT INTO trades_all (condition_id, proxy_wallet, size_usd, price, timestamp_ts, side) "
            "VALUES (?, ?, ?, 0.5, ?, 'BUY')",
            ["cond_low", "0xw1", 1000.0, now - timedelta(minutes=10)],
        )
        for wallet in ["0xw4", "0xw5", "0xw6"]:
            con.execute(
                "INSERT INTO trades_all (condition_id, proxy_wallet, size_usd, price, timestamp_ts, side) "
                "VALUES (?, ?, ?, 0.5, ?, 'BUY')",
                ["cond_low", wallet, 500.0, now - timedelta(minutes=10)],
            )
        con.close()

        _seed_cluster(db_path, "clust_xyz", "0xfunder_y", ["0xw1", "0xw99"], None)

        count, source = c2.compute_cluster_co_presence("cond_low")
        assert count == 0
        assert source is None

    def test_cluster_bonus_in_score(self, c2, db_path):
        """cluster_count >= 3 → score += 1, in features_passed."""
        _seed_market(db_path, "cond_bonus", volume_24h=100.0, volume_cumulative=10_000.0)
        con = duckdb.connect(db_path)
        now = datetime.now(UTC)
        # 4 wallets from same cluster with enough volume to trigger other features
        for i, wallet in enumerate(["0xc1", "0xc2", "0xc3", "0xc4"]):
            con.execute(
                "INSERT INTO trades_all (condition_id, proxy_wallet, size_usd, price, timestamp_ts, side) "
                "VALUES (?, ?, ?, 0.5, ?, 'BUY')",
                ["cond_bonus", wallet, 5000.0 * (i + 1), now - timedelta(minutes=5)],
            )
        con.close()

        _seed_cluster(db_path, "clust_big", "0xfunder_z", ["0xc1", "0xc2", "0xc3", "0xc4"], "OKX")

        result = c2.compute_score("cond_bonus")
        assert "cluster_co_presence" in result["features_passed"]
        assert result["raw_values"]["cluster_co_presence"] == 4
        # Score includes the bonus
        base_features_count = sum(1 for k, v in result["features"].items() if v)
        assert result["score"] == base_features_count + 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_c2_informed_trading.py::TestClusterCoPresence -v`
Expected: FAIL (AttributeError: 'InformedTradingDetector' has no attribute 'compute_cluster_co_presence')

- [ ] **Step 3: Add `compute_cluster_co_presence` method to `InformedTradingDetector`**

Add after `compute_shared_cex_deposit` method (after line 319 in `c2_informed_trading.py`):

```python
    def compute_cluster_co_presence(self, condition_id: str) -> tuple[int, str | None]:
        """Max wallets from same cluster among top-10 traders by 1h volume."""
        con = db_connect(self.db_path, read_only=True)

        # Step 1: Get top-10 traders by 1h volume
        top10_rows = con.execute(
            """
            SELECT proxy_wallet
            FROM trades_all
            WHERE condition_id = ? AND timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
            GROUP BY proxy_wallet
            ORDER BY SUM(size_usd) DESC
            LIMIT 10
            """,
            [condition_id],
        ).fetchall()

        if not top10_rows:
            con.close()
            return 0, None

        top10 = [r[0] for r in top10_rows]
        placeholders = ", ".join(["?"] * len(top10))

        # Step 2: Find largest cluster overlap
        row = con.execute(
            f"""
            SELECT cluster_id, COUNT(*) as cnt
            FROM wallet_cluster_members
            WHERE wallet_address IN ({placeholders})
            GROUP BY cluster_id
            HAVING COUNT(*) >= 2
            ORDER BY cnt DESC
            LIMIT 1
            """,
            top10,
        ).fetchone()

        if not row:
            con.close()
            return 0, None

        cluster_id, count = row[0], int(row[1])

        # Get cex_source for this cluster
        src_row = con.execute(
            "SELECT cex_source FROM wallet_clusters WHERE cluster_id = ? AND cex_source IS NOT NULL",
            [cluster_id],
        ).fetchone()
        con.close()

        cex_source = src_row[0] if src_row else None
        return count, cex_source
```

- [ ] **Step 4: Update `compute_score` to include cluster bonus**

In `compute_score` method, after `score = sum(features.values())` and `features_passed = [...]` (around line 356), add the cluster bonus logic:

```python
        # Cluster co-presence bonus (not part of /8 denominator)
        cluster_count, cluster_source = self.compute_cluster_co_presence(condition_id)
        cluster_bonus = cluster_count >= 3
        if cluster_bonus:
            score += 1
            features_passed.append("cluster_co_presence")

        raw_values["cluster_co_presence"] = cluster_count
        raw_values["cluster_co_presence_source"] = cluster_source
```

The full updated return block becomes:

```python
        score = sum(features.values())
        features_passed = [k for k, v in features.items() if v]

        # Cluster co-presence bonus (not part of /8 denominator)
        cluster_count, cluster_source = self.compute_cluster_co_presence(condition_id)
        cluster_bonus = cluster_count >= 3
        if cluster_bonus:
            score += 1
            features_passed.append("cluster_co_presence")

        raw_values["cluster_co_presence"] = cluster_count
        raw_values["cluster_co_presence_source"] = cluster_source

        return {
            "score": score,
            "features": features,
            "features_passed": features_passed,
            "raw_values": raw_values,
        }
```

- [ ] **Step 5: Update `_format_alert` to display cluster line**

In `_format_alert`, add a case for `cluster_co_presence` in the feature_lines loop (after the `shared_cex_deposit` case):

```python
            elif f == "cluster_co_presence":
                cl_src = raw.get("cluster_co_presence_source", "")
                cl_str = f" ({cl_src})" if cl_src else ""
                feature_lines.append(
                    f"  ✓ Cluster détecté : {raw['cluster_co_presence']} wallets même source{cl_str}"
                )
```

- [ ] **Step 6: Run all C2 tests**

Run: `pytest tests/unit/test_c2_informed_trading.py -v`
Expected: All tests pass (existing 32 + 3 new = 35)

- [ ] **Step 7: Run full test suite**

Run: `pytest tests/unit/ -v --tb=short`
Expected: All pass (226 existing + 6 clustering + 3 C2 = 235)

- [ ] **Step 8: Commit**

```bash
git add src/polybot/components/c2_informed_trading.py tests/unit/test_c2_informed_trading.py
git commit -m "feat(M10-2): add cluster_co_presence bonus feature to C2"
```

---

### Task 4: Daemon Integration

**Files:**
- Modify: `src/polybot/daemon.py`

- [ ] **Step 1: Add import**

At the top of `daemon.py`, after the `from polybot.indexers.cex_funding import run as run_cex_funding` line:

```python
from polybot.indexers.clustering_victor import run as run_clustering
```

- [ ] **Step 2: Add to asyncio.gather**

In the `asyncio.gather(...)` block, after the `cex_funding` entry (after line 226), add:

```python
                run_scheduled_indexer(
                    "clustering_victor",
                    run_clustering,
                    86400,
                    db_executor,
                    initial_delay=1800,
                    db_path=db_path,
                ),
```

- [ ] **Step 3: Run daemon import check**

Run: `python -c "from polybot.daemon import main; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add src/polybot/daemon.py
git commit -m "feat(M10-2): register clustering_victor in daemon (daily, 30min delay)"
```

---

## VPS Deployment

After all tasks pass locally:

```bash
# 1. Sync code
rsync -avz --exclude='.venv' --exclude='data/' --exclude='.git/' --exclude='__pycache__/' \
  ./ root@<VPS_IP>:/root/polybot/

# 2. SSH in, stop daemon, apply migration, restart
ssh root@<VPS_IP> << 'EOF'
cd /root/polybot
systemctl stop polybot
source .venv/bin/activate
python -c "from polybot.db.migrations import apply_migrations; apply_migrations('data/polybot.duckdb', 'migrations')"
python -m polybot.indexers.clustering_victor  # first run
systemctl start polybot
# Verify
journalctl -u polybot --since "1 min ago" | grep clustering
EOF
```
