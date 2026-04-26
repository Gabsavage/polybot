# M8-B Dashboard Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only web dashboard (FastAPI + React) to visualize Polybot monitoring data from DuckDB.

**Architecture:** FastAPI backend reads DuckDB read-only per request, React SPA served as static files by Caddy with basic auth. Two separate processes: existing daemon (writes DB) + new dashboard API (reads DB). Frontend built locally, rsync'd to VPS.

**Tech Stack:** FastAPI, uvicorn, DuckDB (read-only), React 19, Vite, Tailwind CSS v4, Recharts, Caddy

---

## File Structure

### Backend
- Create: `src/polybot/dashboard/__init__.py` — empty package init
- Create: `src/polybot/dashboard/api.py` — FastAPI app with all endpoints
- Create: `deploy/polybot-dashboard.service` — systemd service
- Create: `deploy/Caddyfile` — Caddy reverse proxy + static files config
- Modify: `pyproject.toml` — add fastapi + uvicorn deps

### Frontend
- Create: `dashboard/package.json` — npm project config
- Create: `dashboard/index.html` — Vite entry HTML
- Create: `dashboard/vite.config.js` — Vite + React + Tailwind config
- Create: `dashboard/src/main.jsx` — React entry point
- Create: `dashboard/src/main.css` — Tailwind imports + design tokens
- Create: `dashboard/src/App.jsx` — Router + layout (sidebar/bottom tabs)
- Create: `dashboard/src/hooks/useFetch.js` — data fetching hook
- Create: `dashboard/src/components/KpiCard.jsx` — reusable KPI card
- Create: `dashboard/src/components/StatusDot.jsx` — green/red status indicator
- Create: `dashboard/src/components/DataTable.jsx` — sortable table component
- Create: `dashboard/src/pages/Overview.jsx` — overview page
- Create: `dashboard/src/pages/Alerts.jsx` — alerts page
- Create: `dashboard/src/pages/Wallets.jsx` — wallets page
- Create: `dashboard/src/pages/Performance.jsx` — performance page
- Create: `dashboard/src/pages/System.jsx` — system page

### Tests
- Create: `tests/unit/test_dashboard_api.py` — 6 API endpoint tests

---

### Task 1: FastAPI Backend — Dependencies + App Skeleton + Status Endpoint

**Files:**
- Modify: `pyproject.toml`
- Create: `src/polybot/dashboard/__init__.py`
- Create: `src/polybot/dashboard/api.py`
- Create: `tests/unit/test_dashboard_api.py`

- [ ] **Step 1: Write the failing test for GET /api/status**

```python
# tests/unit/test_dashboard_api.py
"""Tests for the dashboard API endpoints."""

import duckdb
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("CREATE SEQUENCE audit_log_seq START 1")
    con.execute("""
        CREATE TABLE kill_switches (
            target VARCHAR PRIMARY KEY,
            enabled BOOLEAN DEFAULT FALSE,
            reason VARCHAR,
            toggled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            toggled_by VARCHAR DEFAULT 'manual'
        )
    """)
    con.execute("""
        CREATE TABLE rate_limit_counters (
            component VARCHAR,
            "window" VARCHAR,
            count INTEGER DEFAULT 0,
            window_start TIMESTAMP,
            PRIMARY KEY (component, "window")
        )
    """)
    con.execute("""
        CREATE TABLE indexer_state (
            indexer_name VARCHAR PRIMARY KEY,
            last_synced_at TIMESTAMP,
            last_block_number BIGINT,
            last_cursor VARCHAR,
            last_run_status VARCHAR,
            last_run_duration_ms INTEGER,
            last_error VARCHAR,
            ingested_count BIGINT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE audit_log (
            id BIGINT DEFAULT nextval('audit_log_seq') PRIMARY KEY,
            event_type VARCHAR, target VARCHAR, action VARCHAR,
            reason VARCHAR, actor VARCHAR DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE alerts (
            alert_id VARCHAR PRIMARY KEY,
            component VARCHAR,
            emitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            trade_hash VARCHAR, wallet_address VARCHAR,
            condition_id VARCHAR, side VARCHAR,
            size_usd DECIMAL(18,2), price DECIMAL(6,4),
            size_suggested_usd DECIMAL(18,2),
            resolution_risk_score DECIMAL(3,2),
            telegram_message_id BIGINT,
            alignment_score INTEGER, score INTEGER,
            features_passed VARCHAR, momentum_4h DECIMAL(6,4),
            shadow_mode BOOLEAN DEFAULT TRUE,
            dedup_hash VARCHAR, tags VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE alert_outcomes (
            alert_id VARCHAR PRIMARY KEY,
            condition_id VARCHAR NOT NULL,
            resolved_at TIMESTAMP,
            resolution_outcome VARCHAR,
            direction_traded VARCHAR,
            was_direction_correct BOOLEAN,
            price_at_alert DECIMAL(6,4),
            price_at_resolution DECIMAL(6,4),
            shadow_pnl_simulated DECIMAL(18,2),
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE markets (
            condition_id VARCHAR PRIMARY KEY,
            title VARCHAR, slug VARCHAR, event_slug VARCHAR,
            volume_24h DECIMAL(18,2), liquidity_usd DECIMAL(18,2),
            end_date TIMESTAMP, active BOOLEAN DEFAULT TRUE,
            volume_cumulative_usd DECIMAL(18,2),
            category VARCHAR, status VARCHAR,
            last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE tracked_wallets (
            address VARCHAR PRIMARY KEY,
            tier VARCHAR, active BOOLEAN, source VARCHAR,
            added_at TIMESTAMP, last_reviewed_at TIMESTAMP,
            honeypot_flag BOOLEAN, honeypot_score DECIMAL(3,2),
            tier_a_confidence DECIMAL(3,2),
            notes TEXT, last_seen_timestamp BIGINT DEFAULT 0
        )
    """)
    con.execute("""
        CREATE TABLE trades (
            transaction_hash VARCHAR PRIMARY KEY,
            proxy_wallet VARCHAR NOT NULL,
            condition_id VARCHAR NOT NULL,
            asset_id VARCHAR NOT NULL,
            side VARCHAR, size_usd DECIMAL(18,2) NOT NULL,
            price DECIMAL(6,4) NOT NULL,
            outcome VARCHAR, outcome_index INTEGER,
            timestamp_unix BIGINT NOT NULL,
            timestamp_ts TIMESTAMP NOT NULL,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE resolution_risk_cache (
            condition_id VARCHAR PRIMARY KEY,
            llm_score DECIMAL(3,2),
            llm_reasons TEXT[], llm_red_flags TEXT[],
            llm_model_version VARCHAR,
            computed_at TIMESTAMP
        )
    """)
    con.close()
    return path


@pytest.fixture
def client(db_path):
    from polybot.dashboard.api import app, get_db

    def override_db():
        con = duckdb.connect(db_path, read_only=True)
        try:
            yield con
        finally:
            con.close()

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestStatusEndpoint:
    def test_status_returns_all_sections(self, client, db_path):
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO kill_switches (target, enabled, reason) VALUES ('c1', TRUE, 'test')"
        )
        con.execute(
            "INSERT INTO rate_limit_counters (component, \"window\", count, window_start) "
            "VALUES ('c1', 'hourly', 5, CURRENT_TIMESTAMP)"
        )
        con.execute(
            "INSERT INTO indexer_state (indexer_name, last_synced_at, last_run_status, "
            "last_run_duration_ms, ingested_count) "
            "VALUES ('markets_gamma', CURRENT_TIMESTAMP, 'success', 1500, 46000)"
        )
        con.close()

        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["kill_switches"]) == 1
        assert data["kill_switches"][0]["target"] == "c1"
        assert len(data["rate_limits"]) == 1
        assert data["rate_limits"][0]["component"] == "c1"
        assert len(data["indexers"]) == 1
        assert data["indexers"][0]["name"] == "markets_gamma"
        assert data["indexers"][0]["ingested_count"] == 46000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/gabsav/Documents/Polycasquette/Code && python -m pytest tests/unit/test_dashboard_api.py::TestStatusEndpoint::test_status_returns_all_sections -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'polybot.dashboard'`

- [ ] **Step 3: Add dependencies to pyproject.toml**

