"""Polybot Dashboard API — read-only access to DuckDB monitoring data."""

import time
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

MAX_RETRIES = 5
BASE_DELAY = 1.0


def _connect_with_retry() -> duckdb.DuckDBPyConnection:
    for attempt in range(MAX_RETRIES):
        try:
            return duckdb.connect(str(settings.DUCKDB_PATH))
        except duckdb.IOException:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = BASE_DELAY * 2**attempt
            logger.warning("dashboard_db_retry", attempt=attempt + 1, delay=delay)
            time.sleep(delay)
    raise duckdb.IOException("Failed to connect after retries")


def get_db():
    con = _connect_with_retry()
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
            {
                "target": r[0],
                "enabled": r[1],
                "reason": r[2],
                "toggled_at": str(r[3]) if r[3] else None,
            }
            for r in kill_switches
        ],
        "rate_limits": [
            {
                "component": r[0],
                "window": r[1],
                "count": r[2],
                "window_start": str(r[3]) if r[3] else None,
            }
            for r in rate_limits
        ],
        "indexers": [
            {
                "name": r[0],
                "status": r[1],
                "last_synced_at": str(r[2]) if r[2] else None,
                "duration_ms": r[3],
                "ingested_count": r[4],
            }
            for r in indexers
        ],
    }


@app.get("/api/alerts")
def get_alerts(
    con: DB,
    days: int = Query(default=7, ge=1, le=365),
    component: str | None = None,
):
    interval = f"{days} DAY"
    base_sql = (
        "SELECT "
        "a.alert_id, a.component, a.emitted_at, a.wallet_address, a.condition_id, "
        "a.side, a.size_usd, a.price, a.score, a.alignment_score, "
        "a.shadow_mode, a.features_passed, "
        "m.title, m.slug, "
        "ao.resolution_outcome, ao.was_direction_correct, ao.shadow_pnl_simulated, "
        "ao.price_at_alert, ao.price_at_resolution "
        "FROM alerts a "
        "LEFT JOIN markets m ON a.condition_id = m.condition_id "
        "LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id "
        f"WHERE a.emitted_at >= CURRENT_DATE - INTERVAL '{interval}'"
    )
    params: list = []
    if component:
        base_sql += " AND a.component = ?"
        params.append(component)
    base_sql += " ORDER BY a.emitted_at DESC LIMIT 200"
    rows = con.execute(base_sql, params).fetchall()
    return [
        {
            "alert_id": r[0],
            "component": r[1],
            "emitted_at": str(r[2]) if r[2] else None,
            "wallet_address": r[3],
            "condition_id": r[4],
            "side": r[5],
            "size_usd": float(r[6]) if r[6] else None,
            "price": float(r[7]) if r[7] else None,
            "score": r[8],
            "alignment_score": r[9],
            "shadow_mode": r[10],
            "features_passed": r[11],
            "market_title": r[12],
            "market_slug": r[13],
            "resolution_outcome": r[14],
            "was_direction_correct": r[15],
            "shadow_pnl_simulated": float(r[16]) if r[16] else None,
            "price_at_alert": float(r[17]) if r[17] else None,
            "price_at_resolution": float(r[18]) if r[18] else None,
        }
        for r in rows
    ]


@app.get("/api/wallets")
def get_wallets(con: DB):
    wallets = con.execute(
        "SELECT w.address, w.tier, w.active, w.source, w.added_at, "
        "w.honeypot_flag, w.tier_a_confidence, "
        "COUNT(t.transaction_hash) AS trades_total, "
        "SUM(CASE WHEN t.timestamp_ts >= CURRENT_DATE - INTERVAL '7 DAY' "
        "    THEN 1 ELSE 0 END) AS trades_7d, "
        "MAX(t.timestamp_ts) AS last_trade, "
        "COALESCE(SUM(t.size_usd), 0) AS total_volume "
        "FROM tracked_wallets w "
        "LEFT JOIN trades t ON w.address = t.proxy_wallet "
        "WHERE w.tier = 'A' "
        "GROUP BY w.address, w.tier, w.active, w.source, w.added_at, "
        "w.honeypot_flag, w.tier_a_confidence "
        "ORDER BY trades_total DESC"
    ).fetchall()

    addresses = [r[0] for r in wallets]
    perf: dict = {}
    if addresses:
        placeholders = ", ".join(["?"] * len(addresses))
        perf_rows = con.execute(
            "SELECT a.wallet_address, "
            "COUNT(*) AS resolved, "
            "SUM(CASE WHEN ao.was_direction_correct THEN 1 ELSE 0 END) AS correct, "
            "SUM(ao.shadow_pnl_simulated) AS pnl "
            "FROM alerts a "
            "JOIN alert_outcomes ao ON a.alert_id = ao.alert_id "
            f"WHERE a.wallet_address IN ({placeholders}) "
            "GROUP BY a.wallet_address",
            addresses,
        ).fetchall()
        for pr in perf_rows:
            perf[pr[0]] = {
                "resolved": pr[1],
                "correct": pr[2],
                "pnl": float(pr[3]) if pr[3] else None,
            }

    result = []
    for r in wallets:
        addr = r[0]
        p = perf.get(addr, {"resolved": 0, "correct": 0, "pnl": None})
        resolved = p["resolved"]
        correct = p["correct"]
        win_rate = (correct / resolved * 100) if resolved > 0 else None
        result.append({
            "address": addr,
            "tier": r[1],
            "active": r[2],
            "source": r[3],
            "added_at": str(r[4]) if r[4] else None,
            "honeypot_flag": r[5],
            "tier_a_confidence": float(r[6]) if r[6] else None,
            "trades_total": r[7],
            "trades_7d": r[8],
            "last_trade": str(r[9]) if r[9] else None,
            "total_volume": float(r[10]) if r[10] else None,
            "resolved": resolved,
            "correct": correct,
            "pnl": p["pnl"],
            "win_rate": float(win_rate) if win_rate is not None else None,
        })
    return result


