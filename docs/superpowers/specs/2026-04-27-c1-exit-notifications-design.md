# C1 SELL Exit Notifications — Design

**Date:** 2026-04-27
**Status:** Approved, awaiting implementation plan
**Scope:** Single-feature spec (C1 component only)

## Problem

C1 currently emits alerts on Tier A BUY trades. If the wallet later SELLs the position
before the market resolves, copy-traders who entered on the BUY have no signal that the
sharp wallet has exited — they remain exposed to a position the source no longer holds.

## Goal

Notify Telegram (`#ops` in shadow mode, `#alerts` after promotion) when a Tier A wallet
SELLs a position for which a C1 alert is currently pending (not yet resolved). One
notification per `(wallet, condition_id, outcome)` per daemon process.

## Non-goals

- EXIT detection for C2 alerts.
- Persistent dedup (in-memory set is acceptable; resets on daemon restart).
- Schema migration. EXIT events use `audit_log` only.
- Modification of the existing BUY alert pipeline, dedup hash, or rate-limit logic.

## Design decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Match SELL to BUY by outcome? | **Yes** — `(wallet, condition_id, outcome)` | Wallet may hedge with both YES and NO simultaneously. Without outcome match a SELL NO would falsely signal exit of an open YES position. |
| Min SELL size for EXIT? | **New setting** `C1_EXIT_SIZE_MIN_USD = 500.0` | Prevents dust SELL ($5–50) from firing dedup ahead of the real exit. Lower than `C1_SIZE_MIN_USD` ($1000) because partial exits are still signal. |
| EXIT persistence? | **`audit_log`** with JSON in `reason` | Mirrors existing pattern (no migration), keeps EXITs queryable for later analysis (avg P&L, exit frequency). |
| Daemon-restart dedup loss? | **Accepted** | Notifications are informative, not critical. |
| Re-entry after exit? | **Silently ignored** | Same `(wallet, market, outcome)` key blocks until restart. Acceptable per spec. |

## Architecture

Single new code path inside `SharpMoneyDetector.poll_once`, parallel to the existing
BUY pipeline. The `_fetch_new_trades` query already returns SELL rows; only the
first line of `_process_trade` discards them today.

```
poll_once(trade):
    if trade.side == "BUY":
        await _process_trade(trade)        # unchanged
    elif trade.side == "SELL":
        await _process_exit(trade)         # new
```

## Data flow — `_process_exit`

1. **Size floor.** If `trade.size_usd < settings.C1_EXIT_SIZE_MIN_USD` → return.
2. **In-memory dedup.** `key = (proxy_wallet, condition_id, outcome)`. If in
   `self._exit_notified` → return. Set initialized in `__init__`, no eviction.
3. **Find pending alert.** Single read-only SQL:
   ```sql
   SELECT a.alert_id, t_buy.outcome, a.price AS entry_price,
          a.size_suggested_usd, a.emitted_at
   FROM alerts a
   JOIN trades t_buy ON a.trade_hash = t_buy.transaction_hash
   LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
   WHERE a.component = 'C1'
     AND a.wallet_address = ?
     AND a.condition_id = ?
     AND t_buy.outcome = ?
     AND (ao.resolution_outcome IS NULL OR ao.resolution_outcome = 'PENDING')
   ORDER BY a.emitted_at DESC
   LIMIT 1
   ```
   No row → return (no pending position to exit).
4. **Compute.**
   - `pnl_pct = (exit_price - entry_price) / entry_price * 100`
   - `time_held = now - emitted_at` (humanized: `Xh` if < 24h else `Xj`)
5. **Generate EXIT id.** `_next_exit_id(con)`:
   ```sql
   SELECT target
   FROM audit_log
   WHERE event_type = 'position_exit' AND target LIKE 'EXIT_YYYYMMDD_%'
   ORDER BY target DESC LIMIT 1
   ```
   Increment last 4 digits; fallback `0001`. Mirrors existing `_next_alert_id`.
