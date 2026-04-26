# M9-3 — shared_cex_deposit Feature in C2 + Deploy M9

## Objective

Add 8th feature `shared_cex_deposit` to the C2 informed trading detector. Wallets sharing the same CEX deposit address are likely the same entity — a high ratio signals coordinated activity. Deploy all M9 changes (migration 008, seed script, cex_funding indexer, C2 feature) to VPS.

## Architecture

Single-file modification to `src/polybot/components/c2_informed_trading.py`. New method `compute_shared_cex_deposit(condition_id)` queries `cex_funding_map` to compute the ratio of active wallets sharing the most common deposit address. Integrated into `compute_score()` as the 8th boolean feature. No new tables, no new dependencies.

## New Method

### `compute_shared_cex_deposit(self, condition_id: str) -> tuple[float, str | None]`

**Returns:** `(ratio, cex_source)` where ratio is 0.0–1.0 and cex_source is the exchange name or None.

**SQL logic:**

```sql
-- Step 1: Get active wallets for this condition_id
WITH active_wallets AS (
    SELECT DISTINCT proxy_wallet
    FROM trades_all
    WHERE condition_id = ?
      AND proxy_wallet IS NOT NULL
),
-- Step 2: Join with cex_funding_map where deposit_address is not null
funded AS (
    SELECT aw.proxy_wallet, cfm.deposit_address, cfm.cex_source
    FROM active_wallets aw
    JOIN cex_funding_map cfm ON aw.proxy_wallet = cfm.wallet_address
    WHERE cfm.deposit_address IS NOT NULL
)
-- Step 3: Find most common deposit_address, count how many wallets share it
SELECT deposit_address, cex_source, COUNT(*) as cnt
FROM funded
GROUP BY deposit_address, cex_source
ORDER BY cnt DESC
LIMIT 1
```

Then: `ratio = cnt / total_active_wallets`. If no funded wallets or total_active_wallets is 0, return `(0.0, None)`.

**Uses:** `db_connect(self.db_path, read_only=True)` — same pattern as other compute methods in the class (direct connection, not `db_read_with_retry`, matching existing code style).

## Changes to `compute_score()`

**File:** `src/polybot/components/c2_informed_trading.py:272`

Add after line 280 (`dominance = self.compute_single_dominance(condition_id)`):

```python
cex_deposit_ratio, cex_source = self.compute_shared_cex_deposit(condition_id)
```

Add to `features` dict:

```python
"shared_cex_deposit": cex_deposit_ratio > 0.30,
```

Add to `raw_values` dict:

```python
"shared_cex_deposit": round(cex_deposit_ratio, 4),
"shared_cex_deposit_source": cex_source,
```

Score is already computed as `sum(features.values())` — automatically becomes /8.

## Changes to `_format_alert()`

**File:** `src/polybot/components/c2_informed_trading.py:498`

Add feature line case in the for-loop:

```python
elif f == "shared_cex_deposit":
    src = raw.get("shared_cex_deposit_source", "")
    src_str = f" ({src})" if src else ""
    feature_lines.append(
        f"  ✓ CEX deposit partage : {raw['shared_cex_deposit']:.0%}{src_str}"
    )
```

**Score label:** Change line 557 from `/7` to `/8`:

```python
f"🧬 Score : <b>{result['score']}/8</b>"
```

## Threshold

Alert threshold stays at `score >= 4` (line 595). Adding a feature makes it slightly harder to reach 4/8 = 50% vs 4/7 = 57%, which is acceptable — the feature is additive signal, not a gate.

## Fallback Behavior

- If `cex_funding_map` is empty (indexer hasn't run yet): ratio = 0.0, feature = False. No impact on existing alerts.
- If no wallets have `deposit_address` (all direct hot wallet or no CEX match): ratio = 0.0, feature = False.
- Feature only fires when multiple wallets genuinely share the same deposit address with ratio > 30%.

## Tests

**File:** `tests/unit/test_c2_informed_trading.py`

### Test 1: `test_shared_cex_deposit_above_threshold`

Seed 3 wallets trading on same condition_id, 2 sharing same deposit_address in cex_funding_map. Ratio = 2/3 = 0.67 > 0.30 → feature True.

### Test 2: `test_shared_cex_deposit_below_threshold`

Seed 5 wallets, only 1 with deposit_address. Ratio = 1/5 = 0.20 < 0.30 → feature False.

### Test 3: `test_shared_cex_deposit_no_funding_data`

No rows in cex_funding_map → ratio = 0.0, cex_source = None.

### Test 4: `test_shared_cex_deposit_in_score`

Call `compute_score()` with shared_cex_deposit triggering → verify `"shared_cex_deposit"` in `features_passed`, score incremented.

### Test 5: `test_alert_format_score_over_8`

Verify alert message contains `/8` not `/7`.

### Test 6: `test_alert_format_shared_cex_line`

Verify `shared_cex_deposit` in features_passed produces `✓ CEX deposit partage` line with source.

## Deploy (Manual)

SSH commands for VPS deployment — not coded, executed manually by user:

1. `ssh polybot` + `cd ~/polybot`
2. `git pull origin main`
3. `source .venv/bin/activate`
4. `uv sync`
5. `python scripts/init_db.py` (applies migration 008)
6. `python scripts/seed_cex_hot_wallets.py` (loads 23 hot wallets)
7. `sudo systemctl restart polybot`
8. Verify: `journalctl -u polybot -f` — check cex_funding indexer starts after 20min delay, C2 scans show `/8`

## Explicitly Out of Scope

- Changing the alert threshold from 4
- More than 2 hops in funding trace
- Automated deployment scripts
- Dashboard changes for M9
- Cluster detection beyond shared deposit address