@app.get("/api/performance")
def get_performance(con: DB, days: int = Query(default=30, ge=1, le=365)):
    interval = f"{days} DAY"
    daily = con.execute(
        "SELECT date_trunc('day', a.emitted_at)::DATE AS day, a.component, "
        "COUNT(*) AS alerts, "
        "SUM(CASE WHEN ao.was_direction_correct THEN 1 ELSE 0 END) AS correct, "
        "SUM(ao.shadow_pnl_simulated) AS pnl "
        "FROM alerts a "
        "LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id "
        f"WHERE a.emitted_at >= CURRENT_DATE - INTERVAL '{interval}' "
        "GROUP BY day, a.component ORDER BY day"
    ).fetchall()

    cumulative = con.execute(
        "SELECT a.component, COUNT(*) AS alerts, "
        "SUM(CASE WHEN ao.was_direction_correct THEN 1 ELSE 0 END) AS correct, "
        "SUM(ao.shadow_pnl_simulated) AS pnl "
        "FROM alerts a "
        "LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id "
        "GROUP BY a.component"
    ).fetchall()

    alignment = con.execute(
        "SELECT alignment_score, COUNT(*) AS count "
        "FROM alerts "
        "WHERE alignment_score IS NOT NULL "
        "GROUP BY alignment_score ORDER BY alignment_score"
    ).fetchall()

    return {
        "daily": [
            {
                "day": str(r[0]),
                "component": r[1],
                "alerts": r[2],
                "correct": r[3],
                "pnl": float(r[4]) if r[4] else None,
            }
            for r in daily
        ],
        "cumulative": [
            {
                "component": r[0],
                "alerts": r[1],
                "correct": r[2],
                "pnl": float(r[3]) if r[3] else None,
            }
            for r in cumulative
        ],
        "alignment": [
            {"alignment_score": r[0], "count": r[1]} for r in alignment
        ],
    }


@app.get("/api/markets/hot")
def get_hot_markets(con: DB):
    rows = con.execute(
        "SELECT m.condition_id, m.title, m.slug, m.volume_24h, m.liquidity_usd, "
        "m.end_date, m.category, "
        "COUNT(a.alert_id) AS alert_count "
        "FROM markets m "
        "LEFT JOIN alerts a ON m.condition_id = a.condition_id "
        "AND a.emitted_at >= CURRENT_DATE - INTERVAL '7 DAY' "
        "WHERE m.active = TRUE AND m.volume_24h > 10000 "
        "GROUP BY m.condition_id, m.title, m.slug, m.volume_24h, "
        "m.liquidity_usd, m.end_date, m.category "
        "ORDER BY m.volume_24h DESC LIMIT 50"
    ).fetchall()
    return [
        {
            "condition_id": r[0],
            "title": r[1],
            "slug": r[2],
            "volume_24h": float(r[3]) if r[3] else None,
            "liquidity_usd": float(r[4]) if r[4] else None,
            "end_date": str(r[5]) if r[5] else None,
            "category": r[6],
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
            "id": r[0],
            "event_type": r[1],
            "target": r[2],
            "action": r[3],
            "reason": r[4],
            "actor": r[5],
            "created_at": str(r[6]) if r[6] else None,
        }
        for r in rows
    ]


@app.get("/api/costs")
def get_costs(con: DB):
    row = con.execute(
        "SELECT COUNT(*) FROM resolution_risk_cache "
        "WHERE computed_at >= date_trunc('month', CURRENT_DATE)"
    ).fetchone()
    llm_calls = row[0] if row else 0
    return {
        "llm_calls_month": llm_calls,
        "llm_cost_estimate": round(llm_calls * 0.001, 4),
        "vps_monthly": 4.0,
    }


@app.get("/api/c2/features")
def get_c2_features(con: DB, condition_id: str = Query(...)):
    rows = con.execute(
        "SELECT a.alert_id, a.emitted_at, a.wallet_address, a.side, "
        "a.size_usd, a.price, a.score, a.alignment_score, "
        "a.shadow_mode, a.features_passed, "
        "ao.resolution_outcome, ao.was_direction_correct, "
        "ao.shadow_pnl_simulated, ao.price_at_alert, ao.price_at_resolution "
        "FROM alerts a "
        "LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id "
        "WHERE a.condition_id = ? AND a.component = 'C2' "
        "ORDER BY a.emitted_at DESC",
        [condition_id],
    ).fetchall()
    return [
        {
            "alert_id": r[0],
            "emitted_at": str(r[1]) if r[1] else None,
            "wallet_address": r[2],
            "side": r[3],
            "size_usd": float(r[4]) if r[4] else None,
            "price": float(r[5]) if r[5] else None,
            "score": r[6],
            "alignment_score": r[7],
            "shadow_mode": r[8],
            "features_passed": r[9],
            "resolution_outcome": r[10],
            "was_direction_correct": r[11],
            "shadow_pnl_simulated": float(r[12]) if r[12] else None,
            "price_at_alert": float(r[13]) if r[13] else None,
            "price_at_resolution": float(r[14]) if r[14] else None,
        }
        for r in rows
    ]