Add `"fastapi>=0.115"` and `"uvicorn[standard]>=0.30"` to the `dependencies` list in `pyproject.toml`.

- [ ] **Step 4: Install dependencies**

Run: `cd /Users/gabsav/Documents/Polycasquette/Code && uv sync`

- [ ] **Step 5: Create dashboard package and API module**

```python
# src/polybot/dashboard/__init__.py
```

```python
# src/polybot/dashboard/api.py
"""Polybot Dashboard API — read-only access to DuckDB monitoring data."""

from typing import Annotated

import duckdb
import structlog
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from polybot.config import Settings

logger = structlog.get_logger()

settings = Settings()

app = FastAPI(title="Polybot Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    con = duckdb.connect(str(settings.DUCKDB_PATH), read_only=True)
    try:
        yield con
    finally:
        con.close()


DB = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]


@app.get("/api/status")
def get_status(con: DB):
    kill_switches = con.execute(
        "SELECT target, enabled, reason, toggled_at "
        "FROM kill_switches WHERE enabled = TRUE"
    ).fetchall()

    rate_limits = con.execute(
        'SELECT component, "window", count, window_start FROM rate_limit_counters'
    ).fetchall()

    indexers = con.execute(
        "SELECT indexer_name, last_run_status, last_synced_at, "
        "last_run_duration_ms, ingested_count "
        "FROM indexer_state ORDER BY indexer_name"
    ).fetchall()

    return {
        "kill_switches": [
            {"target": r[0], "enabled": r[1], "reason": r[2], "toggled_at": str(r[3]) if r[3] else None}
            for r in kill_switches
        ],
        "rate_limits": [
            {"component": r[0], "window": r[1], "count": r[2], "window_start": str(r[3]) if r[3] else None}
            for r in rate_limits
        ],
        "indexers": [
            {"name": r[0], "status": r[1], "last_synced_at": str(r[2]) if r[2] else None,
             "duration_ms": r[3], "ingested_count": r[4]}
            for r in indexers
        ],
    }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /Users/gabsav/Documents/Polycasquette/Code && python -m pytest tests/unit/test_dashboard_api.py::TestStatusEndpoint::test_status_returns_all_sections -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/polybot/dashboard/__init__.py src/polybot/dashboard/api.py tests/unit/test_dashboard_api.py
git commit -m "feat(M8-B): FastAPI dashboard skeleton + /api/status endpoint + test"
```

---

### Task 2: Backend — All Remaining Endpoints + Tests

**Files:**
- Modify: `src/polybot/dashboard/api.py`
- Modify: `tests/unit/test_dashboard_api.py`

- [ ] **Step 1: Write failing tests for alerts, wallets, performance, costs endpoints**

Add to `tests/unit/test_dashboard_api.py`:

```python
def _seed_alerts(db_path):
    """Insert test alerts with outcomes and markets."""
    con = duckdb.connect(db_path)
    # Markets
    con.execute(
        "INSERT INTO markets (condition_id, title, slug, event_slug, volume_24h, active) "
        "VALUES ('cond_1', 'Will X happen?', 'will-x', 'event-x', 50000, TRUE)"
    )
    con.execute(
        "INSERT INTO markets (condition_id, title, slug, event_slug, volume_24h, active) "
        "VALUES ('cond_2', 'Will Y happen?', 'will-y', 'event-y', 20000, TRUE)"
    )
    # C1 alerts
    for i in range(2):
        con.execute(
            "INSERT INTO alerts (alert_id, component, emitted_at, wallet_address, condition_id, "
            "side, size_usd, price, score, alignment_score) "
            "VALUES (?, 'C1', CURRENT_TIMESTAMP - INTERVAL '1 DAY', '0xwallet_0', 'cond_1', "
            "'BUY', 500, 0.65, NULL, NULL)",
            [f"al_c1_{i}"],
        )
    # C2 alert
    con.execute(
        "INSERT INTO alerts (alert_id, component, emitted_at, wallet_address, condition_id, "
        "side, size_usd, price, score, alignment_score, features_passed, momentum_4h) "
        "VALUES ('al_c2_0', 'C2', CURRENT_TIMESTAMP - INTERVAL '2 DAY', '0xwallet_1', 'cond_2', "
        "'BUY', 300, 0.40, 5, 1, 'vol_spike,smart_money', 0.05)"
    )
    # Outcomes
    con.execute(
        "INSERT INTO alert_outcomes (alert_id, condition_id, resolution_outcome, "
        "was_direction_correct, shadow_pnl_simulated, price_at_alert, price_at_resolution) "
        "VALUES ('al_c1_0', 'cond_1', 'YES', TRUE, 25.00, 0.65, 0.90)"
    )
    con.execute(
        "INSERT INTO alert_outcomes (alert_id, condition_id, resolution_outcome, "
        "was_direction_correct, shadow_pnl_simulated, price_at_alert, price_at_resolution) "
        "VALUES ('al_c2_0', 'cond_2', 'NO', FALSE, -15.00, 0.40, 0.10)"
    )
    # Tracked wallets (5 tier A)
    for i in range(5):
        con.execute(
            "INSERT INTO tracked_wallets (address, tier, active, notes, tier_a_confidence) "
            "VALUES (?, 'A', ?, ?, 0.85)",
            [f"0xwallet_{i}", i < 4, f"wallet_{i}"],
        )
    # Trades for wallets 0-2
    for i in range(3):
        for j in range(4):
            con.execute(
                "INSERT INTO trades (transaction_hash, proxy_wallet, condition_id, asset_id, "
                "side, size_usd, price, timestamp_unix, timestamp_ts) "
                "VALUES (?, ?, 'cond_1', 'asset_1', 'BUY', 100, 0.65, 1714100000, "
                "CURRENT_TIMESTAMP - INTERVAL '1 DAY')",
                [f"tx_{i}_{j}", f"0xwallet_{i}"],
            )
    # LLM cache (50 entries this month)
    for i in range(50):
        con.execute(
            "INSERT INTO resolution_risk_cache (condition_id, llm_score, computed_at) "
            "VALUES (?, 0.5, CURRENT_TIMESTAMP)",
            [f"risk_{i}"],
        )
    con.close()


class TestAlertsEndpoint:
    def test_alerts_returns_all(self, client, db_path):
        _seed_alerts(db_path)
        resp = client.get("/api/alerts?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert any(a["component"] == "C1" for a in data)
        assert any(a["component"] == "C2" for a in data)
        resolved = [a for a in data if a.get("resolution_outcome")]
        assert len(resolved) == 2

    def test_alerts_filter_c1(self, client, db_path):
        _seed_alerts(db_path)
        resp = client.get("/api/alerts?days=7&component=C1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(a["component"] == "C1" for a in data)


class TestWalletsEndpoint:
    def test_wallets_returns_metrics(self, client, db_path):
        _seed_alerts(db_path)
        resp = client.get("/api/wallets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        w0 = next(w for w in data if w["address"] == "0xwallet_0")
        assert w0["trades_total"] == 4
        assert w0["active"] is True


class TestPerformanceEndpoint:
    def test_performance_returns_series(self, client, db_path):
        _seed_alerts(db_path)
        resp = client.get("/api/performance?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert "daily" in data
        assert "cumulative" in data
        assert "alignment" in data
        total_pnl = sum(
            c["pnl"] for c in data["cumulative"] if c["pnl"] is not None
        )
        assert total_pnl == pytest.approx(10.0, abs=0.01)


class TestCostsEndpoint:
    def test_costs_estimate(self, client, db_path):
        _seed_alerts(db_path)
        resp = client.get("/api/costs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["llm_calls_month"] == 50
        assert data["llm_cost_estimate"] == pytest.approx(0.05)
        assert data["vps_monthly"] == 4.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/gabsav/Documents/Polycasquette/Code && python -m pytest tests/unit/test_dashboard_api.py -v -k "not TestStatus"`
Expected: FAIL — endpoints not implemented

- [ ] **Step 3: Implement all remaining endpoints in api.py**

Add to `src/polybot/dashboard/api.py`:

