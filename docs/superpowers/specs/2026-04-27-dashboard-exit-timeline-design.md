# Dashboard EXIT Timeline — Design

**Date:** 2026-04-27
**Status:** Approved, awaiting implementation plan
**Scope:** Single-feature spec (dashboard read path only — no daemon changes, no migration)

## Problem

The C1 EXIT alerts feature (shipped earlier today) writes a row to `audit_log` and sends a Telegram notification when a Tier A wallet SELLs a position with a pending C1 alert. The web dashboard does not yet surface these EXITs — they are invisible to anyone who isn't watching the Telegram topic in real time.

## Goal

Render EXIT events alongside BUY alerts in the dashboard, time-sorted, filterable, and (on the wallet detail page) visually grouped with their originating BUY so the position lifecycle is legible at a glance.

## Non-goals

- No changes to the C1 backend (`daemon`, `c1_sharp_money.py`, `audit_log` insert path).
- No DB migration. The dashboard reads `audit_log` as-is.
- No EXIT row enrichment on the existing `/api/alerts` endpoint (would change its contract). New endpoint instead.
- No automated frontend tests (the repo has no Vitest/Playwright harness; manual + `npm run build` is the bar).

## Empirical findings (verified before design)

- `audit_log.event_type` for EXITs is `'position_exit'` (not `'exit_alert'` and not `'c1'`).
- `audit_log.actor` is `'system'`, not `'c1'` — filter on `event_type`, not `actor`.
- `audit_log.reason` payload schema:
  `{ "alert_id", "condition_id", "outcome", "entry_price", "exit_price", "exit_size_usd", "pnl_pct", "time_held_h" }` (long names, not the `entry`/`exit` short form one might assume).
- `audit_log.target` is `'EXIT_YYYYMMDD_NNNN'`.
- `tracked_wallets.notes` is the wallet display name (e.g., `"sbimbg"`, `"Aenews2"`).
- The current Overview KPI grid has 4 cards: `Alertes 24h`, `Win Rate`, `Wallets actifs`, `Coûts mois`.
- Theme palette has `accent-blue`, `accent-violet`, `accent-cyan`, `pnl-positive`, `pnl-negative`. Violet is already used for "Features" tags inside `AlertCard` — reusing it for EXIT badges would weaken that signal.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| BUY ↔ EXIT visual coupling | **Wallet detail only** | On the global Alerts page the timeline mixes wallets/markets — coupling adds noise. On the wallet page it is the position lifecycle, which is the whole point. |
| Overview KPI for EXITs | **Replace `Coûts mois` with `Exits 7j`** | `Coûts mois` is the most ops-y of the four cards and is reachable on the System page. EXIT activity pairs naturally with `Alertes 24h` as a flow indicator. |
| EXIT accent color | **Add `accent-warning: #f59e0b` to `@theme`** | Avoids violet's existing role for features tags; one-line theme change owns the token forever; matches the ⚠️ vibe of the Telegram message. |
| Endpoint shape | **New `/api/timeline`** (additive, not extending `/api/alerts`) | Keeps existing endpoint stable; cleaner SQL via two CTEs + `UNION ALL`. |
| Type filter applies to | **Both wallets-mixed pages** | Alerts page gets a new `Type: [All|BUY|EXIT]` pill row; WalletDetail does its own client-side grouping so no filter needed there. |
| Existing filters on EXIT rows | Status drops EXITs; Category applies (inherited from BUY) | EXIT rows have no `resolution_outcome`. Category is a market attribute, valid for both. |

## Architecture

Strictly additive on both ends.

### Backend — `/api/timeline`

```
GET /api/timeline?days=7&wallet=<address>
```

Single SQL implementation in `src/polybot/dashboard/api.py`, built from two CTEs:

