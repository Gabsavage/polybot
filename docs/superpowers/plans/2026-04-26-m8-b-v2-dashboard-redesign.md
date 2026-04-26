# M8-B v2 Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refonte complète du frontend dashboard Polybot avec un design "trading terminal" (palette sombre + accents orange/violet, glass effect, Inter font) et ajout de 3 nouveaux endpoints backend (wallet detail, wallet trades, clusters) + modification de `/api/markets/hot` pour ranker par score C2.

**Architecture:** Backend FastAPI conservé (uvicorn embarqué dans `polybot-bot.service`), 3 endpoints ajoutés + 1 modifié. Frontend `dashboard/src/` wipé et reconstruit avec SWR + Tailwind v4 (`@theme`) + lucide-react + Inter via Google Fonts. Caddy basicauth gère l'auth, aucune logique React. Workflow exécution dans un worktree git isolé.

**Tech Stack:** FastAPI + DuckDB (backend), React 19 + Vite 6 + Tailwind CSS v4 + SWR + lucide-react + Recharts + React Router 7 (frontend). Tests : pytest + duckdb in-memory pour backend, vérification manuelle pour frontend.

**Spec:** `docs/superpowers/specs/2026-04-26-m8-b-v2-dashboard-redesign-design.md`

---

## Phase 0 — Setup

### Task 1: Create worktree and switch to it

**Files:**
- New worktree: `worktrees/m8-b-v2-dashboard/`