```python
@app.get("/api/alerts")
def get_alerts(con: DB, days: int = Query(default=7, ge=1, le=365), component: str | None = None):
    params = [days]
    where_component = ""
    if component:
        where_component = "AND a.component = ?"
        params.append(component)

    rows = con.execute(
        f"""
        SELECT
            a.alert_id, a.component, a.emitted_at, a.wallet_address, a.condition_id,
            a.side, a.size_usd, a.price, a.score, a.alignment_score,
            a.shadow_mode, a.features_passed,
            m.title, m.slug,
            ao.resolution_outcome, ao.was_direction_correct, ao.shadow_pnl_simulated,
            ao.price_at_alert, ao.price_at_resolution
        FROM alerts a
        LEFT JOIN markets m ON a.condition_id = m.condition_id
        LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
        WHERE a.emitted_at >= CURRENT_DATE - INTERVAL '? DAY'
          {where_component}
        ORDER BY a.emitted_at DESC
        LIMIT 200
        """,
        params,
    ).fetchall()

    return [
        {
            "alert_id": r[0], "component": r[1],
            "emitted_at": str(r[2]) if r[2] else None,
            "wallet_address": r[3], "condition_id": r[4],
            "side": r[5], "size_usd": float(r[6]) if r[6] else None,
            "price": float(r[7]) if r[7] else None,
            "score": r[8], "alignment_score": r[9],
            "shadow_mode": r[10], "features_passed": r[11],
            "market_title": r[12], "market_slug": r[13],
            "resolution_outcome": r[14], "was_direction_correct": r[15],
            "shadow_pnl_simulated": float(r[16]) if r[16] else None,
            "price_at_alert": float(r[17]) if r[17] else None,
            "price_at_resolution": float(r[18]) if r[18] else None,
        }
        for r in rows
    ]


@app.get("/api/wallets")
def get_wallets(con: DB):
    wallet_rows = con.execute("""
        SELECT
            tw.address, tw.tier, tw.active, tw.notes, tw.tier_a_confidence,
            tw.added_at, tw.honeypot_flag,
            COUNT(t.transaction_hash) as trades_total,
            COUNT(t.transaction_hash) FILTER (
                WHERE t.timestamp_ts >= CURRENT_DATE - INTERVAL '7 DAY'
            ) as trades_7d,
            MAX(t.timestamp_ts) as last_trade,
            SUM(t.size_usd) as total_volume
        FROM tracked_wallets tw
        LEFT JOIN trades t ON tw.address = t.proxy_wallet
        WHERE tw.tier = 'A'
        GROUP BY tw.address, tw.tier, tw.active, tw.notes, tw.tier_a_confidence,
                 tw.added_at, tw.honeypot_flag
        ORDER BY tw.active DESC, trades_total DESC
    """).fetchall()

    perf_rows = con.execute("""
        SELECT
            a.wallet_address,
            COUNT(*) FILTER (WHERE ao.resolution_outcome NOT IN ('PENDING')) as resolved,
            COUNT(*) FILTER (WHERE ao.was_direction_correct = TRUE) as correct,
            SUM(ao.shadow_pnl_simulated) FILTER (
                WHERE ao.resolution_outcome NOT IN ('PENDING')
            ) as pnl
        FROM alerts a
        JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
        WHERE a.wallet_address IN (SELECT address FROM tracked_wallets WHERE tier = 'A')
        GROUP BY a.wallet_address
    """).fetchall()
    perf = {r[0]: {"resolved": r[1], "correct": r[2], "pnl": float(r[3]) if r[3] else 0.0} for r in perf_rows}

    return [
        {
            "address": r[0], "tier": r[1], "active": r[2], "notes": r[3],
            "confidence": float(r[4]) if r[4] else None,
            "added_at": str(r[5]) if r[5] else None,
            "honeypot_flag": r[6],
            "trades_total": r[7], "trades_7d": r[8],
            "last_trade": str(r[9]) if r[9] else None,
            "total_volume": float(r[10]) if r[10] else 0.0,
            "resolved": perf.get(r[0], {}).get("resolved", 0),
            "correct": perf.get(r[0], {}).get("correct", 0),
            "pnl": perf.get(r[0], {}).get("pnl", 0.0),
            "win_rate": (
                perf[r[0]]["correct"] / perf[r[0]]["resolved"] * 100
                if r[0] in perf and perf[r[0]]["resolved"] > 0
                else None
            ),
        }
        for r in wallet_rows
    ]


@app.get("/api/performance")
def get_performance(con: DB, days: int = Query(default=30, ge=1, le=365)):
    daily = con.execute(
        """
        SELECT
            DATE_TRUNC('day', a.emitted_at) as day,
            a.component,
            COUNT(*) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL AND ao.resolution_outcome != 'PENDING'
            ) as resolved,
            COUNT(*) FILTER (WHERE ao.was_direction_correct = TRUE) as correct,
            SUM(ao.shadow_pnl_simulated) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL AND ao.resolution_outcome != 'PENDING'
            ) as pnl
        FROM alerts a
        LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
        WHERE a.emitted_at >= CURRENT_DATE - INTERVAL ? DAY
        GROUP BY day, a.component
        ORDER BY day
        """,
        [days],
    ).fetchall()

    cumulative = con.execute("""
        SELECT
            a.component,
            COUNT(*) as total,
            COUNT(*) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL AND ao.resolution_outcome != 'PENDING'
            ) as resolved,
            COUNT(*) FILTER (WHERE ao.was_direction_correct = TRUE) as correct,
            SUM(ao.shadow_pnl_simulated) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL AND ao.resolution_outcome != 'PENDING'
            ) as pnl
        FROM alerts a
        LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
        GROUP BY a.component
    """).fetchall()

    alignment = con.execute("""
        SELECT alignment_score, COUNT(*)
        FROM alerts WHERE alignment_score IS NOT NULL
        GROUP BY alignment_score
        ORDER BY alignment_score
    """).fetchall()

    return {
        "daily": [
            {"day": str(r[0])[:10], "component": r[1], "resolved": r[2],
             "correct": r[3], "pnl": float(r[4]) if r[4] else 0.0}
            for r in daily
        ],
        "cumulative": [
            {"component": r[0], "total": r[1], "resolved": r[2],
             "correct": r[3], "pnl": float(r[4]) if r[4] else 0.0}
            for r in cumulative
        ],
        "alignment": [
            {"score": r[0], "count": r[1]} for r in alignment
        ],
    }


@app.get("/api/markets/hot")
def get_hot_markets(con: DB):
    rows = con.execute("""
        SELECT
            m.condition_id, m.title, m.slug, m.event_slug,
            m.volume_24h, m.liquidity_usd, m.end_date,
            COUNT(a.alert_id) as alert_count
        FROM markets m
        LEFT JOIN alerts a ON m.condition_id = a.condition_id
            AND a.emitted_at >= CURRENT_DATE - INTERVAL '7 DAY'
        WHERE m.active = TRUE AND m.volume_24h > 10000
        GROUP BY m.condition_id, m.title, m.slug, m.event_slug,
                 m.volume_24h, m.liquidity_usd, m.end_date
        ORDER BY m.volume_24h DESC
        LIMIT 50
    """).fetchall()

    return [
        {
            "condition_id": r[0], "title": r[1], "slug": r[2], "event_slug": r[3],
            "volume_24h": float(r[4]) if r[4] else 0.0,
            "liquidity_usd": float(r[5]) if r[5] else 0.0,
            "end_date": str(r[6]) if r[6] else None,
            "alert_count": r[7],
        }
        for r in rows
    ]


@app.get("/api/audit")
def get_audit(con: DB, limit: int = Query(default=50, ge=1, le=200)):
    rows = con.execute(
        "SELECT id, event_type, target, action, reason, actor, created_at "
        "FROM audit_log ORDER BY created_at DESC LIMIT ?",
        [limit],
    ).fetchall()

    return [
        {
            "id": r[0], "event_type": r[1], "target": r[2], "action": r[3],
            "reason": r[4], "actor": r[5],
            "created_at": str(r[6]) if r[6] else None,
        }
        for r in rows
    ]


@app.get("/api/costs")
def get_costs(con: DB):
    llm_calls = con.execute(
        "SELECT COUNT(*) FROM resolution_risk_cache "
        "WHERE computed_at >= DATE_TRUNC('month', CURRENT_DATE)"
    ).fetchone()[0]

    return {
        "llm_calls_month": llm_calls,
        "llm_cost_estimate": round(llm_calls * 0.001, 2),
        "vps_monthly": 4.0,
    }


@app.get("/api/c2/features")
def get_c2_features(con: DB, condition_id: str = Query(...)):
    rows = con.execute(
        """
        SELECT
            a.alert_id, a.score, a.features_passed, a.momentum_4h,
            a.side, a.size_usd, a.emitted_at,
            ao.resolution_outcome, ao.was_direction_correct, ao.shadow_pnl_simulated
        FROM alerts a
        LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
        WHERE a.condition_id = ? AND a.component = 'C2'
        ORDER BY a.emitted_at DESC
        """,
        [condition_id],
    ).fetchall()

    return [
        {
            "alert_id": r[0], "score": r[1], "features_passed": r[2],
            "momentum_4h": float(r[3]) if r[3] else None,
            "side": r[4], "size_usd": float(r[5]) if r[5] else None,
            "emitted_at": str(r[6]) if r[6] else None,
            "resolution_outcome": r[7], "was_direction_correct": r[8],
            "shadow_pnl_simulated": float(r[9]) if r[9] else None,
        }
        for r in rows
    ]
```