```
WITH buy_rows AS (
  SELECT 'buy' AS type, a.alert_id AS id, a.component, a.emitted_at AS created_at,
         a.wallet_address, tw.notes AS wallet_name,
         a.condition_id, m.title AS market_title, m.slug AS market_slug, m.category,
         a.side, t.outcome, a.price, a.size_usd, a.score,
         a.alignment_score, a.shadow_mode,
         ao.resolution_outcome, ao.was_direction_correct, ao.shadow_pnl_simulated,
         ao.price_at_alert, ao.price_at_resolution
  FROM alerts a
  LEFT JOIN markets m ON a.condition_id = m.condition_id
  LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
  LEFT JOIN trades t ON a.trade_hash = t.transaction_hash
  LEFT JOIN tracked_wallets tw ON a.wallet_address = tw.address
  WHERE a.emitted_at >= CURRENT_DATE - INTERVAL '<days> DAY'
    [AND a.wallet_address = ?]
),
exit_rows AS (
  SELECT 'exit' AS type, al.target AS id, NULL AS component,
         al.created_at, al.action AS wallet_address, tw.notes AS wallet_name,
         json_extract_string(al.reason, '$.condition_id') AS condition_id,
         m.title AS market_title, m.slug AS market_slug, m.category,
         json_extract_string(al.reason, '$.alert_id') AS original_alert_id,
         CAST(json_extract(al.reason, '$.entry_price') AS DOUBLE) AS entry_price,
         CAST(json_extract(al.reason, '$.exit_price') AS DOUBLE) AS exit_price,
         CAST(json_extract(al.reason, '$.exit_size_usd') AS DOUBLE) AS exit_size_usd,
         CAST(json_extract(al.reason, '$.pnl_pct') AS DOUBLE) AS pnl_pct,
         CAST(json_extract(al.reason, '$.time_held_h') AS DOUBLE) AS time_held_h,
         json_extract_string(al.reason, '$.outcome') AS outcome
  FROM audit_log al
  LEFT JOIN markets m
    ON m.condition_id = json_extract_string(al.reason, '$.condition_id')
  LEFT JOIN tracked_wallets tw ON al.action = tw.address
  WHERE al.event_type = 'position_exit'
    AND al.created_at >= CURRENT_DATE - INTERVAL '<days> DAY'
    [AND al.action = ?]
)
SELECT * FROM buy_rows
UNION ALL BY NAME
SELECT * FROM exit_rows
ORDER BY created_at DESC
LIMIT 200
```

The Python wrapper assembles two dicts (BUY shape, EXIT shape — see below) keyed by `type` so the frontend dispatches cleanly.

