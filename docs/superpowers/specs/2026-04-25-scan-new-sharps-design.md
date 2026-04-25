# Scan New Sharps — Design Spec

**Date:** 2026-04-25
**Script:** `scripts/scan_new_sharps.py`
**Standalone:** `uv run python scripts/scan_new_sharps.py`

## Goal

Scan `trades_all` for wallets with strong volume/diversification signals that aren't already tracked. Produce a ranked shortlist for manual investigation or Data API follow-up.

## Approach — Option C (Volume/Activity Only)

No win rate calculation — `trades_all` lacks YES/NO token info. Score purely on volume, diversification, and activity patterns. Top candidates get investigated via Data API separately.

## Pipeline

### Step 1 — Extract active wallets

```sql
SELECT
    proxy_wallet,
    COUNT(*) as n_trades,
    COUNT(DISTINCT condition_id) as n_markets,
    SUM(size_usd) as total_volume,
    AVG(size_usd) as avg_trade_size,
    MIN(timestamp_ts) as first_trade,
    MAX(timestamp_ts) as last_trade,
    COUNT(DISTINCT DATE(timestamp_ts)) as active_days
FROM trades_all
WHERE proxy_wallet NOT IN (SELECT address FROM tracked_wallets)
  AND proxy_wallet NOT IN (
      '0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E',
      '0xC5d563A36AE78145C45a50134d48A1215220f80a'
  )
GROUP BY proxy_wallet
HAVING n_trades >= 20
   AND n_markets >= 5
   AND total_volume >= 1000
```

### Step 2 — Compute HHI per wallet

For each candidate, compute Herfindahl-Hirschman Index on volume by `condition_id`:

```
HHI = Σ (vol_market_i / total_vol)²
```

Lower HHI = more diversified. Threshold: HHI < 0.25 earns a point.

### Step 3 — Score (max 9 points)

| Metric | Threshold | Points |
|--------|-----------|--------|
| Volume | ≥$50K | +3 |
| Volume | ≥$10K | +2 |
| Volume | ≥$3K | +1 |
| Markets | ≥20 distinct | +2 |
| Markets | ≥10 distinct | +1 |
| Active days | ≥3 distinct days | +1 |
| Avg trade size | ≥$100 | +1 |
| HHI | < 0.25 | +1 |

### Step 4 — Output

- Console: top 20 wallets by score, formatted table
- Distribution log: volume/trades/markets percentiles for threshold tuning
- JSON: `reports/new_sharps_YYYYMMDD.json` with all candidates

### Step 5 — Small dataset handling

If < 5 candidates pass filters, log:
> "Dataset trades_all trop petit pour un scan significatif. Relancer dans 1-2 semaines."

## Exclusions

- Exchange contracts (CTF + NegRisk addresses)
- Already-tracked wallets (from `tracked_wallets` table)
- Wallets with < 20 trades, < 5 markets, or < $1K volume

## Patterns

- DB: `duckdb.connect("data/pm.duckdb", read_only=True)`
- No new dependencies
- Read-only — no writes to tracked_wallets
- `reports/` mkdir with exist_ok