**Important note on DuckDB parameterized INTERVAL**: DuckDB does not support `INTERVAL ? DAY` with parameterized queries. You must use f-string interpolation for the interval value (e.g., `f"INTERVAL '{days} DAY'"`) while still validating `days` via FastAPI's `Query(ge=1, le=365)`. The `get_alerts` endpoint similarly cannot use `?` for the INTERVAL — use validated f-string. The implementer must adjust the SQL accordingly; the existing `weekly_report.py` shows the correct pattern (`f"INTERVAL {interval}"`).

- [ ] **Step 4: Run all tests**

Run: `cd /Users/gabsav/Documents/Polycasquette/Code && python -m pytest tests/unit/test_dashboard_api.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Lint check**

Run: `cd /Users/gabsav/Documents/Polycasquette/Code && ruff check src/polybot/dashboard/ tests/unit/test_dashboard_api.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add src/polybot/dashboard/api.py tests/unit/test_dashboard_api.py
git commit -m "feat(M8-B): all dashboard API endpoints — alerts, wallets, performance, costs, audit, c2, markets"
```

---

### Task 3: Deploy Config — Systemd Service + Caddyfile

**Files:**
- Create: `deploy/polybot-dashboard.service`
- Create: `deploy/Caddyfile`

- [ ] **Step 1: Create systemd service file**

```ini
# deploy/polybot-dashboard.service
[Unit]
Description=Polybot Dashboard API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/polybot
Environment=PYTHONPATH=/root/polybot/src
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/root/polybot/.env
ExecStart=/root/polybot/.venv/bin/uvicorn polybot.dashboard.api:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Create Caddyfile**

```
# deploy/Caddyfile
:3000 {
    basicauth {
        polybot {$DASHBOARD_BCRYPT_HASH}
    }

    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle {
        root * /root/polybot/dashboard/dist
        file_server
        try_files {path} /index.html
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add deploy/polybot-dashboard.service deploy/Caddyfile
git commit -m "feat(M8-B): deploy config — dashboard systemd service + Caddyfile"
```

---

### Task 4: Frontend — Vite + React + Tailwind Scaffold

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/index.html`
- Create: `dashboard/vite.config.js`
- Create: `dashboard/src/main.jsx`
- Create: `dashboard/src/main.css`
- Create: `dashboard/.gitignore`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "polybot-dashboard",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.0.0",
    "recharts": "^2.15.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.4.0",
    "vite": "^6.0.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0"
  }
}
```

- [ ] **Step 2: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Polybot Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet" />
  </head>
  <body class="bg-[#0a0a0f] text-[#e4e4e7]">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Create vite.config.js**

```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
```

- [ ] **Step 4: Create main.css with design tokens**

```css
/* dashboard/src/main.css */
@import "tailwindcss";

@theme {
  --color-bg: #0a0a0f;
  --color-card: #12121a;
  --color-border: #1e1e2e;
  --color-text: #e4e4e7;
  --color-text-dim: #71717a;
  --color-accent: #06b6d4;
  --color-positive: #22c55e;
  --color-negative: #ef4444;
  --color-warning: #f59e0b;
  --font-mono: "JetBrains Mono", monospace;
}
```

- [ ] **Step 5: Create main.jsx**

```jsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./main.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);
```

- [ ] **Step 6: Create .gitignore**

```
node_modules/
dist/
.vite/
```

- [ ] **Step 7: Install dependencies and verify build**

Run:
```bash
cd /Users/gabsav/Documents/Polycasquette/Code/dashboard && npm install
```

- [ ] **Step 8: Commit**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git add dashboard/package.json dashboard/index.html dashboard/vite.config.js dashboard/src/main.jsx dashboard/src/main.css dashboard/.gitignore dashboard/package-lock.json
git commit -m "feat(M8-B): frontend scaffold — Vite + React + Tailwind + design tokens"
```

---

### Task 5: Frontend — Layout + useFetch Hook + Shared Components

**Files:**
- Create: `dashboard/src/App.jsx`
- Create: `dashboard/src/hooks/useFetch.js`
- Create: `dashboard/src/components/KpiCard.jsx`
- Create: `dashboard/src/components/StatusDot.jsx`
- Create: `dashboard/src/components/DataTable.jsx`

- [ ] **Step 1: Create useFetch hook**

```jsx
// dashboard/src/hooks/useFetch.js
import { useState, useEffect, useCallback } from "react";

export default function useFetch(url, { refreshInterval = 0 } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(() => {
    setLoading(true);
    setError(null);
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.json();
      })
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [url]);

  useEffect(() => {
    fetchData();
    if (refreshInterval > 0) {
      const id = setInterval(fetchData, refreshInterval);
      return () => clearInterval(id);
    }
  }, [fetchData, refreshInterval]);

  return { data, loading, error, refetch: fetchData };
}
```

- [ ] **Step 2: Create StatusDot component**

```jsx
// dashboard/src/components/StatusDot.jsx
export default function StatusDot({ status, size = "sm" }) {
  const colors = {
    success: "bg-positive",
    failed: "bg-negative",
    running: "bg-warning",
    pending: "bg-text-dim",
  };
  const sizes = { sm: "h-2 w-2", md: "h-3 w-3" };

  return (
    <span
      className={`inline-block rounded-full ${colors[status] || colors.pending} ${sizes[size] || sizes.sm}`}
    />
  );
}
```

- [ ] **Step 3: Create KpiCard component**

```jsx
// dashboard/src/components/KpiCard.jsx
export default function KpiCard({ label, value, sub, color }) {
  const colorClass = {
    positive: "text-positive",
    negative: "text-negative",
    accent: "text-accent",
    warning: "text-warning",
  }[color] || "text-text";

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-wider text-text-dim">{label}</p>
      <p className={`mt-1 font-mono text-2xl font-bold ${colorClass}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-text-dim">{sub}</p>}
    </div>
  );
}
```

- [ ] **Step 4: Create DataTable component**

```jsx
// dashboard/src/components/DataTable.jsx
import { useState } from "react";

export default function DataTable({ columns, data, onRowClick, rowClassName }) {
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState("asc");

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const sorted = sortKey
    ? [...data].sort((a, b) => {
        const av = a[sortKey], bv = b[sortKey];
        if (av == null) return 1;
        if (bv == null) return -1;
        const cmp = av < bv ? -1 : av > bv ? 1 : 0;
        return sortDir === "asc" ? cmp : -cmp;
      })
    : data;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-text-dim">
            {columns.map((col) => (
              <th
                key={col.key}
                className="cursor-pointer px-3 py-2 hover:text-accent"
                onClick={() => col.sortable !== false && handleSort(col.key)}
              >
                {col.label}
                {sortKey === col.key && (sortDir === "asc" ? " ▲" : " ▼")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={i}
              className={`border-b border-border/50 hover:bg-card/80 ${
                onRowClick ? "cursor-pointer" : ""
              } ${rowClassName ? rowClassName(row) : ""}`}
              onClick={() => onRowClick && onRowClick(row)}
            >
              {columns.map((col) => (
                <td key={col.key} className="px-3 py-2 font-mono">
                  {col.render ? col.render(row[col.key], row) : row[col.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 5: Create App.jsx with layout and routing**

```jsx
// dashboard/src/App.jsx
import { Routes, Route, NavLink, useLocation } from "react-router-dom";
import Overview from "./pages/Overview";
import Alerts from "./pages/Alerts";
import Wallets from "./pages/Wallets";
import Performance from "./pages/Performance";
import System from "./pages/System";

const NAV = [
  { path: "/", label: "Overview", icon: "◉" },
  { path: "/alerts", label: "Alerts", icon: "⚡" },
  { path: "/wallets", label: "Wallets", icon: "◆" },
  { path: "/performance", label: "Perf", icon: "△" },
  { path: "/system", label: "System", icon: "⚙" },
];

function Sidebar() {
  return (
    <nav className="hidden md:flex md:w-48 flex-col border-r border-border bg-card p-4">
      <h1 className="mb-8 font-mono text-xl font-bold text-accent">POLYBOT</h1>
      {NAV.map((n) => (
        <NavLink
          key={n.path}
          to={n.path}
          end={n.path === "/"}
          className={({ isActive }) =>
            `mb-1 rounded px-3 py-2 text-sm transition-colors ${
              isActive ? "bg-accent/10 text-accent" : "text-text-dim hover:text-text"
            }`
          }
        >
          <span className="mr-2">{n.icon}</span>
          {n.label}
        </NavLink>
      ))}
    </nav>
  );
}

function MobileNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex border-t border-border bg-card md:hidden">
      {NAV.map((n) => (
        <NavLink
          key={n.path}
          to={n.path}
          end={n.path === "/"}
          className={({ isActive }) =>
            `flex flex-1 flex-col items-center py-2 text-xs ${
              isActive ? "text-accent" : "text-text-dim"
            }`
          }
        >
          <span className="text-lg">{n.icon}</span>
          {n.label}
        </NavLink>
      ))}
    </nav>
  );
}

