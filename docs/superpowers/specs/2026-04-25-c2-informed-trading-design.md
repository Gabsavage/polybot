# C2 Informed Trading — Design Spec

**Date:** 2026-04-25
**Ref:** `docs/specs/c2_informed_trading_spec.md`
**Scope:** Core module + migration 006 + daemon integration + unit tests.
NOT in scope: alignment v0, Telegram format, alert_outcomes job, promotion shadow mode.

## Migration 006

### New table: `alert_outcomes`
Tracks post-resolution outcomes for calibration. Schema per spec.

### ALTER alerts
4 new columns: `score`, `features_passed`, `alignment_score` (already exists from 005), `momentum_4h`.
DuckDB doesn't support `ADD COLUMN IF NOT EXISTS` — check `information_schema.columns` before each ALTER.
`alignment_score` already exists in 005 schema, so skip that one.

## C2 Module — `src/polybot/components/c2_informed_trading.py`

### Hot Market Detection (3 conditions, OR)

Data reality: `markets` lacks `avg_volume_1h_7d` and `price_change_1h`. Approved fallbacks:

| Condition | Implementation |
|-----------|---------------|
| Vol spike (>3x) | vol_1h from `trades_all` last hour. Baseline = `markets.volume_24h / 24`. Ratio > 3 = spike. |
| Price move (>10% + $500 vol) | VWAP last 10min vs VWAP ~1h ago from `trades_all`. Min 2 trades per window. |
| Near resolution | Direct from `markets.end_date` + `markets.volume_24h`. Works as-is. |

No materialized view (DuckDB doesn't support them). Direct query in `get_hot_markets()`.

### 7 Features

All computed from `trades_all` (last 1h window) + `markets` metadata:

1. **fresh_wallets_ratio** — % vol from wallets first seen <7d ago in trades_all
2. **top5_concentration** — HHI of top 5 traders in 1h window
3. **time_to_event** — hours until `markets.end_date`
4. **niche_market_flag** — `markets.volume_cumulative_usd < $50K`
5. **momentum_1h** — VWAP change over 1h from trades_all
6. **volume_zscore** — vol_1h vs `volume_24h/24` baseline, ratio as proxy z-score
7. **single_dominance** — max single wallet share of 1h volume

### Scoring
Binary sum of 7 features. Alert if score >= 4.

### Dedup & Rate Limiting
- 1 alert per market per 6h sliding window
- Max 2 alerts/hour, 5 alerts/day

### Patterns
- Follows C1 class structure: `__init__`, `scan_once()`, `run_forever()`
- DB access via `polybot.db.connection.db_connect()`
- Alert IDs: `AL_YYYYMMDD_XXXX` (shared sequence with C1)
- Settings: C2-prefixed in `config.py`
- Scan interval: 300s (5 min)

## Daemon Integration
Add `c2.run_forever()` to `asyncio.gather()` alongside C1 and daily report.

## Tests (12 unit tests)
Test each hot market condition, key features, score thresholds, dedup, rate limiting, and empty data resilience.