**Defensive parsing.** A row whose `reason` is malformed JSON (or whose JSON-extracted scalar doesn't cast) is skipped at the Python layer with `logger.warning("dashboard_timeline_bad_reason", target=...)`. The endpoint never returns 5xx for one bad row.

**Wallet filter.** `wallet` query param, when provided, is pushed into both CTEs as `AND wallet_address = ?` / `AND al.action = ?`. (`al.action` holds the EXIT's wallet address.)

**Row shape.**

BUY row (matches existing `/api/alerts` row + `type` + `wallet_name`):
```json
{
  "type": "buy",
  "id": "AL_20260425_0003",
  "component": "C1",
  "wallet_address": "0x...",
  "wallet_name": "sbimbg",
  "condition_id": "0x...",
  "market_title": "...",
  "market_slug": "...",
  "category": "Politics",
  "side": "BUY",
  "outcome": "Yes",
  "price": 0.65,
  "size_usd": 5000.0,
  "score": 8.5,
  "alignment_score": 1,
  "shadow_mode": true,
  "resolution_outcome": null,
  "was_direction_correct": null,
  "shadow_pnl_simulated": null,
  "price_at_alert": null,
  "price_at_resolution": null,
  "created_at": "2026-04-25T14:32:00"
}
```

EXIT row:
```json
{
  "type": "exit",
  "id": "EXIT_20260427_0001",
  "wallet_address": "0x...",
  "wallet_name": "sbimbg",
  "condition_id": "0x...",
  "market_title": "...",
  "market_slug": "...",
  "category": "Politics",
  "original_alert_id": "AL_20260425_0003",
  "entry_price": 0.65,
  "exit_price": 0.72,
  "exit_size_usd": 3200.0,
  "pnl_pct": 10.77,
  "time_held_h": 70.18,
  "outcome": "Yes",
  "created_at": "2026-04-27T11:39:04"
}
```

### Frontend — theme

`dashboard/src/index.css`, inside `@theme { ... }`:
```css
--color-accent-warning: #f59e0b;
```
Tailwind v4 auto-generates `text-accent-warning`, `bg-accent-warning/10`, `border-accent-warning/30`, etc.

### Frontend — `dashboard/src/api.js`

```javascript
timeline: ({ days = 7, wallet } = {}) => {
  const qs = new URLSearchParams({ days });
  if (wallet) qs.set("wallet", wallet);
  return `/timeline?${qs}`;
}
```

Type filtering is client-side; backend always returns the merged set.

### Frontend — `ExitCard.jsx` (new)

Lives at `dashboard/src/components/domain/ExitCard.jsx`. Mirrors `AlertCard` structure, swaps colors and content:

- Header: `<LogOut size={14} class="text-accent-warning"/>` + badge `EXIT` (warning palette) + relative time on the right.
- Market title (full, not truncated) — same hover-accent-blue link to Polymarket as `AlertCard`.
- Metrics row (wraps on mobile): `Entry 0.65 → Exit 0.72` (mono prices), `+10.8%` (green if `pnl_pct >= 0`, red otherwise), `Held 70h` via `formatHeld(time_held_h)` helper.
- Footer: `AddressDisplay` (left, links to `/wallets/:address`) + `Original: AL_20260425_0003` chip (right, links to `/alerts?focus=AL_...` for now — focus param is honored by `Alerts.jsx` to scroll the matching card into view).
- No expand/collapse — EXIT card is intentionally simpler than `AlertCard`.

### Frontend — `BuyExitPair.jsx` (new, used only on `WalletDetail`)

Renders an `AlertCard` and an `ExitCard` vertically with a `↳` arrow / thin connecting line in between. Props: `{ buy, exit }`.

### Frontend — `formatHeld(hours)` helper

In `dashboard/src/lib/format.js`. Mirror the daemon's `_humanize_time_held`:
- `hours < 1` → `"<1h"`
- `hours < 24` → `"Nh"` (rounded down)
- `hours >= 24` → `"Nj"` (floor of `hours / 24`)

### Frontend — `Alerts.jsx`

Changes:
- Switch SWR to `urls.timeline({ days, wallet: null })`.
- Add a 5th filter pill row above the others:
  ```
  Type: [Tous] [BUY] [EXIT]
  ```
  Stored in URL searchParam `type`.
- Filter logic in `filtered`:
  - `type` filter → `r.type === filterType`.
  - `status` filter → drops `r.type === 'exit'`; existing logic on BUY rows is unchanged.
  - `category` filter → applies to both (EXIT inherits via JOIN).
- Renderer:
  ```jsx
  filtered.map((r) =>
    r.type === "buy"
      ? <AlertCard key={r.id} alert={r} />
      : <ExitCard key={r.id} exit={r} />
  )
  ```

### Frontend — `Overview.jsx`

- Replace the `Coûts mois` `KpiCard` with `<KpiCard label="Exits 7j" value={exitCount} />`. Source: `useSWR(urls.timeline({ days: 7 }))`, `value = data?.filter(r => r.type === 'exit').length ?? 0`.
- "Dernières alertes" feed switches to `useSWR(urls.timeline({ days: 7 }))`, dispatches `AlertCard`/`ExitCard` per `r.type`. Keep the existing `slice(0, 5)` cap; EXITs count toward the 5.
- Remove the `useSWR(urls.costs())` call only if it ends up unused after the KPI swap.

### Frontend — `WalletDetail.jsx`

Add a new section "Timeline" **above** the existing "Trades récents" table.

```
useSWR(urls.timeline({ wallet: address, days: 365 }))
```

Client-side grouping algorithm:

```
// 1. Index EXITs by the BUY they close.
buy_to_exit = {}
for r in rows where r.type === 'exit':
  buy_to_exit[r.original_alert_id] = r

// 2. Walk rows once. Pair on the BUY (so we always see it before deciding).
groups = []
paired_exit_ids = new Set()

for r in rows:
  if r.type === 'buy':
    exit = buy_to_exit[r.id]   // may be undefined
    if exit:
      groups.push({ kind: 'pair', buy: r, exit, sortKey: exit.created_at })
      paired_exit_ids.add(exit.id)
    else:
      groups.push({ kind: 'buy_only', buy: r, sortKey: r.created_at })
  else: // r.type === 'exit'
    if !paired_exit_ids.has(r.id):
      groups.push({ kind: 'exit_orphan', exit: r, sortKey: r.created_at })
      // EXIT outside the BUY window — referenced BUY is older than 365d.

// 3. Sort groups by their sortKey DESC and render.
groups.sort((a, b) => b.sortKey - a.sortKey)

render each group:
  pair        -> <BuyExitPair buy exit />
  exit_orphan -> <ExitCard exit />
  buy_only    -> <AlertCard alert={buy} />
```

Existing "Trades récents" table stays as-is — it shows raw on-chain trades (BUY/SELL), which is a different lens from the C1-alert/EXIT-notification lifecycle.

## Files touched

| File | Change | Approx LOC |
|------|--------|------------|
| `src/polybot/dashboard/api.py` | Add `/api/timeline` endpoint | +90 |
| `tests/unit/test_dashboard_api.py` | 5 new tests for timeline | +180 |
| `dashboard/src/index.css` | Add `--color-accent-warning` | +1 |
| `dashboard/src/api.js` | Add `timeline()` URL builder | +6 |
| `dashboard/src/lib/format.js` | Add `formatHeld(hours)` | +12 |
| `dashboard/src/components/domain/ExitCard.jsx` | New component | +85 |
| `dashboard/src/components/domain/BuyExitPair.jsx` | New, wallet-detail only | +35 |
| `dashboard/src/pages/Alerts.jsx` | Type filter + dual rendering + timeline source | +30 net |
| `dashboard/src/pages/Overview.jsx` | KPI swap + dual rendering in feed | +20 net |
| `dashboard/src/pages/WalletDetail.jsx` | New "Timeline" section | +60 |

No new files outside `dashboard/src/components/domain/` and `tests/`. No migration. No daemon change.

## Test plan

Backend tests (append to existing `tests/unit/test_dashboard_api.py`):

| # | Test | Asserts |
|---|------|---------|
| 1 | `test_timeline_merges_buy_and_exit` | Seed 1 BUY alert + 1 audit_log EXIT row → both returned, both have correct `type` and required fields. |
| 2 | `test_timeline_orders_desc` | Seed BUY at T-2h, EXIT at T-1h → EXIT first in response. |
| 3 | `test_timeline_filters_by_wallet` | Seed 2 wallets each with BUY+EXIT, query with `wallet=<addr>` → only that wallet's 2 rows. |
| 4 | `test_timeline_skips_malformed_reason` | Seed audit_log row with `reason='not json'` → endpoint returns 200, that row absent, others present. |
| 5 | `test_timeline_resolves_market_title` | EXIT references an alert whose market has a known `title` → returned EXIT row has that `market_title`. |

Frontend verification (no test harness):

- `npm run build` clean.
- `npm run dev` → load Alerts page → existing BUY cards render unchanged; new EXIT cards render distinct (warning palette, ⚠️ icon) when EXITs are in the DB.
- Type filter pills: `EXIT` only → only EXIT cards; `BUY` only → only BUY cards.
- Overview KPI shows `Exits 7j` instead of `Coûts mois`.
- Wallet detail (pick a wallet with both BUY alerts and an EXIT, e.g., re-run the smoke forge if needed): Timeline section shows `BuyExitPair` for matched lifecycles.
- Mobile viewport ≤ 375px: `ExitCard` metrics row wraps; market title remains untruncated (CSS-wrapped only).

## Acceptance criteria

1. All 5 backend tests pass + existing `test_dashboard_api.py` suite remains green.
2. `cd dashboard && npm run build` exits 0 with no new warnings.
3. With at least one BUY alert and one EXIT in the live DB, both surfaces render correctly (Alerts list, Overview feed, WalletDetail timeline).
4. Existing filters (`Composant`, `Période`, `Status`, `Catégorie`) still work on `Alerts.jsx` after the change.

## Deployment

```
cd dashboard && npm run build
rsync -Rv \
  src/polybot/dashboard/api.py \
  tests/unit/test_dashboard_api.py \
  dashboard/dist/ \
  dashboard/src/  \
  polybot:/root/polybot/
ssh polybot 'systemctl restart polybot-bot.service'
```

(Caddy serves `dashboard/dist/` automatically; the daemon embeds the FastAPI app and is restarted to pick up the new endpoint.)

## Out of scope (deferred)

- Telemetry on EXIT-card render counts (no metrics infra in dashboard yet).
- A dedicated `/exits` route (Alerts page covers it via the Type filter).
- Search/sort beyond the existing pills.
- Persistent EXIT dedup history endpoint (the in-memory set already covers the bot use case).