export default function App() {
  return (
    <div className="flex h-screen bg-bg">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-4 pb-20 md:p-6 md:pb-6">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/wallets" element={<Wallets />} />
          <Route path="/performance" element={<Performance />} />
          <Route path="/system" element={<System />} />
        </Routes>
      </main>
      <MobileNav />
    </div>
  );
}
```

- [ ] **Step 6: Create placeholder page files**

Create each page with a minimal placeholder so the app compiles:

```jsx
// dashboard/src/pages/Overview.jsx
export default function Overview() {
  return <div className="text-text-dim">Overview — loading...</div>;
}
```

```jsx
// dashboard/src/pages/Alerts.jsx
export default function Alerts() {
  return <div className="text-text-dim">Alerts — loading...</div>;
}
```

```jsx
// dashboard/src/pages/Wallets.jsx
export default function Wallets() {
  return <div className="text-text-dim">Wallets — loading...</div>;
}
```

```jsx
// dashboard/src/pages/Performance.jsx
export default function Performance() {
  return <div className="text-text-dim">Performance — loading...</div>;
}
```

```jsx
// dashboard/src/pages/System.jsx
export default function System() {
  return <div className="text-text-dim">System — loading...</div>;
}
```

- [ ] **Step 7: Verify dev server starts**

Run:
```bash
cd /Users/gabsav/Documents/Polycasquette/Code/dashboard && npm run dev
```
Expected: Vite dev server starts, visit http://localhost:5173, see sidebar + "Overview — loading..."

- [ ] **Step 8: Verify build succeeds**

Run:
```bash
cd /Users/gabsav/Documents/Polycasquette/Code/dashboard && npm run build
```
Expected: `dist/` directory created

- [ ] **Step 9: Commit**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git add dashboard/src/
git commit -m "feat(M8-B): layout + routing + useFetch + shared components (KpiCard, StatusDot, DataTable)"
```

---

### Task 6: Frontend — Overview Page

**Files:**
- Modify: `dashboard/src/pages/Overview.jsx`

- [ ] **Step 1: Implement Overview page**

```jsx
// dashboard/src/pages/Overview.jsx
import useFetch from "../hooks/useFetch";
import KpiCard from "../components/KpiCard";
import StatusDot from "../components/StatusDot";
import { AreaChart, Area, LineChart, Line, ResponsiveContainer, Tooltip, XAxis } from "recharts";

export default function Overview() {
  const { data: status, loading: statusLoading } = useFetch("/api/status", { refreshInterval: 60000 });
  const { data: perf } = useFetch("/api/performance?days=30", { refreshInterval: 60000 });
  const { data: alerts } = useFetch("/api/alerts?days=7", { refreshInterval: 60000 });
  const { data: wallets } = useFetch("/api/wallets", { refreshInterval: 60000 });
  const { data: costs } = useFetch("/api/costs", { refreshInterval: 60000 });

  if (statusLoading) return <p className="text-text-dim">Loading...</p>;

  const allOk = status?.indexers?.every((ix) => ix.status === "success");
  const alerts24h = alerts?.filter(
    (a) => new Date(a.emitted_at) > new Date(Date.now() - 86400000)
  ).length ?? 0;

  const cumul = perf?.cumulative ?? [];
  const totalPnl = cumul.reduce((s, c) => s + (c.pnl || 0), 0);
  const totalResolved = cumul.reduce((s, c) => s + c.resolved, 0);
  const totalCorrect = cumul.reduce((s, c) => s + c.correct, 0);
  const winRate = totalResolved > 0 ? (totalCorrect / totalResolved * 100).toFixed(1) : "—";
  const winColor = totalResolved === 0 ? "accent" : parseFloat(winRate) > 55 ? "positive" : parseFloat(winRate) < 45 ? "negative" : "warning";

  const activeWallets = wallets?.filter((w) => w.active && w.trades_7d > 0).length ?? 0;
  const totalWallets = wallets?.length ?? 0;

  // Build sparkline data: alerts per day (last 7 days)
  const alertsByDay = {};
  (alerts || []).forEach((a) => {
    const day = a.emitted_at?.slice(0, 10);
    if (day) alertsByDay[day] = (alertsByDay[day] || 0) + 1;
  });
  const alertSpark = Object.entries(alertsByDay)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, count]) => ({ day: day.slice(5), count }));

  // Build P&L sparkline from daily data
  let cumPnl = 0;
  const pnlSpark = (perf?.daily || [])
    .reduce((acc, d) => {
      const existing = acc.find((x) => x.day === d.day);
      if (existing) {
        existing.pnl += d.pnl || 0;
      } else {
        acc.push({ day: d.day, pnl: d.pnl || 0 });
      }
      return acc;
    }, [])
    .sort((a, b) => a.day.localeCompare(b.day))
    .map((d) => {
      cumPnl += d.pnl;
      return { day: d.day.slice(5), pnl: parseFloat(cumPnl.toFixed(2)) };
    });

  const pnlSign = totalPnl >= 0 ? "+" : "";
  const pnlColor = totalPnl >= 0 ? "positive" : "negative";

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <h1 className="font-mono text-2xl font-bold text-accent">POLYBOT</h1>
        <StatusDot status={allOk ? "success" : "failed"} size="md" />
        <span className="text-xs text-text-dim">
          {allOk ? "All systems operational" : "Issues detected"}
        </span>
      </div>

      {/* KPI Cards */}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard label="Alertes 24h" value={alerts24h} color="accent" />
        <KpiCard
          label="Shadow P&L"
          value={`${pnlSign}$${Math.abs(totalPnl).toFixed(2)}`}
          color={pnlColor}
          sub="cumul"
        />
        <KpiCard label="Win Rate" value={winRate === "—" ? "—" : `${winRate}%`} color={winColor} sub={totalResolved > 0 ? `${totalCorrect}/${totalResolved}` : null} />
        <KpiCard label="Wallets Tier A" value={`${activeWallets}/${totalWallets}`} color="accent" sub="actifs cette semaine" />
      </div>

      {/* Sparklines */}
      <div className="mb-6 grid gap-3 md:grid-cols-2">
        {alertSpark.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="mb-2 text-xs uppercase tracking-wider text-text-dim">Alertes / jour (7j)</p>
            <ResponsiveContainer width="100%" height={80}>
              <AreaChart data={alertSpark}>
                <defs>
                  <linearGradient id="cyanGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#71717a" }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: "#12121a", border: "1px solid #1e1e2e", fontSize: 12 }} />
                <Area type="monotone" dataKey="count" stroke="#06b6d4" fill="url(#cyanGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
        {pnlSpark.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="mb-2 text-xs uppercase tracking-wider text-text-dim">Shadow P&L cumulé (30j)</p>
            <ResponsiveContainer width="100%" height={80}>
              <LineChart data={pnlSpark}>
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#71717a" }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: "#12121a", border: "1px solid #1e1e2e", fontSize: 12 }} />
                <Line type="monotone" dataKey="pnl" stroke={totalPnl >= 0 ? "#22c55e" : "#ef4444"} dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Kill Switches Banner */}
      {status?.kill_switches?.length > 0 && (
        <div className="mb-4 rounded-lg border border-negative/50 bg-negative/10 p-3 text-sm text-negative">
          Kill switches actifs: {status.kill_switches.map((ks) => ks.target).join(", ")}
        </div>
      )}

      {/* Indexers Table */}
      <div className="mb-6 rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">Indexers</p>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase text-text-dim">
              <th className="px-2 py-1">Name</th>
              <th className="px-2 py-1">Status</th>
              <th className="px-2 py-1">Last Sync</th>
              <th className="px-2 py-1 hidden sm:table-cell">Duration</th>
              <th className="px-2 py-1 hidden sm:table-cell">Count</th>
            </tr>
          </thead>
          <tbody>
            {(status?.indexers || []).map((ix) => (
              <tr key={ix.name} className="border-b border-border/50">
                <td className="px-2 py-1.5 font-mono text-xs">{ix.name}</td>
                <td className="px-2 py-1.5"><StatusDot status={ix.status} /></td>
                <td className="px-2 py-1.5 text-xs text-text-dim">{ix.last_synced_at?.slice(0, 19) || "—"}</td>
                <td className="px-2 py-1.5 text-xs text-text-dim hidden sm:table-cell">{ix.duration_ms ? `${ix.duration_ms}ms` : "—"}</td>
                <td className="px-2 py-1.5 font-mono text-xs hidden sm:table-cell">{ix.ingested_count?.toLocaleString() || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Costs */}
      {costs && (
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-2 text-xs uppercase tracking-wider text-text-dim">Costs (month)</p>
          <div className="flex gap-6 text-sm">
            <span>LLM: <span className="font-mono text-accent">${costs.llm_cost_estimate}</span> ({costs.llm_calls_month} calls)</span>
            <span>VPS: <span className="font-mono text-accent">${costs.vps_monthly}/mo</span></span>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Start dev server with API backend running, verify page renders**

Run backend: `cd /Users/gabsav/Documents/Polycasquette/Code && uvicorn polybot.dashboard.api:app --host 127.0.0.1 --port 8000`
Run frontend: `cd /Users/gabsav/Documents/Polycasquette/Code/dashboard && npm run dev`
Visit: http://localhost:5173 — verify KPI cards, sparklines, indexers table render

- [ ] **Step 3: Commit**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git add dashboard/src/pages/Overview.jsx
git commit -m "feat(M8-B): Overview page — KPIs, sparklines, indexers, kill switch banner, costs"
```