6. **Persist to `audit_log`.** One row:
   - `event_type='position_exit'`
   - `target=EXIT_YYYYMMDD_NNNN`
   - `action=proxy_wallet`
   - `reason=<JSON>` containing
     `{"alert_id","condition_id","outcome","entry_price","exit_price","exit_size_usd","pnl_pct","time_held_h"}`
7. **Send Telegram.** `_format_exit_message(...)` (see below); topic =
   `"ops" if SHADOW_MODE else "alerts"`. Two URL buttons (market, wallet); no
   Copié/Skip buttons (this is informational, not actionable copy-trade).
8. **Mark dedup** — `self._exit_notified.add(key)` only **after** successful Telegram
   send, so a transient Telegram error gets retried on the next poll.

## Telegram message format

```
⚠️ Position Exit  ·  EXIT_20260427_0001

<market_title>
👤 <wallet_name>  ·  Tier A<sub>

💰 Entrée : BUY <YES|NO> @ 0.65  (il y a 3j)
📤 Sortie : SELL @ 0.72  (+10.8%)
💵 Size exit : $3,200

💡 Si vous avez copié, envisagez de sortir aussi.
```

Two inline buttons: 📊 Marché, 👤 Wallet (URLs identical to C1 BUY format).

## Files touched

| File | Change | Approx LOC |
|------|--------|-----------|
| `src/polybot/components/c1_sharp_money.py` | `__init__` adds `_exit_notified=set()`; `poll_once` dispatches BUY/SELL; new `_process_exit`, `_format_exit_message`, `_next_exit_id`, `_humanize_time_held` | +120 |
| `src/polybot/config.py` | Add `C1_EXIT_SIZE_MIN_USD: float = 500.0` | +1 |
| `tests/unit/test_c1_sharp_money.py` | 8 new tests (see Test plan) | +250 |

No new modules, no migration, no changes outside C1.

## Error handling

| Failure | Behavior |
|---------|----------|
| Pending-alert SQL error | Log `c1_exit_query_error`, return; do not block other trades. |
| `audit_log` INSERT error | Log `c1_exit_audit_failed`; still send Telegram. The user-facing notification is more important than the trace row. |
| Telegram send error | Exception bubbles to `poll_once` outer try/except (`c1_trade_processing_error`). Dedup **not** marked → retried next poll. |
| `_next_exit_id` collision (concurrent emit) | Single-process daemon → impossible. If ever multi-process, `audit_log.id` PK guarantees insert succeeds; only the `target` field could collide (no UNIQUE constraint), accepted. |

## Test plan

| # | Test | Asserts |
|---|------|---------|
| 1 | EXIT fired on SELL with pending C1 alert (matching outcome) | one Telegram message, audit_log row, dedup marked |
| 2 | No EXIT when alert is resolved (`alert_outcomes.resolution_outcome != 'PENDING'`) | zero Telegram messages |
| 3 | No EXIT when no alert exists for `(wallet, market)` | zero Telegram messages |
| 4 | No EXIT when SELL outcome ≠ BUY outcome (hedge case) | zero Telegram messages |
| 5 | Dedup: two consecutive SELLs same `(wallet, market, outcome)` | one Telegram message |
| 6 | Below size floor: SELL `< C1_EXIT_SIZE_MIN_USD` | zero Telegram messages, dedup **not** marked |
| 7 | P&L computation: BUY @ 0.65, SELL @ 0.72 → `pnl_pct ≈ +10.77` | numeric assertion (±0.05) |
| 8 | Message format contains entry, exit, %, time held, EXIT id | substring assertions |

## Acceptance criteria

1. All 8 new tests pass; existing unit-test suite remains green.
2. Manual smoke on VPS: insert a synthetic pending C1 alert + a synthetic SELL trade
   matching outcome → EXIT lands in #ops; second SELL → silent.
3. `audit_log` contains the row with parseable JSON reason.

## Deployment

Same workflow as scheduler-drift fix: rsync changed files, restart `polybot-bot.service`.

## Open follow-ups (not in this spec)

- EXIT for C2 alerts (separate spec, after C1 EXIT validates the pattern in production).
- Persistent dedup table if/when daemon restarts become more frequent.
- Optional `/exits` Telegram command to query recent EXITs from `audit_log`.