- [ ] **Step 1: Verify clean working tree**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git status
```

Expected: working tree clean (the spec was already committed).

- [ ] **Step 2: Create worktree**

```bash
git worktree add worktrees/m8-b-v2-dashboard -b m8-b-v2-dashboard
```

Expected: `Preparing worktree (new branch 'm8-b-v2-dashboard') HEAD is now at <sha>`.

- [ ] **Step 3: Switch to worktree for all subsequent work**

```bash
cd worktrees/m8-b-v2-dashboard
pwd
```

Expected: `/Users/gabsav/Documents/Polycasquette/Code/worktrees/m8-b-v2-dashboard`.

**All subsequent tasks run from this worktree directory.**

---

## Phase 1 — Backend: extend test fixture

### Task 2: Add wallet_clusters + cex_funding_map tables to test fixture

**Files:**
- Modify: `tests/unit/test_dashboard_api.py:75-196` (the `db_path` fixture)

The existing fixture creates 8 tables but is missing `wallet_clusters`, `wallet_cluster_members`, `cex_hot_wallets`, `cex_funding_map`. Without these, the new wallet-detail and clusters endpoint tests can't run. Add them.

- [ ] **Step 1: Locate the fixture**

Find the `db_path` fixture in `tests/unit/test_dashboard_api.py` (starts around line 76). It currently ends with the `resolution_risk_cache` table creation.

- [ ] **Step 2: Append the 4 new table creates inside the fixture**

Just before `con.close()` and `return path` (around line 195), insert :

```python
    con.execute("""
        CREATE TABLE cex_hot_wallets (
            address VARCHAR PRIMARY KEY,
            exchange_name VARCHAR NOT NULL,
            label VARCHAR,
            verified BOOLEAN DEFAULT TRUE,
            source VARCHAR,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE cex_funding_map (
            wallet_address VARCHAR PRIMARY KEY,
            funded_by VARCHAR,
            funded_by_hop2 VARCHAR,
            cex_source VARCHAR,
            deposit_address VARCHAR,
            confidence DECIMAL(3,2),
            method VARCHAR,
            traced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE wallet_clusters (
            cluster_id VARCHAR PRIMARY KEY,
            funded_by VARCHAR NOT NULL,
            cex_source VARCHAR,
            size INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE wallet_cluster_members (
            wallet_address VARCHAR PRIMARY KEY,
            cluster_id VARCHAR NOT NULL,
            funded_by VARCHAR NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
```

- [ ] **Step 3: Run existing tests to verify nothing broke**

```bash
uv run pytest tests/unit/test_dashboard_api.py -v
```

Expected: 7 existing tests still PASS (no regression).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_dashboard_api.py
git commit -m "test(M8-B v2): add cex_funding + cluster tables to dashboard test fixture"
```

---

## Phase 2 — Backend: GET /api/clusters

### Task 3: TDD `/api/clusters`

**Files:**
- Modify: `tests/unit/test_dashboard_api.py` (append new test class)
- Modify: `src/polybot/dashboard/api.py` (add new endpoint)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_dashboard_api.py` :

```python
class TestClustersEndpoint:
    def test_clusters_ordered_by_tier_a_count_desc(self, client, db_path):
        con = duckdb.connect(db_path)
        # cluster_b: 5 members (1 Tier A) ; cluster_a: 3 members (2 Tier A)
        con.execute(
            "INSERT INTO wallet_clusters (cluster_id, funded_by, cex_source, size) "
            "VALUES ('cluster_a', '0xfundA', 'Binance', 3), "
            "       ('cluster_b', '0xfundB', 'Coinbase', 5)"
        )
        # 2 Tier A wallets in cluster_a, 1 in cluster_b
        for i in range(3):
            tier = "A" if i < 2 else "B"
            con.execute(
                "INSERT INTO tracked_wallets (address, tier, active) VALUES (?, ?, TRUE)",
                [f"0xa_member_{i}", tier],
            )
            con.execute(
                "INSERT INTO wallet_cluster_members (wallet_address, cluster_id, funded_by) "
                "VALUES (?, 'cluster_a', '0xfundA')",
                [f"0xa_member_{i}"],
            )
        for i in range(5):
            tier = "A" if i < 1 else "B"
            con.execute(
                "INSERT INTO tracked_wallets (address, tier, active) VALUES (?, ?, TRUE)",
                [f"0xb_member_{i}", tier],
            )
            con.execute(
                "INSERT INTO wallet_cluster_members (wallet_address, cluster_id, funded_by) "
                "VALUES (?, 'cluster_b', '0xfundB')",
                [f"0xb_member_{i}"],
            )
        con.close()

        resp = client.get("/api/clusters")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # cluster_a first (2 Tier A) before cluster_b (1 Tier A)
        assert data[0]["cluster_id"] == "cluster_a"
        assert data[0]["tier_a_count"] == 2
        assert data[0]["member_count"] == 3
        assert data[0]["cex_source"] == "Binance"
        assert data[1]["cluster_id"] == "cluster_b"
        assert data[1]["tier_a_count"] == 1
        assert data[1]["member_count"] == 5
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestClustersEndpoint -v
```

Expected: FAIL with 404 (endpoint not implemented yet).

- [ ] **Step 3: Implement endpoint**

Append to `src/polybot/dashboard/api.py`:

```python
@app.get("/api/clusters")
def get_clusters(con: DB):
    rows = con.execute(
        "SELECT c.cluster_id, c.funded_by, c.cex_source, c.size, c.created_at, "
        "       COUNT(m.wallet_address) AS member_count, "
        "       COUNT(*) FILTER (WHERE w.tier = 'A') AS tier_a_count "
        "FROM wallet_clusters c "
        "LEFT JOIN wallet_cluster_members m ON c.cluster_id = m.cluster_id "
        "LEFT JOIN tracked_wallets w ON m.wallet_address = w.address "
        "GROUP BY c.cluster_id, c.funded_by, c.cex_source, c.size, c.created_at "
        "ORDER BY tier_a_count DESC, c.size DESC "
        "LIMIT 100"
    ).fetchall()
    return [
        {
            "cluster_id": r[0],
            "funded_by": r[1],
            "cex_source": r[2],
            "size": r[3],
            "created_at": str(r[4]) if r[4] else None,
            "member_count": r[5],
            "tier_a_count": r[6],
        }
        for r in rows
    ]
```

- [ ] **Step 4: Run test, verify it passes**

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestClustersEndpoint -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/polybot/dashboard/api.py tests/unit/test_dashboard_api.py
git commit -m "feat(M8-B v2): add GET /api/clusters endpoint"
```

---

## Phase 3 — Backend: GET /api/wallets/{address}

### Task 4: TDD `/api/wallets/{address}` (404 case)

**Files:**
- Modify: `tests/unit/test_dashboard_api.py`
- Modify: `src/polybot/dashboard/api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_dashboard_api.py` :

```python
class TestWalletDetailEndpoint:
    def test_returns_404_when_wallet_not_found(self, client):
        resp = client.get("/api/wallets/0xDEADBEEF")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestWalletDetailEndpoint::test_returns_404_when_wallet_not_found -v
```

Expected: FAIL with 404 because the route doesn't exist yet → FastAPI returns... wait, actually FastAPI returns 404 by default for missing routes, so the test might pass falsely. Verify the failure mode is "Not Found" with empty body, then we'll change to a real 404 from our handler.

If it passes incorrectly, change the assertion to:
```python
assert resp.status_code == 404
assert resp.json()["detail"] == "Wallet not found"
```

This will fail with a different message until we implement.

- [ ] **Step 3: Implement endpoint stub**

Append to `src/polybot/dashboard/api.py`:

```python
from fastapi import HTTPException

@app.get("/api/wallets/{address}")
def get_wallet_detail(con: DB, address: str):
    row = con.execute(
        "SELECT w.address, w.notes, w.tier, w.active, w.tier_a_confidence, "
        "       w.honeypot_flag, w.added_at, w.source, "
        "       COUNT(t.transaction_hash) AS trades_total, "
        "       MAX(t.timestamp_ts) AS last_trade, "
        "       AVG(t.size_usd) AS avg_trade_size, "
        "       COALESCE(SUM(t.size_usd), 0) AS total_volume "
        "FROM tracked_wallets w "
        "LEFT JOIN trades t ON w.address = t.proxy_wallet "
        "WHERE w.address = ? "
        "GROUP BY w.address, w.notes, w.tier, w.active, w.tier_a_confidence, "
        "         w.honeypot_flag, w.added_at, w.source",
        [address],
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return {"address": row[0]}  # incomplete — will be filled in next task
```

- [ ] **Step 4: Run test, verify it passes**

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestWalletDetailEndpoint -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/polybot/dashboard/api.py tests/unit/test_dashboard_api.py
git commit -m "feat(M8-B v2): add GET /api/wallets/{address} stub with 404"
```

### Task 5: TDD `/api/wallets/{address}` full response

**Files:**
- Modify: `tests/unit/test_dashboard_api.py`
- Modify: `src/polybot/dashboard/api.py`

- [ ] **Step 1: Write the failing test**

Append to `TestWalletDetailEndpoint` :

```python
    def test_returns_full_wallet_with_metrics(self, client, db_path):
        _seed_alerts(db_path)  # this seeds 0xwallet_0..2 with 4 trades each + alerts
        # Set notes (= name) for wallet 0
        con = duckdb.connect(db_path)
        con.execute("UPDATE tracked_wallets SET notes='TestUser' WHERE address='0xwallet_0'")
        con.close()

        resp = client.get("/api/wallets/0xwallet_0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["address"] == "0xwallet_0"
        assert data["name"] == "TestUser"
        assert data["tier"] == "A"
        assert data["active"] is True
        assert data["trades_total"] == 4
        # 0xwallet_0 has 1 alert (a1) which is correct → resolved=1, correct=1, pnl=25.0
        assert data["resolved"] == 1
        assert data["correct"] == 1
        assert data["win_rate"] == pytest.approx(1.0, abs=0.01)
        assert data["pnl"] == pytest.approx(25.0, abs=0.01)
        assert isinstance(data["pnl_series"], list)
        assert data["cex_funding"] is None
        assert data["cluster"] is None

    def test_includes_cex_funding_when_present(self, client, db_path):
        _seed_alerts(db_path)
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO cex_funding_map "
            "(wallet_address, cex_source, deposit_address, confidence, method) "
            "VALUES ('0xwallet_0', 'Binance', '0xdeposit_abc', 0.95, 'deposit_address_match')"
        )
        con.close()
        resp = client.get("/api/wallets/0xwallet_0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cex_funding"] is not None
        assert data["cex_funding"]["cex_source"] == "Binance"
        assert data["cex_funding"]["confidence"] == pytest.approx(0.95)
        assert data["cex_funding"]["method"] == "deposit_address_match"

    def test_includes_cluster_when_member(self, client, db_path):
        _seed_alerts(db_path)
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO wallet_clusters (cluster_id, funded_by, cex_source, size) "
            "VALUES ('clu_xyz', '0xfundX', 'Binance', 12)"
        )
        con.execute(
            "INSERT INTO wallet_cluster_members (wallet_address, cluster_id, funded_by) "
            "VALUES ('0xwallet_0', 'clu_xyz', '0xfundX')"
        )
        con.close()
        resp = client.get("/api/wallets/0xwallet_0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cluster"] is not None
        assert data["cluster"]["cluster_id"] == "clu_xyz"
        assert data["cluster"]["size"] == 12
        assert data["cluster"]["cex_source"] == "Binance"
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestWalletDetailEndpoint -v
```

Expected: 3 new tests FAIL (response missing fields).

- [ ] **Step 3: Replace stub with full implementation**

Replace the `get_wallet_detail` function in `src/polybot/dashboard/api.py` :

```python
@app.get("/api/wallets/{address}")
def get_wallet_detail(con: DB, address: str):
    # Bloc 1 : info wallet + métriques trades
    row = con.execute(
        "SELECT w.address, w.notes, w.tier, w.active, w.tier_a_confidence, "
        "       w.honeypot_flag, w.added_at, w.source, "
        "       COUNT(t.transaction_hash) AS trades_total, "
        "       MAX(t.timestamp_ts) AS last_trade, "
        "       AVG(t.size_usd) AS avg_trade_size, "
        "       COALESCE(SUM(t.size_usd), 0) AS total_volume "
        "FROM tracked_wallets w "
        "LEFT JOIN trades t ON w.address = t.proxy_wallet "
        "WHERE w.address = ? "
        "GROUP BY w.address, w.notes, w.tier, w.active, w.tier_a_confidence, "
        "         w.honeypot_flag, w.added_at, w.source",
        [address],
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Bloc 2 : alertes résolues + win rate + Shadow P&L
    perf = con.execute(
        "SELECT "
        " COUNT(*) FILTER (WHERE ao.resolution_outcome NOT IN ('PENDING')) AS resolved, "
        " COUNT(*) FILTER (WHERE ao.was_direction_correct = TRUE) AS correct, "
        " SUM(ao.shadow_pnl_simulated) FILTER (WHERE ao.resolution_outcome NOT IN ('PENDING')) AS pnl "
        "FROM alerts a "
        "LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id "
        "WHERE a.wallet_address = ?",
        [address],
    ).fetchone()
    resolved = perf[0] or 0
    correct = perf[1] or 0
    pnl = float(perf[2]) if perf[2] is not None else None
    win_rate = (correct / resolved) if resolved > 0 else None

    # Bloc 3 : pnl_series (90 derniers jours, agrégé par jour puis cumulé)
    pnl_series_rows = con.execute(
        "WITH daily AS ("
        "  SELECT DATE_TRUNC('day', a.emitted_at)::DATE AS day, "
        "         SUM(ao.shadow_pnl_simulated) AS daily_pnl "
        "  FROM alerts a "
        "  JOIN alert_outcomes ao ON a.alert_id = ao.alert_id "
        "  WHERE a.wallet_address = ? "
        "    AND ao.resolution_outcome NOT IN ('PENDING') "
        "    AND a.emitted_at >= CURRENT_DATE - INTERVAL '90 DAY' "
        "  GROUP BY day"
        ") "
        "SELECT day, SUM(daily_pnl) OVER (ORDER BY day) AS cum_pnl "
        "FROM daily ORDER BY day",
        [address],
    ).fetchall()

    # Bloc 4 : cex_funding
    cex_row = con.execute(
        "SELECT cex_source, deposit_address, confidence, method "
        "FROM cex_funding_map WHERE wallet_address = ?",
        [address],
    ).fetchone()

    # Bloc 5 : cluster info
    cluster_row = con.execute(
        "SELECT m.cluster_id, c.size, c.funded_by, c.cex_source "
        "FROM wallet_cluster_members m "
        "JOIN wallet_clusters c ON m.cluster_id = c.cluster_id "
        "WHERE m.wallet_address = ?",
        [address],
    ).fetchone()

    return {
        "address": row[0],
        "name": row[1],
        "tier": row[2],
        "active": row[3],
        "tier_a_confidence": float(row[4]) if row[4] is not None else None,
        "honeypot_flag": row[5],
        "added_at": str(row[6]) if row[6] else None,
        "source": row[7],
        "trades_total": row[8] or 0,
        "last_trade": str(row[9]) if row[9] else None,
        "avg_trade_size": float(row[10]) if row[10] is not None else None,
        "total_volume": float(row[11]) if row[11] is not None else 0.0,
        "resolved": resolved,
        "correct": correct,
        "pnl": pnl,
        "win_rate": float(win_rate) if win_rate is not None else None,
        "pnl_series": [
            {"day": str(r[0]), "cum_pnl": float(r[1]) if r[1] is not None else 0.0}
            for r in pnl_series_rows
        ],
        "cex_funding": (
            {
                "cex_source": cex_row[0],
                "deposit_address": cex_row[1],
                "confidence": float(cex_row[2]) if cex_row[2] is not None else None,
                "method": cex_row[3],
            }
            if cex_row
            else None
        ),
        "cluster": (
            {
                "cluster_id": cluster_row[0],
                "size": cluster_row[1],
                "funded_by": cluster_row[2],
                "cex_source": cluster_row[3],
            }
            if cluster_row
            else None
        ),
    }
```

- [ ] **Step 4: Run all dashboard tests**

```bash
uv run pytest tests/unit/test_dashboard_api.py -v
```

Expected: all 4 wallet detail tests PASS, plus all existing tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add src/polybot/dashboard/api.py tests/unit/test_dashboard_api.py
git commit -m "feat(M8-B v2): full GET /api/wallets/{address} with cex/cluster"
```

---

## Phase 4 — Backend: GET /api/wallets/{address}/trades

### Task 6: TDD wallet trades

**Files:**
- Modify: `tests/unit/test_dashboard_api.py`
- Modify: `src/polybot/dashboard/api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_dashboard_api.py` :

```python
class TestWalletTradesEndpoint:
    def test_returns_recent_trades_for_wallet(self, client, db_path):
        con = duckdb.connect(db_path)
        # 1 wallet, 5 trades, descending timestamp
        con.execute(
            "INSERT INTO tracked_wallets (address, tier, active) "
            "VALUES ('0xWA', 'A', TRUE)"
        )
        con.execute(
            "INSERT INTO markets (condition_id, title, slug, active) "
            "VALUES ('cond_z', 'Market Z', 'market-z', TRUE)"
        )
        for i in range(5):
            con.execute(
                "INSERT INTO trades "
                "(transaction_hash, proxy_wallet, condition_id, asset_id, "
                " side, size_usd, price, timestamp_unix, timestamp_ts) "
                "VALUES (?, '0xWA', 'cond_z', 'a_z', 'YES', 100, 0.5, ?, ?)",
                [f"tx_{i}", 1700000000 + i, f"2026-04-{20 + i:02d} 10:00:00"],
            )
        con.close()

        resp = client.get("/api/wallets/0xWA/trades?limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # Most recent first
        assert data[0]["transaction_hash"] == "tx_4"
        assert data[1]["transaction_hash"] == "tx_3"
        assert data[2]["transaction_hash"] == "tx_2"
        assert data[0]["market_title"] == "Market Z"

    def test_dedupes_when_multiple_alerts_per_market(self, client, db_path):
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO tracked_wallets (address, tier, active) VALUES ('0xWB', 'A', TRUE)"
        )
        con.execute(
            "INSERT INTO markets (condition_id, title, slug, active) "
            "VALUES ('cond_y', 'Market Y', 'market-y', TRUE)"
        )
        con.execute(
            "INSERT INTO trades "
            "(transaction_hash, proxy_wallet, condition_id, asset_id, "
            " side, size_usd, price, timestamp_unix, timestamp_ts) "
            "VALUES ('tx_only', '0xWB', 'cond_y', 'a_y', 'YES', 100, 0.5, "
            "        1700000000, '2026-04-26 10:00:00')"
        )
        # Two alerts for same wallet+market → cross-join would produce 2 trade rows
        con.execute(
            "INSERT INTO alerts "
            "(alert_id, component, emitted_at, wallet_address, condition_id, "
            " side, size_usd, price, score) "
            "VALUES ('al_1', 'C2', CURRENT_TIMESTAMP, '0xWB', 'cond_y', 'YES', 50, 0.5, 7), "
            "       ('al_2', 'C2', CURRENT_TIMESTAMP, '0xWB', 'cond_y', 'YES', 50, 0.5, 8)"
        )
        con.close()

        resp = client.get("/api/wallets/0xWB/trades?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        # Should still return only 1 trade row despite 2 alerts joining
        assert len(data) == 1
        assert data[0]["transaction_hash"] == "tx_only"
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestWalletTradesEndpoint -v
```

Expected: FAIL (404 — endpoint not implemented).

- [ ] **Step 3: Implement endpoint**

Append to `src/polybot/dashboard/api.py`:

```python
@app.get("/api/wallets/{address}/trades")
def get_wallet_trades(
    con: DB,
    address: str,
    limit: int = Query(default=100, ge=1, le=500),
):
    rows = con.execute(
        "SELECT t.transaction_hash, t.timestamp_ts, t.condition_id, "
        "       m.title, m.slug, t.side, t.outcome, t.size_usd, t.price, "
        "       m.resolved, m.active, "
        "       ao.resolution_outcome, ao.was_direction_correct "
        "FROM trades t "
        "LEFT JOIN markets m ON t.condition_id = m.condition_id "
        "LEFT JOIN alerts a ON a.wallet_address = t.proxy_wallet "
        "                  AND a.condition_id = t.condition_id "
        "LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id "
        "WHERE t.proxy_wallet = ? "
        "ORDER BY t.timestamp_ts DESC, a.emitted_at DESC",
        [address],
    ).fetchall()

    # Dedup by transaction_hash, keep first occurrence (most recent due to ORDER BY)
    seen: dict = {}
    for r in rows:
        tx = r[0]
        if tx not in seen:
            seen[tx] = r
        if len(seen) >= limit:
            break

    return [
        {
            "transaction_hash": r[0],
            "timestamp_ts": str(r[1]) if r[1] else None,
            "condition_id": r[2],
            "market_title": r[3],
            "market_slug": r[4],
            "side": r[5],
            "outcome": r[6],
            "size_usd": float(r[7]) if r[7] is not None else None,
            "price": float(r[8]) if r[8] is not None else None,
            "resolved": r[9],
            "active": r[10],
            "resolution_outcome": r[11],
            "was_direction_correct": r[12],
        }
        for r in seen.values()
    ]
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestWalletTradesEndpoint -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/polybot/dashboard/api.py tests/unit/test_dashboard_api.py
git commit -m "feat(M8-B v2): add GET /api/wallets/{address}/trades with dedup"
```

---

## Phase 5 — Backend: modify GET /api/markets/hot ranking

### Task 7: TDD `/api/markets/hot` ranking by C2 score

**Files:**
- Modify: `tests/unit/test_dashboard_api.py`
- Modify: `src/polybot/dashboard/api.py:278-304` (the existing `get_hot_markets`)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_dashboard_api.py` :

```python
class TestHotMarketsRanking:
    def test_orders_by_c2_score_max(self, client, db_path):
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO markets (condition_id, title, slug, volume_24h, active) "
            "VALUES ('cond_low', 'Low Score', 'low', 99999, TRUE), "
            "       ('cond_mid', 'Mid Score', 'mid', 50000, TRUE), "
            "       ('cond_top', 'Top Score', 'top', 1000, TRUE)"
        )
        # cond_top has score 9 ; cond_mid 7 ; cond_low 5
        # Despite cond_low having the highest volume, cond_top should rank first
        con.execute(
            "INSERT INTO alerts "
            "(alert_id, component, emitted_at, wallet_address, condition_id, "
            " side, size_usd, price, score, features_passed) "
            "VALUES "
            "('h1', 'C2', CURRENT_TIMESTAMP, '0xw', 'cond_low', 'YES', 100, 0.5, 5, 'volume'), "
            "('h2', 'C2', CURRENT_TIMESTAMP, '0xw', 'cond_mid', 'YES', 100, 0.5, 7, 'volume,edge'), "
            "('h3', 'C2', CURRENT_TIMESTAMP, '0xw', 'cond_top', 'YES', 100, 0.5, 9, 'volume,edge,momentum')"
        )
        con.close()

        resp = client.get("/api/markets/hot")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["condition_id"] == "cond_top"
        assert data[0]["c2_score_max"] == 9
        assert data[0]["c2_alerts_7d"] == 1
        assert data[0]["features_last"] == "volume,edge,momentum"
        assert data[1]["condition_id"] == "cond_mid"
        assert data[2]["condition_id"] == "cond_low"
```

- [ ] **Step 2: Run test, verify it fails**

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestHotMarketsRanking -v
```

Expected: FAIL — current endpoint orders by volume_24h desc and doesn't return `c2_score_max`/`features_last`.

- [ ] **Step 3: Replace `get_hot_markets`**

In `src/polybot/dashboard/api.py`, locate `@app.get("/api/markets/hot")` and replace its body :

```python
@app.get("/api/markets/hot")
def get_hot_markets(con: DB):
    rows = con.execute(
        "SELECT m.condition_id, m.title, m.slug, "
        "       MAX(a.score) AS c2_score_max, "
        "       (SELECT a2.features_passed FROM alerts a2 "
        "        WHERE a2.condition_id = m.condition_id AND a2.component = 'C2' "
        "        ORDER BY a2.emitted_at DESC LIMIT 1) AS features_last, "
        "       COUNT(a.alert_id) AS c2_alerts_7d, "
        "       MAX(a.emitted_at) AS last_alert_at, "
        "       m.volume_24h, m.end_date "
        "FROM markets m "
        "JOIN alerts a ON m.condition_id = a.condition_id "
        "WHERE a.component = 'C2' "
        "  AND a.emitted_at >= CURRENT_DATE - INTERVAL '7 DAY' "
        "GROUP BY m.condition_id, m.title, m.slug, m.volume_24h, m.end_date "
        "ORDER BY c2_score_max DESC, c2_alerts_7d DESC "
        "LIMIT 10"
    ).fetchall()
    return [
        {
            "condition_id": r[0],
            "title": r[1],
            "slug": r[2],
            "c2_score_max": r[3],
            "features_last": r[4],
            "c2_alerts_7d": r[5],
            "last_alert_at": str(r[6]) if r[6] else None,
            "volume_24h": float(r[7]) if r[7] is not None else None,
            "end_date": str(r[8]) if r[8] else None,
        }
        for r in rows
    ]
```

- [ ] **Step 4: Run test, verify it passes**

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestHotMarketsRanking -v
uv run pytest tests/unit/test_dashboard_api.py -v
```

Expected: new test PASS, all other tests still PASS (no regression).

- [ ] **Step 5: Commit**

```bash
git add src/polybot/dashboard/api.py tests/unit/test_dashboard_api.py
git commit -m "feat(M8-B v2): rank /api/markets/hot by C2 score (BREAKING)"
```

---

## Phase 6 — Frontend: wipe + scaffold

### Task 8: Wipe `dashboard/src/` and scaffold tokens + entry

**Files:**
- Delete: `dashboard/src/App.jsx`
- Delete: `dashboard/src/main.jsx`
- Delete: `dashboard/src/main.css`
- Delete: `dashboard/src/components/` (all 3 files)
- Delete: `dashboard/src/pages/` (all 5 files)
- Delete: `dashboard/src/hooks/` (1 file)
- Modify: `dashboard/index.html`
- Modify: `dashboard/package.json`
- Create: `dashboard/src/index.css`
- Create: `dashboard/src/main.jsx`
- Create: `dashboard/src/App.jsx`

- [ ] **Step 1: Wipe old src**

```bash
rm -rf dashboard/src
mkdir -p dashboard/src/lib dashboard/src/components/layout dashboard/src/components/primitives dashboard/src/components/charts dashboard/src/components/domain dashboard/src/pages
```

- [ ] **Step 2: Add SWR + lucide-react to package.json**

```bash
cd dashboard && npm install swr lucide-react && cd ..
```

Expected: `package.json` updated with `"swr": "^2.x"` and `"lucide-react": "^0.x"`.

- [ ] **Step 3: Update `index.html` to use Inter font**

Replace `dashboard/index.html` content:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Polybot Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet" />
  </head>
  <body class="bg-bg-primary text-text-primary antialiased">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 4: Create `dashboard/src/index.css`**

```css
@import "tailwindcss";

@theme {
  --color-bg-primary: #0a0a0f;
  --color-bg-card: #12121a;
  --color-bg-card-hover: #16161f;
  --color-bg-sidebar: #0e0e14;
  --color-accent-orange: #f97316;
  --color-accent-violet: #a855f7;
  --color-pnl-positive: #22c55e;
  --color-pnl-negative: #ef4444;
  --color-text-primary: #f1f1f4;
  --color-text-secondary: #6b7280;
  --color-text-tertiary: #4b5563;
  --font-sans: "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
  --radius-card: 16px;
}

@layer base {
  body {
    font-family: var(--font-sans);
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
  }
}

@layer utilities {
  .glass-card {
    background: linear-gradient(135deg, #12121a 0%, #0e0e18 100%);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: var(--radius-card);
  }
  .glass-hero {
    backdrop-filter: blur(20px);
    background: rgba(18, 18, 26, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: var(--radius-card);
  }
  .row-hover {
    transition: background 0.15s ease;
  }
  .row-hover:hover {
    background: rgba(255, 255, 255, 0.03);
  }
  .card-hover {
    transition: border-color 0.2s ease, background 0.2s ease;
  }
  .card-hover:hover {
    border-color: rgba(249, 115, 22, 0.3);
  }
}
```

- [ ] **Step 5: Create `dashboard/src/main.jsx`**

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { SWRConfig } from "swr";
import { fetcher } from "./api";
import App from "./App";
import Overview from "./pages/Overview";
import Alerts from "./pages/Alerts";
import Wallets from "./pages/Wallets";
import WalletDetail from "./pages/WalletDetail";
import Performance from "./pages/Performance";
import System from "./pages/System";
import "./index.css";

const router = createBrowserRouter([{
  path: "/",
  element: <App />,
  children: [
    { index: true, element: <Overview /> },
    { path: "alerts", element: <Alerts /> },
    { path: "wallets", element: <Wallets /> },
    { path: "wallets/:address", element: <WalletDetail /> },
    { path: "performance", element: <Performance /> },
    { path: "system", element: <System /> },
  ],
}]);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <SWRConfig value={{
      fetcher,
      revalidateOnFocus: true,
      dedupingInterval: 5000,
      errorRetryCount: 2,
      errorRetryInterval: 5000,
    }}>
      <RouterProvider router={router} />
    </SWRConfig>
  </React.StrictMode>
);
```

- [ ] **Step 6: Create stub `dashboard/src/App.jsx`** (just `<Outlet/>` — Sidebar + TopBar added next task)

```jsx
import { Outlet } from "react-router-dom";

export default function App() {
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary">
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 7: Create stub pages** (so router doesn't crash)

For each of `Overview.jsx`, `Alerts.jsx`, `Wallets.jsx`, `WalletDetail.jsx`, `Performance.jsx`, `System.jsx` in `dashboard/src/pages/`:

```jsx
export default function Overview() {  // adjust name per file
  return <div>Overview placeholder</div>;
}
```

- [ ] **Step 8: Create `dashboard/src/api.js`**

```javascript
const API_BASE = "/api";

export async function fetcher(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    err.info = await res.text().catch(() => null);
    throw err;
  }
  return res.json();
}

export const urls = {
  status: () => "/status",
  alerts: ({ days = 7, component } = {}) =>
    `/alerts?days=${days}${component ? `&component=${component}` : ""}`,
  wallets: () => "/wallets",
  walletDetail: (addr) => `/wallets/${addr}`,
  walletTrades: (addr, limit = 100) => `/wallets/${addr}/trades?limit=${limit}`,
  performance: (days = 30) => `/performance?days=${days}`,
  hotMarkets: () => "/markets/hot",
  audit: (limit = 50) => `/audit?limit=${limit}`,
  costs: () => "/costs",
  clusters: () => "/clusters",
};
```

- [ ] **Step 9: Verify build**

```bash
cd dashboard && npm run build && cd ..
```

Expected: build succeeds, `dist/` produced. No TS errors (project is JS).

- [ ] **Step 10: Commit**

```bash
git add dashboard/
git commit -m "feat(M8-B v2): wipe dashboard/src + scaffold Tailwind v4 tokens + SWR + Inter"
```

### Task 9: lib helpers (format + colors)

**Files:**
- Create: `dashboard/src/lib/format.js`
- Create: `dashboard/src/lib/colors.js`

- [ ] **Step 1: Create `dashboard/src/lib/format.js`**

```javascript
export function formatUSD(value, opts = {}) {
  if (value == null || isNaN(value)) return "—";
  const sign = opts.signed && value > 0 ? "+" : "";
  const fixed = Math.abs(value) >= 1000 ? 0 : 2;
  return `${sign}$${value.toFixed(fixed)}`;
}

export function formatPct(value, decimals = 1) {
  if (value == null || isNaN(value)) return "—";
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatRelative(isoString) {
  if (!isoString) return "—";
  const d = new Date(isoString);
  const diffSec = (Date.now() - d.getTime()) / 1000;
  if (diffSec < 60) return "à l'instant";
  if (diffSec < 3600) return `il y a ${Math.floor(diffSec / 60)}m`;
  if (diffSec < 86400) return `il y a ${Math.floor(diffSec / 3600)}h`;
  return `il y a ${Math.floor(diffSec / 86400)}j`;
}

export function truncateAddr(addr, chars = 6) {
  if (!addr) return "";
  return `${addr.slice(0, chars)}...${addr.slice(-4)}`;
}

export async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function parseFeaturesSafe(jsonOrStr) {
  if (!jsonOrStr) return [];
  if (typeof jsonOrStr === "string") {
    // Try comma-separated first (legacy format), fall back to JSON
    if (!jsonOrStr.startsWith("[") && !jsonOrStr.startsWith("{")) {
      return jsonOrStr.split(",").map((s) => s.trim()).filter(Boolean);
    }
    try {
      const parsed = JSON.parse(jsonOrStr);
      if (Array.isArray(parsed)) return parsed;
      if (typeof parsed === "object") return Object.keys(parsed);
      return [];
    } catch {
      return [];
    }
  }
  if (Array.isArray(jsonOrStr)) return jsonOrStr;
  return [];
}
```

- [ ] **Step 2: Create `dashboard/src/lib/colors.js`**

```javascript
export function pnlColor(value) {
  if (value == null) return "text-text-secondary";
  return value > 0 ? "text-pnl-positive" : value < 0 ? "text-pnl-negative" : "text-text-secondary";
}

export function statusColor(status) {
  switch ((status || "").toLowerCase()) {
    case "correct":
    case "success":
    case "active":
      return "text-pnl-positive";
    case "incorrect":
    case "failed":
    case "error":
      return "text-pnl-negative";
    case "running":
    case "pending":
      return "text-accent-orange";
    default:
      return "text-text-secondary";
  }
}

export function sideColor(side) {
  // YES / BUY YES → green ; NO / BUY NO → red
  const s = (side || "").toUpperCase();
  if (s.includes("YES")) return "text-pnl-positive";
  if (s.includes("NO")) return "text-pnl-negative";
  return "text-text-primary";
}

export function componentColor(component) {
  if (component === "C1") return "bg-accent-orange/20 text-accent-orange";
  if (component === "C2") return "bg-accent-violet/20 text-accent-violet";
  return "bg-white/5 text-text-secondary";
}
```

- [ ] **Step 3: Verify build still works**

```bash
cd dashboard && npm run build && cd ..
```

Expected: success.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/lib/
git commit -m "feat(M8-B v2): add format + colors lib helpers"
```

---

## Phase 7 — Frontend: layout shell

### Task 10: Sidebar component

**Files:**
- Create: `dashboard/src/components/layout/Sidebar.jsx`
- Modify: `dashboard/src/App.jsx`

- [ ] **Step 1: Create `Sidebar.jsx`**

```jsx
import { NavLink } from "react-router-dom";
import { Activity, Zap, Users, TrendingUp, Settings } from "lucide-react";

const NAV = [
  { path: "/", label: "Overview", icon: Activity },
  { path: "/alerts", label: "Alerts", icon: Zap },
  { path: "/wallets", label: "Wallets", icon: Users },
  { path: "/performance", label: "Performance", icon: TrendingUp },
  { path: "/system", label: "System", icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="hidden md:flex md:w-60 lg:w-60 md:flex-col bg-bg-sidebar border-r border-white/[0.06] py-6 px-4">
      <h1 className="font-extrabold text-2xl tracking-widest text-text-primary mb-10 px-2">
        POLYBOT
      </h1>
      <nav className="flex flex-col gap-1">
        {NAV.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-accent-orange/10 text-accent-orange border-l-[3px] border-accent-orange pl-[9px]"
                  : "text-text-secondary hover:bg-white/[0.05] hover:text-text-primary"
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: Wire into App.jsx**

Replace `dashboard/src/App.jsx` :

```jsx
import { Outlet } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar";

export default function App() {
  return (
    <div className="flex min-h-screen bg-bg-primary text-text-primary">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Visual check**

```bash
cd dashboard && npm run dev
```

Expected: sidebar visible at left with POLYBOT logo + 5 nav items, active state turns orange when clicked.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/
git commit -m "feat(M8-B v2): add Sidebar component"
```

### Task 11: TopBar component with live pills

**Files:**
- Create: `dashboard/src/components/layout/TopBar.jsx`
- Modify: `dashboard/src/App.jsx`

- [ ] **Step 1: Create `TopBar.jsx`**

```jsx
import useSWR from "swr";
import { RefreshCw } from "lucide-react";
import { urls } from "../../api";
import { formatUSD, formatPct } from "../../lib/format";
import { pnlColor } from "../../lib/colors";

function Pill({ label, value, valueClass = "" }) {
  return (
    <div className="flex items-center gap-2 bg-white/[0.05] rounded-full px-3 py-1 text-xs whitespace-nowrap">
      <span className="text-text-secondary uppercase tracking-wider">{label}</span>
      <span className={`font-semibold ${valueClass}`}>{value}</span>
    </div>
  );
}

export default function TopBar() {
  const { data: status, mutate: mutateStatus } = useSWR(urls.status(), {
    refreshInterval: 30_000,
  });
  const { data: perf, mutate: mutatePerf } = useSWR(urls.performance(30), {
    refreshInterval: 60_000,
  });
  const { data: alerts, mutate: mutateAlerts } = useSWR(urls.alerts({ days: 1 }), {
    refreshInterval: 60_000,
  });

  // Compute Shadow P&L total
  const totalPnl = perf?.cumulative?.reduce(
    (sum, c) => sum + (c.pnl || 0), 0
  );

  // Win rate over all resolved
  const totalResolved = perf?.cumulative?.reduce(
    (sum, c) => sum + (c.alerts || 0), 0
  );
  const totalCorrect = perf?.cumulative?.reduce(
    (sum, c) => sum + (c.correct || 0), 0
  );
  const winRate = totalResolved > 0 ? totalCorrect / totalResolved : null;

  // Indexers status
  const indexers = status?.indexers || [];
  const okCount = indexers.filter((i) => i.status === "success").length;
  const total = indexers.length;
  const indexerStatus =
    total === 0
      ? "—"
      : okCount === total
      ? `${okCount}/${total} ✓`
      : okCount === total - 1
      ? `${okCount}/${total} ⚠`
      : `${okCount}/${total} ✗`;
  const indexerClass =
    okCount === total
      ? "text-pnl-positive"
      : okCount >= total - 1
      ? "text-accent-orange"
      : "text-pnl-negative";

  function refreshAll() {
    mutateStatus();
    mutatePerf();
    mutateAlerts();
  }

  return (
    <div className="flex items-center gap-2 mb-6 overflow-x-auto">
      <Pill
        label="Shadow P&L"
        value={formatUSD(totalPnl, { signed: true })}
        valueClass={pnlColor(totalPnl)}
      />
      <Pill label="Alertes 24h" value={alerts?.length ?? "—"} />
      <Pill label="Win Rate" value={formatPct(winRate)} />
      <Pill label="Indexers" value={indexerStatus} valueClass={indexerClass} />
      <button
        onClick={refreshAll}
        className="ml-auto p-2 rounded-lg hover:bg-white/[0.05] text-text-secondary hover:text-text-primary transition-colors"
        title="Refresh all"
      >
        <RefreshCw size={16} />
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Wire into App.jsx**

Replace `dashboard/src/App.jsx` :

```jsx
import { Outlet } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar";
import TopBar from "./components/layout/TopBar";

export default function App() {
  return (
    <div className="flex min-h-screen bg-bg-primary text-text-primary">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <TopBar />
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Start backend then test visually**

```bash
# In one terminal: start backend
uv run uvicorn polybot.dashboard.api:app --port 8000 --reload
# In another: start frontend
cd dashboard && npm run dev
```

Open `http://localhost:5173`. Expected: TopBar with 4 pills + refresh icon, values populate (or show "—" if DB empty).

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/
git commit -m "feat(M8-B v2): add TopBar with live SWR pills"
```

---

## Phase 8 — Frontend: primitives

### Task 12: Build all primitives at once

**Files:**
- Create: `dashboard/src/components/primitives/GlassCard.jsx`
- Create: `dashboard/src/components/primitives/KpiCard.jsx`
- Create: `dashboard/src/components/primitives/StatusBadge.jsx`
- Create: `dashboard/src/components/primitives/FilterPills.jsx`
- Create: `dashboard/src/components/primitives/AddressDisplay.jsx`
- Create: `dashboard/src/components/primitives/EmptyState.jsx`
- Create: `dashboard/src/components/primitives/ErrorState.jsx`
- Create: `dashboard/src/components/primitives/SkeletonList.jsx`

- [ ] **Step 1: GlassCard**

```jsx
// GlassCard.jsx
export default function GlassCard({ hero = false, className = "", children, ...rest }) {
  const base = hero ? "glass-hero p-6" : "glass-card p-6";
  return (
    <div className={`${base} ${className}`} {...rest}>
      {children}
    </div>
  );
}
```

- [ ] **Step 2: KpiCard**

```jsx
// KpiCard.jsx
import GlassCard from "./GlassCard";

export default function KpiCard({ label, value, valueClass = "", subtitle, extra }) {
  return (
    <GlassCard>
      <div className="flex flex-col gap-2">
        <div className="text-xs uppercase tracking-wider text-text-secondary font-medium">
          {label}
        </div>
        <div className={`text-3xl font-bold tracking-tight ${valueClass}`}>
          {value}
        </div>
        {subtitle && (
          <div className="text-xs text-text-secondary">{subtitle}</div>
        )}
        {extra && <div className="mt-2">{extra}</div>}
      </div>
    </GlassCard>
  );
}
```

- [ ] **Step 3: StatusBadge**

```jsx
// StatusBadge.jsx
import { statusColor } from "../../lib/colors";

export default function StatusBadge({ status, label }) {
  const color = statusColor(status);
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${color}`}>
      <span className={`w-1.5 h-1.5 rounded-full bg-current`} />
      {label || status}
    </span>
  );
}
```

- [ ] **Step 4: FilterPills**

```jsx
// FilterPills.jsx
export default function FilterPills({ options, value, onChange }) {
  // options: [{ value: "C1", label: "C1" }, ...]
  return (
    <div className="flex gap-1 flex-wrap">
      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value ?? "_all"}
            onClick={() => onChange(opt.value)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              active
                ? "bg-accent-orange text-bg-primary"
                : "bg-white/[0.05] text-text-secondary hover:bg-white/[0.08] hover:text-text-primary"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 5: AddressDisplay**

```jsx
// AddressDisplay.jsx
import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { copyToClipboard, truncateAddr } from "../../lib/format";

export default function AddressDisplay({ address, truncate = true, className = "" }) {
  const [copied, setCopied] = useState(false);
  if (!address) return <span className="text-text-secondary">—</span>;
  const display = truncate ? truncateAddr(address) : address;

  async function handleCopy(e) {
    e.stopPropagation();
    if (await copyToClipboard(address)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <span className={`inline-flex items-center gap-1.5 font-mono text-xs ${className}`}>
      <span>{display}</span>
      <button
        onClick={handleCopy}
        className="text-text-tertiary hover:text-text-primary transition-colors"
        title="Copy address"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
      </button>
    </span>
  );
}
```

- [ ] **Step 6: EmptyState**

```jsx
// EmptyState.jsx
export default function EmptyState({ icon: Icon, message, subtitle }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {Icon && <Icon size={32} className="text-text-tertiary mb-3" />}
      <div className="text-text-secondary text-sm">{message}</div>
      {subtitle && (
        <div className="text-text-tertiary text-xs mt-1">{subtitle}</div>
      )}
    </div>
  );
}
```

- [ ] **Step 7: ErrorState**

```jsx
// ErrorState.jsx
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function ErrorState({ error, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <AlertTriangle size={32} className="text-pnl-negative mb-3" />
      <div className="text-text-primary font-medium mb-1">Erreur de chargement</div>
      {error?.message && (
        <details className="text-xs text-text-secondary mt-2 max-w-md">
          <summary className="cursor-pointer">Détails</summary>
          <pre className="mt-2 text-left bg-bg-card p-3 rounded text-text-tertiary overflow-auto">
            {error.message}{error.info ? `\n\n${error.info}` : ""}
          </pre>
        </details>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-accent-orange/10 text-accent-orange hover:bg-accent-orange/20 rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCw size={14} />
          Réessayer
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 8: SkeletonList**

```jsx
// SkeletonList.jsx
export default function SkeletonList({ count = 5, height = 96 }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-bg-card-hover animate-pulse rounded-card"
          style={{ height: `${height}px` }}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 9: Verify build**

```bash
cd dashboard && npm run build && cd ..
```

Expected: success.

- [ ] **Step 10: Commit**

```bash
git add dashboard/src/components/primitives/
git commit -m "feat(M8-B v2): add 8 primitive components (cards, badges, pills, address, states)"
```

---

## Phase 9 — Frontend: charts

### Task 13: Chart wrappers

**Files:**
- Create: `dashboard/src/components/charts/ChartArea.jsx`
- Create: `dashboard/src/components/charts/ChartLine.jsx`
- Create: `dashboard/src/components/charts/ChartDonut.jsx`
- Create: `dashboard/src/components/charts/ChartBar.jsx`
- Create: `dashboard/src/components/charts/Sparkline.jsx`

- [ ] **Step 1: ChartArea**

```jsx
// ChartArea.jsx
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

export default function ChartArea({
  data,
  xKey = "day",
  yKey = "cum_pnl",
  height = 240,
  color = "#22c55e",
  negativeColor = "#ef4444",
}) {
  const lastValue = data?.length ? data[data.length - 1][yKey] : 0;
  const strokeColor = lastValue >= 0 ? color : negativeColor;
  const fillId = `area-fill-${strokeColor.replace("#", "")}`;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data || []} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={strokeColor} stopOpacity={0.3} />
            <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" />
        <XAxis dataKey={xKey} stroke="#6b7280" fontSize={11} tickLine={false} />
        <YAxis stroke="#6b7280" fontSize={11} tickLine={false} />
        <Tooltip
          contentStyle={{
            background: "#12121a",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Area
          type="monotone"
          dataKey={yKey}
          stroke={strokeColor}
          strokeWidth={2}
          fill={`url(#${fillId})`}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: ChartLine** (multi-series for C1 vs C2)

```jsx
// ChartLine.jsx
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";

export default function ChartLine({ data, xKey = "day", series = [], height = 280 }) {
  // series: [{ key: "c1_pnl", color: "#f97316", name: "C1" }, ...]
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data || []} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" />
        <XAxis dataKey={xKey} stroke="#6b7280" fontSize={11} tickLine={false} />
        <YAxis stroke="#6b7280" fontSize={11} tickLine={false} />
        <Tooltip
          contentStyle={{
            background: "#12121a",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Legend wrapperStyle={{ fontSize: "12px", color: "#6b7280" }} />
        {series.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name}
            stroke={s.color}
            strokeWidth={2}
            dot={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 3: ChartDonut**

```jsx
// ChartDonut.jsx
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";

export default function ChartDonut({
  data,
  height = 160,
  colors = ["#22c55e", "#ef4444", "#6b7280"],
}) {
  // data: [{ name: "Correct", value: 21 }, { name: "Incorrect", value: 13 }]
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data || []}
          dataKey="value"
          nameKey="name"
          innerRadius={50}
          outerRadius={70}
          paddingAngle={2}
        >
          {(data || []).map((_, i) => (
            <Cell key={i} fill={colors[i % colors.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "#12121a",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 4: ChartBar (horizontal)**

```jsx
// ChartBar.jsx
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";

export default function ChartBar({
  data,
  xKey = "count",
  yKey = "label",
  height = 200,
  color = "#a855f7",
  cellColors,
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data || []} layout="vertical" margin={{ top: 8, right: 16, left: 24, bottom: 0 }}>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" />
        <XAxis type="number" stroke="#6b7280" fontSize={11} tickLine={false} />
        <YAxis dataKey={yKey} type="category" stroke="#6b7280" fontSize={11} tickLine={false} width={60} />
        <Tooltip
          contentStyle={{
            background: "#12121a",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Bar dataKey={xKey} radius={[0, 4, 4, 0]}>
          {(data || []).map((_, i) => (
            <Cell key={i} fill={cellColors ? cellColors[i] : color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 5: Sparkline**

```jsx
// Sparkline.jsx
import { ResponsiveContainer, AreaChart, Area } from "recharts";

export default function Sparkline({ data, dataKey = "value", color = "#f97316", height = 32 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data || []} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
        <Area
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={1.5}
          fill={color}
          fillOpacity={0.15}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 6: Verify build**

```bash
cd dashboard && npm run build && cd ..
```

Expected: success.

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/components/charts/
git commit -m "feat(M8-B v2): add 5 chart wrappers (Recharts pre-styled)"
```

---

## Phase 10 — Frontend: domain components

### Task 14: AlertCard, WalletCard, IndexerRow, HotMarketRow

**Files:**
- Create: `dashboard/src/components/domain/AlertCard.jsx`
- Create: `dashboard/src/components/domain/WalletCard.jsx`
- Create: `dashboard/src/components/domain/IndexerRow.jsx`
- Create: `dashboard/src/components/domain/HotMarketRow.jsx`

- [ ] **Step 1: AlertCard (with expand inline)**

```jsx
// AlertCard.jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ExternalLink, ChevronDown } from "lucide-react";
import GlassCard from "../primitives/GlassCard";
import StatusBadge from "../primitives/StatusBadge";
import AddressDisplay from "../primitives/AddressDisplay";
import { formatUSD, formatRelative, parseFeaturesSafe } from "../../lib/format";
import { sideColor, componentColor } from "../../lib/colors";

function alertStatus(alert) {
  if (!alert.resolution_outcome || alert.resolution_outcome === "PENDING") return "pending";
  return alert.was_direction_correct ? "correct" : "incorrect";
}

export default function AlertCard({ alert }) {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();
  const status = alertStatus(alert);
  const features = parseFeaturesSafe(alert.features_passed);
  const polymarketUrl = alert.market_slug
    ? `https://polymarket.com/event/${alert.market_slug}`
    : null;

  return (
    <GlassCard className="card-hover cursor-pointer" onClick={() => setExpanded((v) => !v)}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${componentColor(alert.component)}`}>
            {alert.component}
          </span>
          <span className="text-xs text-text-secondary">{formatRelative(alert.emitted_at)}</span>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={status} />
          <ChevronDown
            size={16}
            className={`text-text-tertiary transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        </div>
      </div>
      <div className="mt-3 text-base font-semibold text-text-primary">
        {alert.market_title || "Marché inconnu"}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <span className={`font-semibold ${sideColor(alert.side)}`}>
          BUY {alert.side} @ {alert.price?.toFixed(2)}
        </span>
        <span className="text-text-secondary">
          ${formatUSD(alert.size_usd)} <span className="text-text-tertiary">(wallet)</span>
        </span>
        {alert.score != null && (
          <span className="text-text-secondary">
            Score: <span className="text-text-primary font-medium">{alert.score}/8</span>
          </span>
        )}
      </div>
      <div className="mt-2 flex items-center justify-between text-xs">
        <button
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/wallets/${alert.wallet_address}`);
          }}
          className="text-text-secondary hover:text-accent-orange transition-colors"
        >
          <AddressDisplay address={alert.wallet_address} />
        </button>
        {polymarketUrl && (
          <a
            href={polymarketUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-text-secondary hover:text-accent-orange transition-colors"
          >
            Polymarket <ExternalLink size={11} />
          </a>
        )}
      </div>
      {expanded && (
        <div className="mt-4 pt-4 border-t border-white/[0.06] text-sm space-y-2">
          {alert.alignment_score != null && (
            <div className="flex justify-between">
              <span className="text-text-secondary">Alignment :</span>
              <span className="font-mono">{alert.alignment_score}</span>
            </div>
          )}
          {features.length > 0 && (
            <div>
              <div className="text-text-secondary mb-1">Features :</div>
              <div className="flex flex-wrap gap-1">
                {features.map((f) => (
                  <span
                    key={f}
                    className="px-2 py-0.5 bg-accent-violet/10 text-accent-violet rounded text-xs"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}
          {alert.shadow_pnl_simulated != null && (
            <div className="flex justify-between">
              <span className="text-text-secondary">Shadow P&L :</span>
              <span>{formatUSD(alert.shadow_pnl_simulated, { signed: true })}</span>
            </div>
          )}
          <div className="text-xs text-text-tertiary font-mono">
            ID : {alert.alert_id}
          </div>
        </div>
      )}
    </GlassCard>
  );
}
```

- [ ] **Step 2: WalletCard**

```jsx
// WalletCard.jsx
import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import GlassCard from "../primitives/GlassCard";
import AddressDisplay from "../primitives/AddressDisplay";
import { formatUSD, formatPct, formatRelative } from "../../lib/format";
import { pnlColor } from "../../lib/colors";

export default function WalletCard({ wallet }) {
  const navigate = useNavigate();
  const inactive = !wallet.active;
  return (
    <GlassCard
      className={`card-hover cursor-pointer ${inactive ? "opacity-50" : ""}`}
      onClick={() => navigate(`/wallets/${wallet.address}`)}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`w-2 h-2 rounded-full ${
                wallet.active ? "bg-pnl-positive" : "bg-pnl-negative"
              }`}
            />
            <span className="font-semibold text-text-primary truncate">
              {wallet.notes || "(sans nom)"}
            </span>
            {inactive && (
              <span className="text-xs px-2 py-0.5 bg-pnl-negative/10 text-pnl-negative rounded">
                DEMOTED
              </span>
            )}
            {wallet.tier === "A" && (
              <span className="text-xs px-2 py-0.5 bg-accent-orange/10 text-accent-orange rounded">
                Tier A{wallet.tier_a_confidence ? `1` : ""}
              </span>
            )}
          </div>
          <AddressDisplay address={wallet.address} truncate={false} className="text-text-tertiary" />
          <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <Stat label="Trades" value={wallet.trades_total ?? 0} />
            <Stat label="Résolus" value={wallet.resolved ?? 0} />
            <Stat label="Win" value={formatPct(wallet.win_rate != null ? wallet.win_rate / 100 : null)} />
            <Stat
              label="P&L"
              value={formatUSD(wallet.pnl, { signed: true })}
              valueClass={pnlColor(wallet.pnl)}
            />
          </div>
          <div className="mt-2 text-xs text-text-secondary">
            Dernier trade : {formatRelative(wallet.last_trade)}
          </div>
        </div>
        <ChevronRight size={20} className="text-text-tertiary mt-1 flex-shrink-0" />
      </div>
    </GlassCard>
  );
}

function Stat({ label, value, valueClass = "" }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-text-secondary">{label}</div>
      <div className={`font-medium ${valueClass}`}>{value}</div>
    </div>
  );
}
```

Note: the `/api/wallets` endpoint returns `notes` via the `source` field name and `win_rate` as percent (0-100). The component uses `wallet.notes` — if notes isn't returned by the existing endpoint, fall back to "(sans nom)". Verify by inspecting `/api/wallets` response in DevTools during visual check.

- [ ] **Step 3: IndexerRow**

```jsx
// IndexerRow.jsx
import { formatRelative } from "../../lib/format";
import { statusColor } from "../../lib/colors";

export default function IndexerRow({ indexer }) {
  const dotColor = statusColor(indexer.status).replace("text-", "bg-");
  return (
    <div className="flex items-center justify-between py-2 px-3 row-hover rounded-lg">
      <div className="flex items-center gap-3 min-w-0">
        <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
        <span className="text-sm font-medium truncate">{indexer.name}</span>
      </div>
      <div className="text-xs text-text-secondary whitespace-nowrap">
        {formatRelative(indexer.last_synced_at)}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: HotMarketRow**

```jsx
// HotMarketRow.jsx
import { ExternalLink } from "lucide-react";
import { parseFeaturesSafe } from "../../lib/format";

export default function HotMarketRow({ market }) {
  const features = parseFeaturesSafe(market.features_last);
  const polymarketUrl = market.slug ? `https://polymarket.com/event/${market.slug}` : null;
  return (
    <div className="flex items-center justify-between gap-4 py-3 px-3 row-hover rounded-lg">
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-text-primary truncate">
          {market.title}
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          {features.map((f) => (
            <span
              key={f}
              className="px-1.5 py-0.5 bg-accent-violet/10 text-accent-violet rounded text-[10px]"
            >
              {f}
            </span>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm font-mono">
          <span className="text-text-primary font-bold">{market.c2_score_max}</span>
          <span className="text-text-tertiary">/8</span>
        </span>
        {polymarketUrl && (
          <a
            href={polymarketUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-tertiary hover:text-accent-orange transition-colors"
          >
            <ExternalLink size={14} />
          </a>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify build**

```bash
cd dashboard && npm run build && cd ..
```

Expected: success.

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/components/domain/
git commit -m "feat(M8-B v2): add 4 domain components (alert/wallet/indexer/hotmarket)"
```

---

## Phase 11 — Frontend: pages

### Task 15: Overview page

**Files:**
- Modify: `dashboard/src/pages/Overview.jsx`

- [ ] **Step 1: Implement Overview**

Replace `dashboard/src/pages/Overview.jsx` :

```jsx
import { Link } from "react-router-dom";
import useSWR from "swr";
import { Inbox, ArrowRight } from "lucide-react";
import { urls } from "../api";
import GlassCard from "../components/primitives/GlassCard";
import KpiCard from "../components/primitives/KpiCard";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import ChartArea from "../components/charts/ChartArea";
import Sparkline from "../components/charts/Sparkline";
import AlertCard from "../components/domain/AlertCard";
import IndexerRow from "../components/domain/IndexerRow";
import HotMarketRow from "../components/domain/HotMarketRow";
import { formatUSD, formatPct } from "../lib/format";
import { pnlColor } from "../lib/colors";

export default function Overview() {
  const { data: perf, error: perfError } = useSWR(urls.performance(30), { refreshInterval: 60_000 });
  const { data: alerts, error: alertsError } = useSWR(urls.alerts({ days: 7 }), { refreshInterval: 60_000 });
  const { data: alerts24, error: alerts24Error } = useSWR(urls.alerts({ days: 1 }), { refreshInterval: 60_000 });
  const { data: status, error: statusError } = useSWR(urls.status(), { refreshInterval: 30_000 });
  const { data: hotMarkets } = useSWR(urls.hotMarkets(), { refreshInterval: 120_000 });
  const { data: costs } = useSWR(urls.costs());
  const { data: wallets } = useSWR(urls.wallets());

  // Build pnl_series for hero chart from perf.daily
  const pnlSeries = (perf?.daily || []).reduce((acc, d) => {
    const existing = acc.find((x) => x.day === d.day);
    if (existing) existing.cum_pnl = (existing.cum_pnl || 0) + (d.pnl || 0);
    else acc.push({ day: d.day, cum_pnl: d.pnl || 0 });
    return acc;
  }, []);
  // Cumulate
  let runningPnl = 0;
  const pnlChart = pnlSeries.map((p) => {
    runningPnl += p.cum_pnl;
    return { day: p.day, cum_pnl: runningPnl };
  });
  const totalPnl = runningPnl;

  // KPI computations
  const total24 = alerts24?.length ?? 0;
  const totalResolved = perf?.cumulative?.reduce((s, c) => s + (c.alerts || 0), 0) ?? 0;
  const totalCorrect = perf?.cumulative?.reduce((s, c) => s + (c.correct || 0), 0) ?? 0;
  const winRate = totalResolved > 0 ? totalCorrect / totalResolved : null;
  const activeWallets = wallets?.filter((w) => w.active).length ?? 0;
  const totalWallets = wallets?.length ?? 0;

  const recentAlerts = (alerts || []).slice(0, 5);

  return (
    <div className="flex flex-col gap-6">
      {/* Hero */}
      <GlassCard hero className="p-8">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-wider text-text-secondary mb-2">
              Shadow P&L cumulé
            </div>
            <div className={`text-5xl font-bold tracking-tight ${pnlColor(totalPnl)}`}>
              {formatUSD(totalPnl, { signed: true })}
            </div>
            <div className="mt-2 inline-flex items-center gap-2 text-xs">
              <span className="w-2 h-2 rounded-full bg-pnl-positive animate-pulse" />
              <span className="text-text-secondary uppercase tracking-wider">Shadow Mode</span>
            </div>
          </div>
        </div>
        <div className="mt-6">
          {perfError ? (
            <ErrorState error={perfError} />
          ) : pnlChart.length === 0 ? (
            <EmptyState icon={Inbox} message="Données P&L insuffisantes" />
          ) : (
            <ChartArea data={pnlChart} height={180} />
          )}
        </div>
      </GlassCard>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Alertes 24h"
          value={total24}
          extra={<Sparkline data={pnlChart.slice(-7)} dataKey="cum_pnl" />}
        />
        <KpiCard label="Win Rate" value={formatPct(winRate)} />
        <KpiCard
          label="Wallets actifs"
          value={`${activeWallets}/${totalWallets}`}
        />
        <KpiCard
          label="Coûts mois"
          value={formatUSD((costs?.llm_cost_estimate || 0) + (costs?.vps_monthly || 0))}
          subtitle={`LLM ${formatUSD(costs?.llm_cost_estimate)} + VPS ${formatUSD(costs?.vps_monthly)}`}
        />
      </div>

      {/* Bottom: Alerts (left) + Indexers (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Dernières alertes</h2>
            <Link to="/alerts" className="text-sm text-accent-orange hover:underline inline-flex items-center gap-1">
              Voir tout <ArrowRight size={14} />
            </Link>
          </div>
          {alertsError ? (
            <ErrorState error={alertsError} />
          ) : !alerts ? (
            <SkeletonList count={5} height={140} />
          ) : recentAlerts.length === 0 ? (
            <EmptyState icon={Inbox} message="Aucune alerte récente" />
          ) : (
            recentAlerts.map((a) => <AlertCard key={a.alert_id} alert={a} />)
          )}
        </div>

        <div className="lg:col-span-2 flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Indexers</h2>
          <GlassCard>
            {statusError ? (
              <ErrorState error={statusError} />
            ) : !status ? (
              <SkeletonList count={6} height={32} />
            ) : (
              status.indexers.map((i) => <IndexerRow key={i.name} indexer={i} />)
            )}
          </GlassCard>
        </div>
      </div>

      {/* Hot Markets */}
      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Hot Markets (par score C2)</h2>
        <GlassCard>
          {!hotMarkets ? (
            <SkeletonList count={5} height={56} />
          ) : hotMarkets.length === 0 ? (
            <EmptyState icon={Inbox} message="Aucune alerte C2 sur 7j" />
          ) : (
            hotMarkets.slice(0, 5).map((m) => <HotMarketRow key={m.condition_id} market={m} />)
          )}
        </GlassCard>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Visual check**

```bash
cd dashboard && npm run dev
```

Open `http://localhost:5173/`. Expected: hero card with P&L, 4 KPI cards, dernières alertes, indexers list, hot markets. Pages may show empty states if DB has no data — that's OK.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/pages/Overview.jsx
git commit -m "feat(M8-B v2): build Overview page (hero P&L + KPIs + alerts + indexers + hot markets)"
```

### Task 16: Alerts page (with URL params + expand inline)

**Files:**
- Modify: `dashboard/src/pages/Alerts.jsx`

- [ ] **Step 1: Implement Alerts**

```jsx
import useSWR from "swr";
import { useSearchParams } from "react-router-dom";
import { Inbox } from "lucide-react";
import { urls } from "../api";
import FilterPills from "../components/primitives/FilterPills";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import AlertCard from "../components/domain/AlertCard";

const COMPONENT_OPTIONS = [
  { value: null, label: "Tous" },
  { value: "C1", label: "C1" },
  { value: "C2", label: "C2" },
];
const PERIOD_OPTIONS = [
  { value: "1", label: "24h" },
  { value: "7", label: "7j" },
  { value: "30", label: "30j" },
  { value: "365", label: "All" },
];
const STATUS_OPTIONS = [
  { value: null, label: "Tous" },
  { value: "pending", label: "Pending" },
  { value: "correct", label: "Correct" },
  { value: "incorrect", label: "Incorrect" },
];

function alertStatus(alert) {
  if (!alert.resolution_outcome || alert.resolution_outcome === "PENDING") return "pending";
  return alert.was_direction_correct ? "correct" : "incorrect";
}

export default function Alerts() {
  const [params, setParams] = useSearchParams();
  const component = params.get("component");
  const days = params.get("days") || "7";
  const status = params.get("status");

  const { data, error, isLoading, mutate } = useSWR(
    urls.alerts({ days: parseInt(days), component }),
    { refreshInterval: 60_000 }
  );

  function setParam(key, value) {
    const next = new URLSearchParams(params);
    if (value == null) next.delete(key);
    else next.set(key, value);
    setParams(next);
  }

  const filtered = status ? (data || []).filter((a) => alertStatus(a) === status) : data;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-bold">Alertes</h1>

      <div className="flex flex-col md:flex-row md:items-center gap-4 flex-wrap">
        <div>
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-1">Composant</div>
          <FilterPills options={COMPONENT_OPTIONS} value={component} onChange={(v) => setParam("component", v)} />
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-1">Période</div>
          <FilterPills options={PERIOD_OPTIONS} value={days} onChange={(v) => setParam("days", v)} />
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-1">Status</div>
          <FilterPills options={STATUS_OPTIONS} value={status} onChange={(v) => setParam("status", v)} />
        </div>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => mutate()} />
      ) : isLoading ? (
        <SkeletonList count={8} height={140} />
      ) : !filtered?.length ? (
        <EmptyState icon={Inbox} message="Aucune alerte sur ces critères" />
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((a) => (
            <AlertCard key={a.alert_id} alert={a} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Visual check**

Navigate to `http://localhost:5173/alerts`. Click filter pills — verify URL changes (`?component=C2&days=7`). Reload — filters preserved. Click a card — expands inline.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/pages/Alerts.jsx
git commit -m "feat(M8-B v2): build Alerts page with URL filters + expand inline"
```

### Task 17: Wallets page

**Files:**
- Modify: `dashboard/src/pages/Wallets.jsx`

- [ ] **Step 1: Implement Wallets**

```jsx
import useSWR from "swr";
import { Inbox } from "lucide-react";
import { urls } from "../api";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import WalletCard from "../components/domain/WalletCard";

export default function Wallets() {
  const { data, error, isLoading, mutate } = useSWR(urls.wallets());

  if (error) return <ErrorState error={error} onRetry={() => mutate()} />;
  if (isLoading) return <SkeletonList count={10} height={140} />;
  if (!data?.length) return <EmptyState icon={Inbox} message="Aucun wallet Tier A" />;

  // Sort: active first, then by trades_total desc
  const sorted = [...data].sort((a, b) => {
    if (a.active !== b.active) return a.active ? -1 : 1;
    return (b.trades_total || 0) - (a.trades_total || 0);
  });

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-bold">Wallets Tier A</h1>
      <div className="flex flex-col gap-3">
        {sorted.map((w) => (
          <WalletCard key={w.address} wallet={w} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Visual check**

Navigate `/wallets`. Expected: WalletCards with names from `notes`, demoted ones grayed, click → routes to `/wallets/:address`.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/pages/Wallets.jsx
git commit -m "feat(M8-B v2): build Wallets list page"
```

### Task 18: WalletDetail page

**Files:**
- Modify: `dashboard/src/pages/WalletDetail.jsx`

- [ ] **Step 1: Implement WalletDetail**

```jsx
import useSWR from "swr";
import { useParams, Link } from "react-router-dom";
import { ExternalLink, ArrowLeft, Inbox } from "lucide-react";
import { urls } from "../api";
import GlassCard from "../components/primitives/GlassCard";
import KpiCard from "../components/primitives/KpiCard";
import AddressDisplay from "../components/primitives/AddressDisplay";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import StatusBadge from "../components/primitives/StatusBadge";
import ChartArea from "../components/charts/ChartArea";
import { formatUSD, formatPct, formatRelative } from "../lib/format";
import { pnlColor, sideColor } from "../lib/colors";

function tradeStatus(t) {
  if (!t.resolution_outcome) return "pending";
  return t.was_direction_correct ? "correct" : "incorrect";
}

export default function WalletDetail() {
  const { address } = useParams();
  const { data, error, isLoading, mutate } = useSWR(urls.walletDetail(address));
  const { data: trades } = useSWR(urls.walletTrades(address, 100));

  if (error) {
    if (error.status === 404) {
      return (
        <div className="flex flex-col items-center justify-center py-16 gap-4">
          <h1 className="text-xl text-text-primary">Wallet non suivi</h1>
          <Link to="/wallets" className="text-accent-orange hover:underline inline-flex items-center gap-1">
            <ArrowLeft size={14} /> Retour aux wallets
          </Link>
        </div>
      );
    }
    return <ErrorState error={error} onRetry={() => mutate()} />;
  }
  if (isLoading || !data) return <SkeletonList count={4} height={120} />;

  const polymarketUrl = `https://polymarket.com/profile/${address}`;

  return (
    <div className="flex flex-col gap-6">
      <Link to="/wallets" className="text-sm text-text-secondary hover:text-accent-orange inline-flex items-center gap-1 w-fit">
        <ArrowLeft size={14} /> Retour
      </Link>

      <GlassCard>
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">{data.name || "(sans nom)"}</h1>
            <div className="mt-2">
              <AddressDisplay address={data.address} truncate={false} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              <span className="px-2 py-0.5 bg-accent-orange/10 text-accent-orange rounded">
                Tier {data.tier}
              </span>
              {data.tier_a_confidence != null && (
                <span className="px-2 py-0.5 bg-white/[0.05] rounded text-text-secondary">
                  conf: {data.tier_a_confidence.toFixed(2)}
                </span>
              )}
              {!data.active && (
                <span className="px-2 py-0.5 bg-pnl-negative/10 text-pnl-negative rounded">DEMOTED</span>
              )}
            </div>
          </div>
          <a
            href={polymarketUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 bg-accent-orange/10 text-accent-orange hover:bg-accent-orange/20 rounded-lg text-sm font-medium transition-colors"
          >
            Voir sur Polymarket <ExternalLink size={14} />
          </a>
        </div>
      </GlassCard>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Trades" value={data.trades_total ?? 0} />
        <KpiCard label="Résolus" value={data.resolved ?? 0} />
        <KpiCard label="Win Rate" value={formatPct(data.win_rate)} />
        <KpiCard
          label="Shadow P&L"
          value={formatUSD(data.pnl, { signed: true })}
          valueClass={pnlColor(data.pnl)}
        />
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">P&L cumulé (90j)</h2>
        <GlassCard>
          {!data.pnl_series?.length ? (
            <EmptyState icon={Inbox} message="Aucune alerte résolue" />
          ) : (
            <ChartArea data={data.pnl_series} xKey="day" yKey="cum_pnl" />
          )}
        </GlassCard>
      </div>

      {data.cex_funding && (
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">CEX funding</h2>
          <GlassCard>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Source</div>
                <div className="font-medium">{data.cex_funding.cex_source}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Confidence</div>
                <div className="font-medium">{data.cex_funding.confidence?.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Method</div>
                <div className="font-medium font-mono text-xs">{data.cex_funding.method}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Deposit</div>
                <AddressDisplay address={data.cex_funding.deposit_address} />
              </div>
            </div>
          </GlassCard>
        </div>
      )}

      {data.cluster && (
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Cluster</h2>
          <GlassCard>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Cluster ID</div>
                <div className="font-medium font-mono text-xs">{data.cluster.cluster_id}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Size</div>
                <div className="font-medium">{data.cluster.size}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">CEX</div>
                <div className="font-medium">{data.cluster.cex_source || "—"}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Funded by</div>
                <AddressDisplay address={data.cluster.funded_by} />
              </div>
            </div>
          </GlassCard>
        </div>
      )}

      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Trades récents</h2>
        <GlassCard className="overflow-x-auto">
          {!trades ? (
            <SkeletonList count={5} height={32} />
          ) : trades.length === 0 ? (
            <EmptyState icon={Inbox} message="Aucun trade enregistré" />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-text-secondary">
                  <th className="pb-2">Date</th>
                  <th className="pb-2">Marché</th>
                  <th className="pb-2">Side</th>
                  <th className="pb-2 text-right">Size</th>
                  <th className="pb-2 text-right">Prix</th>
                  <th className="pb-2 text-right">Status</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.transaction_hash} className="border-t border-white/[0.04]">
                    <td className="py-2 text-text-secondary whitespace-nowrap">
                      {formatRelative(t.timestamp_ts)}
                    </td>
                    <td className="py-2 max-w-xs truncate">{t.market_title || "—"}</td>
                    <td className={`py-2 font-medium ${sideColor(t.side)}`}>{t.side}</td>
                    <td className="py-2 text-right">{formatUSD(t.size_usd)}</td>
                    <td className="py-2 text-right">{t.price?.toFixed(2) ?? "—"}</td>
                    <td className="py-2 text-right">
                      <StatusBadge status={tradeStatus(t)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Visual check**

Navigate `/wallets/0xd1acd3925d895de9aec98ff95f3a30c5279d08d5`. Expected: header with name "Kickstand7", KPIs, P&L graph, trades table. CEX/cluster sections appear if applicable.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/pages/WalletDetail.jsx
git commit -m "feat(M8-B v2): build WalletDetail page (header + KPIs + P&L + trades + cex/cluster)"
```

### Task 19: Performance page

**Files:**
- Modify: `dashboard/src/pages/Performance.jsx`

- [ ] **Step 1: Implement Performance**

```jsx
import useSWR from "swr";
import { Inbox, AlertTriangle } from "lucide-react";
import { urls } from "../api";
import GlassCard from "../components/primitives/GlassCard";
import KpiCard from "../components/primitives/KpiCard";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import ChartLine from "../components/charts/ChartLine";
import ChartDonut from "../components/charts/ChartDonut";
import ChartBar from "../components/charts/ChartBar";
import { formatUSD, formatPct } from "../lib/format";
import { pnlColor } from "../lib/colors";

export default function Performance() {
  const { data, error, isLoading, mutate } = useSWR(urls.performance(30), {
    refreshInterval: 60_000,
  });

  if (error) return <ErrorState error={error} onRetry={() => mutate()} />;
  if (isLoading || !data) return <SkeletonList count={4} height={160} />;

  // Build daily series with C1 + C2 separate columns
  const byDay = {};
  (data.daily || []).forEach((d) => {
    if (!byDay[d.day]) byDay[d.day] = { day: d.day, c1_pnl: 0, c2_pnl: 0 };
    if (d.component === "C1") byDay[d.day].c1_pnl += d.pnl || 0;
    if (d.component === "C2") byDay[d.day].c2_pnl += d.pnl || 0;
  });
  const daysSorted = Object.values(byDay).sort((a, b) => (a.day < b.day ? -1 : 1));
  // Cumulate
  let c1 = 0, c2 = 0;
  const chartData = daysSorted.map((d) => {
    c1 += d.c1_pnl;
    c2 += d.c2_pnl;
    return { day: d.day, c1_pnl: c1, c2_pnl: c2 };
  });

  // KPIs
  const totalAlerts = data.cumulative.reduce((s, c) => s + c.alerts, 0);
  const totalResolved = data.cumulative.reduce((s, c) => s + c.alerts, 0);  // /api/perf cumulative.alerts == resolved
  const totalCorrect = data.cumulative.reduce((s, c) => s + c.correct, 0);
  const totalPnl = data.cumulative.reduce((s, c) => s + (c.pnl || 0), 0);
  const winRate = totalResolved > 0 ? totalCorrect / totalResolved : null;
  const avgPnl = totalResolved > 0 ? totalPnl / totalResolved : 0;

  const directionData = [
    { name: "Correct", value: totalCorrect },
    { name: "Incorrect", value: totalResolved - totalCorrect },
  ];

  // alignment distribution (from data.alignment)
  const alignmentData = (data.alignment || []).map((a) => ({
    label: String(a.alignment_score),
    count: a.count,
  }));
  const alignmentColors = (data.alignment || []).map((a) =>
    a.alignment_score > 0 ? "#22c55e" : a.alignment_score < 0 ? "#ef4444" : "#6b7280"
  );

  const insufficient = totalResolved < 30;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-bold">Performance</h1>

      {insufficient && (
        <div className="bg-accent-orange/10 border border-accent-orange/30 rounded-card p-4 flex items-start gap-3">
          <AlertTriangle size={18} className="text-accent-orange mt-0.5 flex-shrink-0" />
          <div className="text-sm">
            <div className="font-medium text-accent-orange">Échantillon insuffisant</div>
            <div className="text-text-secondary mt-1">
              {totalResolved}/30 minimum. Résultats indicatifs.
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Shadow P&L cumulé (30j)</h2>
        <GlassCard>
          {chartData.length === 0 ? (
            <EmptyState icon={Inbox} message="Aucune donnée P&L sur 30j" />
          ) : (
            <ChartLine
              data={chartData}
              xKey="day"
              series={[
                { key: "c1_pnl", color: "#f97316", name: "C1" },
                { key: "c2_pnl", color: "#a855f7", name: "C2" },
              ]}
            />
          )}
        </GlassCard>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total alertes" value={totalAlerts} />
        <KpiCard label="Win rate" value={formatPct(winRate)} />
        <KpiCard label="Avg P&L / alerte" value={formatUSD(avgPnl, { signed: true })} valueClass={pnlColor(avgPnl)} />
        <KpiCard label="P&L total" value={formatUSD(totalPnl, { signed: true })} valueClass={pnlColor(totalPnl)} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Direction correcte</h2>
          <GlassCard>
            {totalResolved === 0 ? (
              <EmptyState icon={Inbox} message="Aucune alerte résolue" />
            ) : (
              <ChartDonut data={directionData} />
            )}
          </GlassCard>
        </div>

        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Alignment distribution</h2>
          <GlassCard>
            {alignmentData.length === 0 ? (
              <EmptyState icon={Inbox} message="Aucune alignment data" />
            ) : (
              <ChartBar data={alignmentData} xKey="count" yKey="label" cellColors={alignmentColors} />
            )}
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Visual check**

Navigate `/performance`. Expected: ChartLine with C1 (orange) and C2 (violet), 4 KPI cards, donut + bar chart. Warning banner if <30 résolues.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/pages/Performance.jsx
git commit -m "feat(M8-B v2): build Performance page (ChartLine C1/C2 + donut + alignment)"
```

### Task 20: System page

**Files:**
- Modify: `dashboard/src/pages/System.jsx`

- [ ] **Step 1: Implement System**

```jsx
import useSWR from "swr";
import { Inbox, Power, Activity, Shield } from "lucide-react";
import { urls } from "../api";
import GlassCard from "../components/primitives/GlassCard";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import IndexerRow from "../components/domain/IndexerRow";
import { formatRelative } from "../lib/format";
import { statusColor } from "../lib/colors";

function eventIcon(eventType) {
  if (eventType === "kill_switch") return Power;
  if (eventType === "rate_limit") return Shield;
  return Activity;
}

export default function System() {
  const { data: status, error: statusError, mutate: mutateStatus } = useSWR(urls.status(), {
    refreshInterval: 30_000,
  });
  const { data: audit, error: auditError } = useSWR(urls.audit(50));

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-bold">System</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Indexers</h2>
          {statusError ? (
            <ErrorState error={statusError} onRetry={() => mutateStatus()} />
          ) : !status ? (
            <SkeletonList count={6} height={56} />
          ) : (
            <GlassCard>
              {status.indexers.map((i) => (
                <div key={i.name} className="py-2 px-3 row-hover rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-2 h-2 rounded-full ${statusColor(i.status).replace("text-", "bg-")}`}
                      />
                      <span className="font-medium">{i.name}</span>
                    </div>
                    <span className="text-xs text-text-secondary">
                      {formatRelative(i.last_synced_at)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-text-tertiary flex gap-4">
                    <span>Status: {i.status || "—"}</span>
                    <span>Duration: {i.duration_ms ?? "—"}ms</span>
                    <span>Ingested: {i.ingested_count ?? 0}</span>
                  </div>
                </div>
              ))}
            </GlassCard>
          )}
        </div>

        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Kill switches</h2>
          {!status ? (
            <SkeletonList count={4} height={48} />
          ) : status.kill_switches.length === 0 ? (
            <GlassCard>
              <EmptyState icon={Power} message="Aucun kill switch actif" />
            </GlassCard>
          ) : (
            <GlassCard>
              {status.kill_switches.map((k) => (
                <div key={k.target} className="flex items-center justify-between py-2 px-3 row-hover rounded-lg">
                  <div>
                    <div className="font-medium">{k.target}</div>
                    {k.reason && <div className="text-xs text-text-secondary">{k.reason}</div>}
                  </div>
                  <span className="px-2 py-0.5 bg-pnl-negative/10 text-pnl-negative rounded text-xs font-medium">
                    ENABLED
                  </span>
                </div>
              ))}
            </GlassCard>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Rate limits</h2>
        {!status ? (
          <SkeletonList count={3} height={48} />
        ) : status.rate_limits.length === 0 ? (
          <GlassCard>
            <EmptyState icon={Shield} message="Aucun rate limit actif" />
          </GlassCard>
        ) : (
          <GlassCard>
            {status.rate_limits.map((r) => (
              <div key={`${r.component}-${r.window}`} className="py-2 px-3 row-hover rounded-lg">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{r.component}</span>
                  <span className="text-text-secondary">{r.window}</span>
                  <span className="font-mono">{r.count}</span>
                </div>
              </div>
            ))}
          </GlassCard>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Audit log</h2>
        {auditError ? (
          <ErrorState error={auditError} />
        ) : !audit ? (
          <SkeletonList count={6} height={64} />
        ) : audit.length === 0 ? (
          <EmptyState icon={Inbox} message="Aucun événement enregistré" />
        ) : (
          <div className="flex flex-col gap-2">
            {audit.map((a) => {
              const Icon = eventIcon(a.event_type);
              return (
                <GlassCard key={a.id} className="!p-4">
                  <div className="flex items-start gap-3">
                    <Icon size={16} className="text-accent-orange mt-0.5" />
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">
                          {a.event_type} · {a.target} · {a.action}
                        </span>
                        <span className="text-xs text-text-secondary">
                          {formatRelative(a.created_at)}
                        </span>
                      </div>
                      {a.reason && (
                        <div className="text-xs text-text-secondary mt-1">{a.reason}</div>
                      )}
                      {a.actor && (
                        <div className="text-xs text-text-tertiary mt-0.5">par {a.actor}</div>
                      )}
                    </div>
                  </div>
                </GlassCard>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Visual check**

Navigate `/system`. Expected: indexers list, kill switches (or empty), rate limits, audit log cards.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/pages/System.jsx
git commit -m "feat(M8-B v2): build System page (indexers + kill switches + rate limits + audit)"
```

---

## Phase 12 — Verification & deploy

### Task 21: Run full backend test suite + frontend build

**Files:** none modified

- [ ] **Step 1: Run all dashboard tests**

```bash
uv run pytest tests/unit/test_dashboard_api.py -v
```

Expected: all tests PASS (existing 7 + new 8 = 15 total).

- [ ] **Step 2: Run full test suite (regression check)**

```bash
uv run pytest -x
```

Expected: zero failures across the project.

- [ ] **Step 3: Frontend build**

```bash
cd dashboard && npm run build && cd ..
ls -la dashboard/dist/
```

Expected: build succeeds, `dist/index.html` + assets generated. Note bundle size — should be < ~500kb gzipped.

- [ ] **Step 4: Manual frontend verification checklist**

Start backend and frontend in two terminals :

```bash
# Terminal 1 (backend)
uv run uvicorn polybot.dashboard.api:app --port 8000 --reload
# Terminal 2 (frontend)
cd dashboard && npm run dev
```

Open `http://localhost:5173` and verify each item below. Take screenshots and store in `/tmp/m8-b-v2-screenshots/` for the deploy step.

- [ ] Sidebar visible left, POLYBOT logo, 5 nav items, active state turns orange
- [ ] TopBar 4 pills (Shadow P&L, Alertes 24h, Win Rate, Indexers) + refresh button
- [ ] Overview : hero P&L card with chart, 4 KPI cards, 5 dernières alertes, indexers list, hot markets
- [ ] Click on alert in Overview → navigates correctly OR expands inline (per AlertCard implementation)
- [ ] Alerts page : 3 filter rows (composant, période, status), URL changes on click (`?component=C2&days=7`), reload preserves filters, click card → expand inline with features/alignment/PNL
- [ ] Wallets page : cards with names (Domer, Aenews2, Kickstand7…), demoted ones grayed
- [ ] Click wallet → `/wallets/:address`
- [ ] WalletDetail : header with name + adresse copyable + tier + lien Polymarket externe, 4 KPIs, ChartArea P&L, table trades, sections CEX/cluster si applicable
- [ ] Performance : ChartLine C1 vs C2, KPIs, donut direction %, bar alignment, warning banner si <30 résolues
- [ ] System : indexers expanded avec status/duration/count, kill switches (ou empty), rate limits, audit log cards
- [ ] Mobile (DevTools < 768px) : sidebar hidden, content stack, tables overflow-x
- [ ] Tablet (DevTools 768-1023px) : sidebar 64px (icons only)
- [ ] Polling : laisser Overview ouvert 90s → vérifier que `last_synced_at` sur indexers se met à jour

- [ ] **Step 5: Commit (no code change, but stamp the verification)**

```bash
git commit --allow-empty -m "chore(M8-B v2): manual frontend verification + screenshots stored"
```

### Task 22: Deploy VPS + smoke test

**Files:** none modified

- [ ] **Step 1: Push branch + merge to main**

From the worktree :

```bash
cd /Users/gabsav/Documents/Polycasquette/Code/worktrees/m8-b-v2-dashboard
git push -u origin m8-b-v2-dashboard
```

Then ask the user to open a PR or merge locally :

```bash
cd /Users/gabsav/Documents/Polycasquette/Code  # main worktree
git checkout main
git merge m8-b-v2-dashboard --no-ff
git push origin main
```

- [ ] **Step 2: SSH + pull on VPS**

(Requires US VPN active for some operations.)

```bash
ssh polybot 'cd /root/polybot && git pull && uv sync'
```

Expected: pull succeeds, no new Python dep to install.

- [ ] **Step 3: Restart polybot-bot service** (which embeds the dashboard API)

```bash
ssh polybot 'systemctl restart polybot-bot && systemctl status polybot-bot'
```

Expected: service active (running), no startup error in journal.

- [ ] **Step 4: Rsync the built `dist/` to VPS**

From local main worktree :

```bash
rsync -avz --delete dashboard/dist/ polybot:/root/polybot/dashboard/dist/
```

- [ ] **Step 5: Reload Caddy** (defensive — usually not needed for static file changes)

```bash
ssh polybot 'systemctl reload caddy'
```

- [ ] **Step 6: Smoke test prod**

(VPN US active.) Open `http://62.146.230.73:3000` in browser. Authentifie avec basicauth.

- [ ] Sidebar + TopBar visibles
- [ ] Overview charge avec data réelle (P&L, alertes, indexers, hot markets)
- [ ] Alerts charge, click sur une alerte → expand
- [ ] Wallets liste avec noms réels
- [ ] WalletDetail charge pour un wallet réel (ex: Kickstand7)
- [ ] Performance charge avec graphes
- [ ] System charge avec indexers en cours

Capture screenshots prod et stocke dans `/tmp/m8-b-v2-prod-screenshots/`.

- [ ] **Step 7: Final commit on main + cleanup worktree**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git commit --allow-empty -m "chore(M8-B v2): deploy to VPS verified — dashboard refonte complete"
git push origin main
git worktree remove worktrees/m8-b-v2-dashboard
git branch -d m8-b-v2-dashboard
```

Expected: worktree removed, branch deleted (already merged).

---

## Self-review notes

- **Spec coverage** : every spec section has at least one task. Pages 1-5 + WalletDetail = tasks 15-20. 3 nouveaux endpoints + modif markets/hot = tasks 3-7. Wipe + scaffold = task 8. Layout (Sidebar + TopBar) = tasks 10-11. Primitives + Charts + Domain = tasks 12-14.
- **System page caveats** : the spec mentioned disk/RAM and indexer history but flagged these as potentially unavailable. Task 20 omits them (no source data) — consistent with the spec's note "Si non disponible, masquer cette section". OK.
- **Frontend tests** : per spec, no Vitest in v1 — manual verification via Task 21 checklist. Consistent.
- **Endpoint /api/wallets/{address}/trades dedup** : implemented Python-side via dict (Task 6 step 3). Consistent with spec's "à traiter dans l'impl".
- **`/api/wallets` notes field** : the existing endpoint doesn't return `notes` (it returns `source` etc., see api.py:155-219). The WalletCard reads `wallet.notes` — this will be undefined and fall back to "(sans nom)". To fix : either modify the existing `/api/wallets` query to include `w.notes AS notes` in the SELECT and map it in the response dict, or accept the placeholder. Adding to Task 17 step 1: include a minor patch to `/api/wallets` to expose `notes`.

### Patch addition for Task 17 — expose `notes` on `/api/wallets`

Insert before Task 17 step 1 :

- [ ] **Task 17 pre-step: Patch `/api/wallets` to include `notes`**

In `src/polybot/dashboard/api.py`, locate `def get_wallets(con: DB):` (~line 156). Modify the SQL SELECT to add `w.notes` and the GROUP BY accordingly :

```python
"SELECT w.address, w.tier, w.active, w.source, w.added_at, "
"w.honeypot_flag, w.tier_a_confidence, w.notes, "
"COUNT(t.transaction_hash) AS trades_total, "
...
"GROUP BY w.address, w.tier, w.active, w.source, w.added_at, "
"w.honeypot_flag, w.tier_a_confidence, w.notes "
```

Then update the result dict to include `"notes": r[7],` and shift the indexes for trades_total etc. by +1. Run existing tests to confirm no regression :

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestWalletsEndpoint -v
```

Expected: PASS. Commit :

```bash
git add src/polybot/dashboard/api.py
git commit -m "feat(M8-B v2): expose notes (display name) on /api/wallets"
```

---

**Plan complete. Total: 22 tasks across 12 phases. Estimated effort: 1-2 sessions.**