---

### Task 7: Frontend — Alerts Page

**Files:**
- Modify: `dashboard/src/pages/Alerts.jsx`

- [ ] **Step 1: Implement Alerts page**

```jsx
// dashboard/src/pages/Alerts.jsx
import { useState } from "react";
import useFetch from "../hooks/useFetch";
import DataTable from "../components/DataTable";

export default function Alerts() {
  const [days, setDays] = useState(7);
  const [component, setComponent] = useState(null);
  const [expanded, setExpanded] = useState(null);

  const params = new URLSearchParams({ days });
  if (component) params.set("component", component);
  const { data, loading, refetch } = useFetch(`/api/alerts?${params}`);

  const columns = [
    {
      key: "emitted_at", label: "Date", sortable: true,
      render: (v) => v?.slice(0, 16).replace("T", " ") || "—",
    },
    { key: "component", label: "Comp", sortable: true },
    {
      key: "market_title", label: "Market", sortable: false,
      render: (v) => (
        <span className="max-w-[200px] truncate inline-block" title={v}>{v || "—"}</span>
      ),
    },
    { key: "side", label: "Side", sortable: true },
    {
      key: "size_usd", label: "Size", sortable: true,
      render: (v) => v != null ? `$${Number(v).toFixed(0)}` : "—",
    },
    {
      key: "price", label: "Price", sortable: true,
      render: (v) => v != null ? Number(v).toFixed(2) : "—",
    },
    { key: "score", label: "Score", sortable: true, render: (v) => v ?? "—" },
    {
      key: "alignment_score", label: "Align", sortable: true,
      render: (v) =>
        v === 1 ? "📈" : v === -1 ? "📉" : v === 0 ? "➡️" : "—",
    },
    {
      key: "resolution_outcome", label: "Status", sortable: true,
      render: (v, row) => {
        if (!v || v === "PENDING")
          return <span className="text-text-dim">pending</span>;
        return row.was_direction_correct ? (
          <span className="text-positive">correct</span>
        ) : (
          <span className="text-negative">incorrect</span>
        );
      },
    },
  ];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h2 className="font-mono text-lg font-bold text-text">Alerts</h2>
        <div className="flex gap-1 rounded border border-border bg-card text-xs">
          {[null, "C1", "C2"].map((c) => (
            <button
              key={c ?? "all"}
              onClick={() => setComponent(c)}
              className={`px-3 py-1 transition-colors ${
                component === c ? "bg-accent/20 text-accent" : "text-text-dim hover:text-text"
              }`}
            >
              {c ?? "All"}
            </button>
          ))}
        </div>
        <div className="flex gap-1 rounded border border-border bg-card text-xs">
          {[7, 30, 365].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 transition-colors ${
                days === d ? "bg-accent/20 text-accent" : "text-text-dim hover:text-text"
              }`}
            >
              {d === 365 ? "All" : `${d}d`}
            </button>
          ))}
        </div>
        <button onClick={refetch} className="ml-auto text-xs text-text-dim hover:text-accent">
          ↻ Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-text-dim">Loading...</p>
      ) : (
        <DataTable
          columns={columns}
          data={data || []}
          onRowClick={(row) => setExpanded(expanded === row.alert_id ? null : row.alert_id)}
          rowClassName={(row) =>
            expanded === row.alert_id ? "bg-card/60" : ""
          }
        />
      )}

      {/* Expanded detail panel */}
      {expanded && data && (() => {
        const row = data.find((a) => a.alert_id === expanded);
        if (!row) return null;
        return (
          <div className="mt-2 rounded border border-border bg-card p-4 text-xs">
            <div className="grid gap-2 sm:grid-cols-3">
              <div>
                <span className="text-text-dim">Alert ID: </span>
                <span className="font-mono">{row.alert_id}</span>
              </div>
              <div>
                <span className="text-text-dim">Wallet: </span>
                <span className="font-mono">{row.wallet_address?.slice(0, 14)}...</span>
              </div>
              <div>
                <span className="text-text-dim">Market: </span>
                <span>{row.market_title || row.condition_id}</span>
              </div>
              {row.features_passed && (
                <div className="sm:col-span-3">
                  <span className="text-text-dim">Features: </span>
                  <span className="font-mono text-accent">{row.features_passed}</span>
                </div>
              )}
              {row.shadow_pnl_simulated != null && (
                <div>
                  <span className="text-text-dim">Shadow P&L: </span>
                  <span className={`font-mono ${row.shadow_pnl_simulated >= 0 ? "text-positive" : "text-negative"}`}>
                    {row.shadow_pnl_simulated >= 0 ? "+" : ""}${Math.abs(row.shadow_pnl_simulated).toFixed(2)}
                  </span>
                </div>
              )}
              {row.price_at_alert != null && (
                <div>
                  <span className="text-text-dim">Price at alert: </span>
                  <span className="font-mono">{Number(row.price_at_alert).toFixed(2)}</span>
                  {row.price_at_resolution != null && (
                    <span className="font-mono text-text-dim"> → {Number(row.price_at_resolution).toFixed(2)}</span>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Visit http://localhost:5173/alerts — verify table renders, filters work, row expand works

- [ ] **Step 3: Commit**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git add dashboard/src/pages/Alerts.jsx
git commit -m "feat(M8-B): Alerts page — filterable table, row expand with C2 details"
```

---

### Task 8: Frontend — Wallets Page

**Files:**
- Modify: `dashboard/src/pages/Wallets.jsx`

- [ ] **Step 1: Implement Wallets page**

```jsx
// dashboard/src/pages/Wallets.jsx
import useFetch from "../hooks/useFetch";
import DataTable from "../components/DataTable";

export default function Wallets() {
  const { data, loading, refetch } = useFetch("/api/wallets");

  const columns = [
    {
      key: "address", label: "Address", sortable: false,
      render: (v) => <span className="font-mono">{v?.slice(0, 10)}...</span>,
    },
    { key: "notes", label: "Name", sortable: true, render: (v) => v || "—" },
    {
      key: "confidence", label: "Conf", sortable: true,
      render: (v) => v != null ? Number(v).toFixed(2) : "—",
    },
    { key: "trades_total", label: "Trades", sortable: true },
    { key: "trades_7d", label: "7d", sortable: true },
    {
      key: "win_rate", label: "Win %", sortable: true,
      render: (v) => {
        if (v == null) return <span className="text-text-dim">—</span>;
        const color = v > 55 ? "text-positive" : v < 45 ? "text-negative" : "text-warning";
        return <span className={`font-mono ${color}`}>{v.toFixed(1)}%</span>;
      },
    },
    {
      key: "pnl", label: "P&L", sortable: true,
      render: (v) => {
        if (!v) return <span className="text-text-dim">$0</span>;
        const color = v >= 0 ? "text-positive" : "text-negative";
        return <span className={`font-mono ${color}`}>{v >= 0 ? "+" : ""}${Math.abs(v).toFixed(2)}</span>;
      },
    },
    {
      key: "last_trade", label: "Last Trade", sortable: true,
      render: (v) => v?.slice(0, 10) || "—",
    },
  ];

  function rowClassName(row) {
    if (!row.active) return "opacity-50 line-through";
    if (row.trades_7d === 0) return "border-l-2 border-l-warning";
    return "";
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <h2 className="font-mono text-lg font-bold text-text">Wallets Tier A</h2>
        <button onClick={refetch} className="ml-auto text-xs text-text-dim hover:text-accent">
          ↻ Refresh
        </button>
      </div>
      {loading ? (
        <p className="text-text-dim">Loading...</p>
      ) : (
        <DataTable columns={columns} data={data || []} rowClassName={rowClassName} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Visit http://localhost:5173/wallets — verify table, sorting, inactive wallet styling

- [ ] **Step 3: Commit**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git add dashboard/src/pages/Wallets.jsx
git commit -m "feat(M8-B): Wallets page — sortable table, win rate, inactive highlighting"
```

---

### Task 9: Frontend — Performance Page

**Files:**
- Modify: `dashboard/src/pages/Performance.jsx`

- [ ] **Step 1: Implement Performance page**

```jsx
// dashboard/src/pages/Performance.jsx
import { useState } from "react";
import useFetch from "../hooks/useFetch";
import KpiCard from "../components/KpiCard";
import {
  LineChart, Line, BarChart, Bar, ResponsiveContainer,
  Tooltip, XAxis, YAxis, Legend, CartesianGrid,
} from "recharts";

export default function Performance() {
  const [days, setDays] = useState(30);
  const { data, loading, refetch } = useFetch(`/api/performance?days=${days}`);

  if (loading) return <p className="text-text-dim">Loading...</p>;
  if (!data) return null;

  const { daily, cumulative, alignment } = data;

  const totalAlerts = cumulative.reduce((s, c) => s + c.total, 0);
  const totalResolved = cumulative.reduce((s, c) => s + c.resolved, 0);
  const totalCorrect = cumulative.reduce((s, c) => s + c.correct, 0);
  const totalPnl = cumulative.reduce((s, c) => s + (c.pnl || 0), 0);
  const pending = totalAlerts - totalResolved;
  const correctPct = totalResolved > 0 ? (totalCorrect / totalResolved * 100).toFixed(1) : "—";
  const incorrectPct = totalResolved > 0 ? ((totalResolved - totalCorrect) / totalResolved * 100).toFixed(1) : "—";

  // Build cumulative P&L series per component
  const dayMap = {};
  daily.forEach((d) => {
    if (!dayMap[d.day]) dayMap[d.day] = { day: d.day, C1: 0, C2: 0 };
    if (d.component === "C1") dayMap[d.day].C1 = d.pnl || 0;
    if (d.component === "C2") dayMap[d.day].C2 = d.pnl || 0;
  });
  let cumC1 = 0, cumC2 = 0;
  const pnlSeries = Object.values(dayMap)
    .sort((a, b) => a.day.localeCompare(b.day))
    .map((d) => {
      cumC1 += d.C1;
      cumC2 += d.C2;
      return {
        day: d.day.slice(5),
        C1: parseFloat(cumC1.toFixed(2)),
        C2: parseFloat(cumC2.toFixed(2)),
        Total: parseFloat((cumC1 + cumC2).toFixed(2)),
      };
    });

  const alignMap = {};
  (alignment || []).forEach((a) => { alignMap[a.score] = a.count; });
  const alignData = [
    { label: "📉 Contrariant", value: alignMap[-1] || 0 },
    { label: "➡️ Neutre", value: alignMap[0] || 0 },
    { label: "📈 Suit", value: alignMap[1] || 0 },
  ];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h2 className="font-mono text-lg font-bold text-text">Performance</h2>
        <div className="flex gap-1 rounded border border-border bg-card text-xs">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 transition-colors ${days === d ? "bg-accent/20 text-accent" : "text-text-dim hover:text-text"}`}
            >
              {d}d
            </button>
          ))}
        </div>
        <button onClick={refetch} className="ml-auto text-xs text-text-dim hover:text-accent">↻ Refresh</button>
      </div>

      {totalResolved < 30 && (
        <div className="mb-4 rounded border border-warning/50 bg-warning/10 p-3 text-sm text-warning">
          Echantillon &lt; 30 alertes resolues — donnees insuffisantes pour conclure
        </div>
      )}

      {/* KPI Cards */}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <KpiCard label="Total alertes" value={totalAlerts} color="accent" />
        <KpiCard label="Resolues" value={totalResolved} color="accent" />
        <KpiCard label="Pending" value={pending} color="warning" />
        <KpiCard label="Correct %" value={correctPct === "—" ? "—" : `${correctPct}%`} color={parseFloat(correctPct) > 55 ? "positive" : "warning"} />
        <KpiCard label="Incorrect %" value={incorrectPct === "—" ? "—" : `${incorrectPct}%`} color="negative" />
      </div>

      {/* P&L Chart */}
      {pnlSeries.length > 0 && (
        <div className="mb-6 rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">Shadow P&L cumule ({days}j)</p>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={pnlSeries}>
              <CartesianGrid stroke="#1e1e2e" />
              <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#71717a" }} />
              <YAxis tick={{ fontSize: 10, fill: "#71717a" }} />
              <Tooltip contentStyle={{ backgroundColor: "#12121a", border: "1px solid #1e1e2e", fontSize: 12 }} />
              <Legend />
              <Line type="monotone" dataKey="Total" stroke="#e4e4e7" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="C1" stroke="#06b6d4" strokeWidth={1.5} dot={false} />
              <Line type="monotone" dataKey="C2" stroke="#f59e0b" strokeWidth={1.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Alignment Distribution */}
      {alignment && alignment.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">Alignment C2</p>
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={alignData}>
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#71717a" }} />
              <Tooltip contentStyle={{ backgroundColor: "#12121a", border: "1px solid #1e1e2e", fontSize: 12 }} />
              <Bar dataKey="value" fill="#06b6d4" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Visit http://localhost:5173/performance — verify chart, KPI cards, alignment bar chart

- [ ] **Step 3: Commit**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git add dashboard/src/pages/Performance.jsx
git commit -m "feat(M8-B): Performance page — P&L chart, component breakdown, alignment distribution"
```

---

### Task 10: Frontend — System Page

**Files:**
- Modify: `dashboard/src/pages/System.jsx`

- [ ] **Step 1: Implement System page**

```jsx
// dashboard/src/pages/System.jsx
import useFetch from "../hooks/useFetch";
import StatusDot from "../components/StatusDot";

export default function System() {
  const { data: status, loading, refetch } = useFetch("/api/status");
  const { data: audit } = useFetch("/api/audit?limit=50");

  if (loading) return <p className="text-text-dim">Loading...</p>;

  const icons = {
    kill_switch: "⚙️",
    rate_limit: "⚠️",
    circuit_breaker: "🔧",
    config_change: "💰",
  };

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <h2 className="font-mono text-lg font-bold text-text">System</h2>
        <button onClick={refetch} className="ml-auto text-xs text-text-dim hover:text-accent">↻ Refresh</button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Kill Switches */}
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">Kill Switches</p>
          {(status?.kill_switches || []).length === 0 ? (
            <p className="text-sm text-text-dim">Aucun kill switch actif</p>
          ) : (
            <div className="space-y-2">
              {status.kill_switches.map((ks) => (
                <div key={ks.target} className="flex items-center justify-between rounded border border-negative/30 bg-negative/5 px-3 py-2">
                  <span className="font-mono text-sm text-negative">{ks.target}</span>
                  <span className="text-xs text-text-dim">{ks.reason || "—"}</span>
                  <span className="text-xs text-text-dim">{ks.toggled_at?.slice(0, 19)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Rate Limits */}
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">Rate Limits</p>
          {(status?.rate_limits || []).length === 0 ? (
            <p className="text-sm text-text-dim">Aucun compteur actif</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-text-dim">
                  <th className="px-2 py-1">Component</th>
                  <th className="px-2 py-1">Window</th>
                  <th className="px-2 py-1">Count</th>
                  <th className="px-2 py-1">Since</th>
                </tr>
              </thead>
              <tbody>
                {status.rate_limits.map((rl, i) => (
                  <tr key={i} className="border-t border-border/50">
                    <td className="px-2 py-1 font-mono">{rl.component}</td>
                    <td className="px-2 py-1">{rl.window}</td>
                    <td className="px-2 py-1 font-mono">{rl.count}</td>
                    <td className="px-2 py-1 text-xs text-text-dim">{rl.window_start?.slice(11, 19) || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Indexers Detail */}
        <div className="rounded-lg border border-border bg-card p-4 lg:col-span-2">
          <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">Indexers</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(status?.indexers || []).map((ix) => (
              <div key={ix.name} className="rounded border border-border p-3">
                <div className="flex items-center gap-2 mb-2">
                  <StatusDot status={ix.status} />
                  <span className="font-mono text-sm">{ix.name}</span>
                </div>
                <div className="text-xs text-text-dim space-y-0.5">
                  <p>Last sync: {ix.last_synced_at?.slice(0, 19) || "—"}</p>
                  <p>Duration: {ix.duration_ms ? `${ix.duration_ms}ms` : "—"}</p>
                  <p>Ingested: {ix.ingested_count?.toLocaleString() || "—"}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Audit Log */}
      <div className="mt-4 rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">Audit Log</p>
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-card">
              <tr className="text-left uppercase text-text-dim">
                <th className="px-2 py-1">Time</th>
                <th className="px-2 py-1">Type</th>
                <th className="px-2 py-1">Target</th>
                <th className="px-2 py-1">Action</th>
                <th className="px-2 py-1 hidden sm:table-cell">Reason</th>
                <th className="px-2 py-1 hidden sm:table-cell">Actor</th>
              </tr>
            </thead>
            <tbody>
              {(audit || []).map((ev) => (
                <tr key={ev.id} className="border-t border-border/50">
                  <td className="px-2 py-1 text-text-dim">{ev.created_at?.slice(11, 19) || "—"}</td>
                  <td className="px-2 py-1">{icons[ev.event_type] || "📋"} {ev.event_type}</td>
                  <td className="px-2 py-1 font-mono">{ev.target}</td>
                  <td className="px-2 py-1">{ev.action}</td>
                  <td className="px-2 py-1 text-text-dim hidden sm:table-cell">{ev.reason || "—"}</td>
                  <td className="px-2 py-1 text-text-dim hidden sm:table-cell">{ev.actor}</td>
                </tr>
              ))}
              {(!audit || audit.length === 0) && (
                <tr><td colSpan={6} className="px-2 py-4 text-center text-text-dim">Audit log vide</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Visit http://localhost:5173/system — verify kill switches, rate limits, indexers, audit log

- [ ] **Step 3: Commit**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git add dashboard/src/pages/System.jsx
git commit -m "feat(M8-B): System page — kill switches, rate limits, indexers, audit log"
```

---

### Task 11: Build + Deploy to VPS

**Files:**
- No new files — deploy existing code

- [ ] **Step 1: Build frontend**

Run:
```bash
cd /Users/gabsav/Documents/Polycasquette/Code/dashboard && npm run build
```
Expected: `dist/` directory with `index.html`, `assets/` folder

- [ ] **Step 2: Run all backend tests**

Run:
```bash
cd /Users/gabsav/Documents/Polycasquette/Code && python -m pytest tests/unit/test_dashboard_api.py -v
```
Expected: 6 tests PASS

- [ ] **Step 3: Run lint on all new files**

Run:
```bash
cd /Users/gabsav/Documents/Polycasquette/Code && ruff check src/polybot/dashboard/
```
Expected: No errors

- [ ] **Step 4: Push to GitHub**

Run:
```bash
cd /Users/gabsav/Documents/Polycasquette/Code && git push origin main
```

- [ ] **Step 5: Rsync to VPS**

Run:
```bash
rsync -avz --exclude node_modules --exclude .git --exclude .venv --exclude '*.pyc' --exclude __pycache__ /Users/gabsav/Documents/Polycasquette/Code/ polybot:/root/polybot/
```

- [ ] **Step 6: Install Python deps on VPS**

Run:
```bash
ssh polybot "cd /root/polybot && uv sync"
```

- [ ] **Step 7: Install and configure Caddy**

Run:
```bash
ssh polybot "apt install -y caddy"
ssh polybot "cp /root/polybot/deploy/Caddyfile /etc/caddy/Caddyfile"
```

- [ ] **Step 8: Generate bcrypt hash and configure basic auth**

Run (locally):
```bash
caddy hash-password --plaintext '<chosen_password>'
```
Then on VPS:
```bash
ssh polybot "echo 'DASHBOARD_BCRYPT_HASH=<hash_from_above>' >> /root/polybot/.env"
```

**Note:** If `caddy` is not available locally, use the VPS:
```bash
ssh polybot "caddy hash-password --plaintext '<chosen_password>'"
```

- [ ] **Step 9: Deploy dashboard systemd service**

Run:
```bash
ssh polybot "cp /root/polybot/deploy/polybot-dashboard.service /etc/systemd/system/"
ssh polybot "systemctl daemon-reload"
ssh polybot "systemctl enable --now polybot-dashboard"
ssh polybot "systemctl restart caddy"
```

- [ ] **Step 10: Open firewall port**

Run:
```bash
ssh polybot "ufw allow 3000/tcp"
```

- [ ] **Step 11: Verify deployment**

Run:
```bash
# Check API responds
ssh polybot "curl -s http://127.0.0.1:8000/api/status | head -c 200"

# Check Caddy serves dashboard (with basic auth)
ssh polybot "curl -s -u polybot:<password> http://127.0.0.1:3000/ | head -c 200"

# Check services are running
ssh polybot "systemctl status polybot-dashboard --no-pager"
ssh polybot "systemctl status caddy --no-pager"
```

- [ ] **Step 12: Test from external browser**

Visit `http://<vps_ip>:3000` — should prompt for basic auth, then show the dashboard.

Verify all 5 pages load with real data:
- Overview: KPIs, sparklines, indexers
- Alerts: table with filters
- Wallets: sortable table
- Performance: P&L chart
- System: audit log, rate limits
