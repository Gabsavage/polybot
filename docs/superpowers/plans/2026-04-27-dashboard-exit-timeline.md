# Dashboard EXIT Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render C1 EXIT alerts (audit_log) alongside BUY alerts (alerts table) in the web dashboard via a new `/api/timeline` endpoint and two new frontend components, with BUY-EXIT lifecycle pairing on the wallet detail page.

**Architecture:** Strictly additive — new FastAPI endpoint, two new React components (`ExitCard`, `BuyExitPair`), one theme token (`accent-warning`), one `lib/format.js` helper (`formatHeld`). Existing `/api/alerts` endpoint and `AlertCard` component remain untouched. The timeline endpoint UNIONs two CTEs (alerts → BUY rows; audit_log filtered on `event_type='position_exit'` → EXIT rows) sorted DESC.

**Tech Stack:** Python 3.13, FastAPI, DuckDB, pytest; React 18, Vite, SWR, Tailwind v4 `@theme`, lucide-react, react-router-dom.

**Spec:** `docs/superpowers/specs/2026-04-27-dashboard-exit-timeline-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/polybot/dashboard/api.py` | Adds `GET /api/timeline` reading both `alerts` and `audit_log`. |
| `tests/unit/test_dashboard_api.py` | Adds 5 tests covering the new endpoint. |
| `dashboard/src/index.css` | Adds `--color-accent-warning` token to `@theme`. |
| `dashboard/src/api.js` | Adds `timeline()` URL builder. |
| `dashboard/src/lib/format.js` | Adds `formatHeld(hours)` helper. |
| `dashboard/src/components/domain/ExitCard.jsx` | NEW. Glass card for one EXIT row. |
| `dashboard/src/components/domain/BuyExitPair.jsx` | NEW. Couples one BUY card and one EXIT card with a connector — used only on `WalletDetail.jsx`. |
| `dashboard/src/pages/Alerts.jsx` | Switch to `/api/timeline`, add Type filter pill row, dispatch BUY/EXIT card. |
| `dashboard/src/pages/Overview.jsx` | Replace `Coûts mois` KPI with `Exits 7j`; dual-render the recent-alerts feed. |
| `dashboard/src/pages/WalletDetail.jsx` | Add a "Timeline" section above "Trades récents" that uses `BuyExitPair` to render position lifecycles. |

No new files outside the table above. No DB migration. No daemon code change.

---

## Conventions used throughout

- Working directory: `/Users/gabsav/Documents/Polycasquette/Code`. Branch: `main`.
- Backend tests: `uv run pytest tests/unit/test_dashboard_api.py -v`.
- Frontend build check: `cd dashboard && npm run build`.
- Deploy at the end via `rsync` to `polybot:/root/polybot/` and `systemctl restart polybot-bot.service`.
- Each task ends with one Conventional Commit on `main` (no branch).

---

## Task 1: Backend `/api/timeline` endpoint

**Files:**
- Modify: `src/polybot/dashboard/api.py` (append a new endpoint near `/api/audit`, around line 318)
- Test: `tests/unit/test_dashboard_api.py` (append a new `class TestTimeline` after the existing tests)

The endpoint UNIONs two CTEs and parses each EXIT's JSON `reason` defensively. Malformed JSON is skipped at the Python layer.

- [ ] **Step 1: Write the 5 failing tests**

Append to `tests/unit/test_dashboard_api.py` (preserve all existing imports — they already include `duckdb`, `pytest`, `TestClient`, `_seed_alerts`):

```python
def _seed_timeline(db_path: str) -> None:
    """Seed alerts + audit_log rows for timeline tests, on top of _seed_alerts()."""
    con = duckdb.connect(db_path)
    # Wallet display name on wallet_0.
    con.execute(
        "UPDATE tracked_wallets SET notes = 'sbimbg' WHERE address = '0xwallet_0'"
    )
    # An EXIT closing alert a1 (which was on cond_1).
    con.execute(
        "INSERT INTO audit_log (event_type, target, action, reason, actor) "
        "VALUES ('position_exit', 'EXIT_20260427_0001', '0xwallet_0', "
        "        ?, 'system')",
        ['{"alert_id": "a1", "condition_id": "cond_1", "outcome": "Yes", '
         '"entry_price": 0.65, "exit_price": 0.72, "exit_size_usd": 3200.0, '
         '"pnl_pct": 10.77, "time_held_h": 70.18}'],
    )
    con.close()


class TestTimeline:
    """Uses the existing `client` fixture (defined at line 240) which wires
    the test DB into the API via `app.dependency_overrides[get_db]`."""

    def test_merges_buy_and_exit(self, client, db_path):
        _seed_alerts(db_path)
        _seed_timeline(db_path)
        resp = client.get("/api/timeline?days=30")
        assert resp.status_code == 200
        rows = resp.json()
        types = sorted({r["type"] for r in rows})
        assert types == ["buy", "exit"]
        exit_row = next(r for r in rows if r["type"] == "exit")
        assert exit_row["id"] == "EXIT_20260427_0001"
        assert exit_row["original_alert_id"] == "a1"
        assert exit_row["entry_price"] == 0.65
        assert exit_row["exit_price"] == 0.72
        assert abs(exit_row["pnl_pct"] - 10.77) < 0.01
        assert exit_row["wallet_name"] == "sbimbg"
        assert exit_row["market_title"] == "Market One"

    def test_orders_desc(self, client, db_path):
        # BUY at T-2h, EXIT at T-1h → EXIT must come first.
        _seed_alerts(db_path)
        con = duckdb.connect(db_path)
        # Push the BUY back 2h.
        con.execute(
            "UPDATE alerts SET emitted_at = CURRENT_TIMESTAMP - INTERVAL 2 HOUR "
            "WHERE alert_id = 'a1'"
        )
        # EXIT at T-1h.
        con.execute(
            "INSERT INTO audit_log "
            "(event_type, target, action, reason, actor, created_at) "
            "VALUES ('position_exit', 'EXIT_20260427_0001', '0xwallet_0', ?, "
            "'system', CURRENT_TIMESTAMP - INTERVAL 1 HOUR)",
            ['{"alert_id": "a1", "condition_id": "cond_1", "outcome": "Yes", '
             '"entry_price": 0.65, "exit_price": 0.72, "exit_size_usd": 100.0, '
             '"pnl_pct": 10.77, "time_held_h": 1.0}'],
        )
        con.close()
        resp = client.get("/api/timeline?days=1")
        assert resp.status_code == 200
        rows = resp.json()
        # First row is the EXIT (most recent).
        assert rows[0]["type"] == "exit"
        # The BUY follows.
        assert any(r["type"] == "buy" and r["id"] == "a1" for r in rows[1:])

    def test_filters_by_wallet(self, client, db_path):
        _seed_alerts(db_path)
        con = duckdb.connect(db_path)
        # EXIT for wallet_0
        con.execute(
            "INSERT INTO audit_log (event_type, target, action, reason, actor) "
            "VALUES ('position_exit', 'EXIT_20260427_0001', '0xwallet_0', ?, 'system')",
            ['{"alert_id": "a1", "condition_id": "cond_1", "outcome": "Yes", '
             '"entry_price": 0.65, "exit_price": 0.72, "exit_size_usd": 100.0, '
             '"pnl_pct": 10.77, "time_held_h": 1.0}'],
        )
        # EXIT for wallet_1
        con.execute(
            "INSERT INTO audit_log (event_type, target, action, reason, actor) "
            "VALUES ('position_exit', 'EXIT_20260427_0002', '0xwallet_1', ?, 'system')",
            ['{"alert_id": "a2", "condition_id": "cond_1", "outcome": "No", '
             '"entry_price": 0.35, "exit_price": 0.30, "exit_size_usd": 100.0, '
             '"pnl_pct": -14.29, "time_held_h": 1.0}'],
        )
        con.close()
        resp = client.get("/api/timeline?days=30&wallet=0xwallet_0")
        assert resp.status_code == 200
        rows = resp.json()
        assert all(r["wallet_address"] == "0xwallet_0" for r in rows)
        assert any(r["type"] == "exit" and r["id"] == "EXIT_20260427_0001" for r in rows)
        assert not any(r.get("id") == "EXIT_20260427_0002" for r in rows)

    def test_skips_malformed_reason(self, client, db_path):
        _seed_alerts(db_path)
        con = duckdb.connect(db_path)
        # Valid EXIT
        con.execute(
            "INSERT INTO audit_log (event_type, target, action, reason, actor) "
            "VALUES ('position_exit', 'EXIT_20260427_0001', '0xwallet_0', ?, 'system')",
            ['{"alert_id": "a1", "condition_id": "cond_1", "outcome": "Yes", '
             '"entry_price": 0.65, "exit_price": 0.72, "exit_size_usd": 100.0, '
             '"pnl_pct": 10.77, "time_held_h": 1.0}'],
        )
        # Malformed (not JSON)
        con.execute(
            "INSERT INTO audit_log (event_type, target, action, reason, actor) "
            "VALUES ('position_exit', 'EXIT_20260427_0002', '0xwallet_0', "
            "'this is not json', 'system')"
        )
        con.close()
        resp = client.get("/api/timeline?days=30")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert "EXIT_20260427_0001" in ids
        assert "EXIT_20260427_0002" not in ids

    def test_resolves_market_title(self, client, db_path):
        _seed_alerts(db_path)
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO audit_log (event_type, target, action, reason, actor) "
            "VALUES ('position_exit', 'EXIT_20260427_0001', '0xwallet_0', ?, 'system')",
            ['{"alert_id": "a1", "condition_id": "cond_1", "outcome": "Yes", '
             '"entry_price": 0.65, "exit_price": 0.72, "exit_size_usd": 100.0, '
             '"pnl_pct": 10.77, "time_held_h": 1.0}'],
        )
        con.close()
        resp = client.get("/api/timeline?days=30")
        exit_row = next(r for r in resp.json() if r["type"] == "exit")
        assert exit_row["market_title"] == "Market One"
        assert exit_row["market_slug"] == "market-one"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestTimeline -v
```

Expected: 5 failures with `404 Not Found` (the route does not exist yet).

- [ ] **Step 3: Add the endpoint to `api.py`**

Open `src/polybot/dashboard/api.py`. Near the bottom, after the existing `@app.get("/api/audit")` handler (around line 339), append:

```python
@app.get("/api/timeline")
def get_timeline(
    con: DB,
    days: int = Query(default=7, ge=1, le=365),
    wallet: str | None = None,
):
    """Unified BUY+EXIT timeline. Merges alerts (type=buy) and
    audit_log position_exit rows (type=exit), sorted DESC by created_at.
    """
    import json as _json

    interval = f"{days} DAY"

    # --- BUY rows (mirror /api/alerts shape, plus wallet_name and type) ---
    buy_sql = (
        "SELECT a.alert_id, a.component, a.emitted_at, a.wallet_address, "
        "       tw.notes AS wallet_name, "
        "       a.condition_id, a.side, a.size_usd, a.price, a.score, "
        "       a.alignment_score, a.shadow_mode, a.features_passed, "
        "       m.title AS market_title, m.slug AS market_slug, m.category, "
        "       ao.resolution_outcome, ao.was_direction_correct, "
        "       ao.shadow_pnl_simulated, ao.price_at_alert, "
        "       ao.price_at_resolution, t.outcome "
        "FROM alerts a "
        "LEFT JOIN markets m ON a.condition_id = m.condition_id "
        "LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id "
        "LEFT JOIN trades t ON a.trade_hash = t.transaction_hash "
        "LEFT JOIN tracked_wallets tw ON a.wallet_address = tw.address "
        f"WHERE a.emitted_at >= CURRENT_DATE - INTERVAL '{interval}'"
    )
    buy_params: list = []
    if wallet:
        buy_sql += " AND a.wallet_address = ?"
        buy_params.append(wallet)
    buy_sql += " ORDER BY a.emitted_at DESC"
    buy_rows = con.execute(buy_sql, buy_params).fetchall()

    buys = [
        {
            "type": "buy",
            "id": r[0],
            "component": r[1],
            "created_at": str(r[2]) if r[2] else None,
            "wallet_address": r[3],
            "wallet_name": r[4],
            "condition_id": r[5],
            "side": r[6],
            "size_usd": float(r[7]) if r[7] is not None else None,
            "price": float(r[8]) if r[8] is not None else None,
            "score": r[9],
            "alignment_score": r[10],
            "shadow_mode": r[11],
            "features_passed": r[12],
            "market_title": r[13],
            "market_slug": r[14],
            "category": r[15],
            "resolution_outcome": r[16],
            "was_direction_correct": r[17],
            "shadow_pnl_simulated": float(r[18]) if r[18] is not None else None,
            "price_at_alert": float(r[19]) if r[19] is not None else None,
            "price_at_resolution": float(r[20]) if r[20] is not None else None,
            "outcome": r[21],
        }
        for r in buy_rows
    ]

    # --- EXIT rows (parse JSON reason in Python so malformed rows skip safely) ---
    exit_sql = (
        "SELECT al.target, al.action, al.reason, al.created_at, "
        "       tw.notes AS wallet_name "
        "FROM audit_log al "
        "LEFT JOIN tracked_wallets tw ON al.action = tw.address "
        f"WHERE al.event_type = 'position_exit' "
        f"  AND al.created_at >= CURRENT_DATE - INTERVAL '{interval}'"
    )
    exit_params: list = []
    if wallet:
        exit_sql += " AND al.action = ?"
        exit_params.append(wallet)
    exit_sql += " ORDER BY al.created_at DESC"
    exit_raw = con.execute(exit_sql, exit_params).fetchall()

    exits: list[dict] = []
    market_titles: dict[str, tuple[str | None, str | None, str | None]] = {}
    for target, action, reason, created_at, wallet_name in exit_raw:
        try:
            payload = _json.loads(reason) if reason else {}
        except (ValueError, TypeError):
            logger.warning("dashboard_timeline_bad_reason", target=target)
            continue
        cond_id = payload.get("condition_id")
        if cond_id and cond_id not in market_titles:
            mrow = con.execute(
                "SELECT title, slug, category FROM markets WHERE condition_id = ?",
                [cond_id],
            ).fetchone()
            market_titles[cond_id] = mrow if mrow else (None, None, None)
        title, slug, category = market_titles.get(cond_id, (None, None, None))
        exits.append({
            "type": "exit",
            "id": target,
            "wallet_address": action,
            "wallet_name": wallet_name,
            "condition_id": cond_id,
            "market_title": title,
            "market_slug": slug,
            "category": category,
            "original_alert_id": payload.get("alert_id"),
            "entry_price": payload.get("entry_price"),
            "exit_price": payload.get("exit_price"),
            "exit_size_usd": payload.get("exit_size_usd"),
            "pnl_pct": payload.get("pnl_pct"),
            "time_held_h": payload.get("time_held_h"),
            "outcome": payload.get("outcome"),
            "created_at": str(created_at) if created_at else None,
        })

    # Merge and sort DESC by created_at (string compare works because
    # both come from str(TIMESTAMP) in the same wall-clock format).
    merged = sorted(
        buys + exits,
        key=lambda r: r["created_at"] or "",
        reverse=True,
    )
    return merged[:200]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_dashboard_api.py::TestTimeline -v
```

Expected: PASS (5/5).

- [ ] **Step 5: Run full dashboard test file to confirm no regression**

```bash
uv run pytest tests/unit/test_dashboard_api.py -q
```

Expected: all PASS (existing + 5 new).

- [ ] **Step 6: Commit**

```bash
git add src/polybot/dashboard/api.py tests/unit/test_dashboard_api.py
git commit -m "feat(api): GET /api/timeline merges BUY alerts + EXIT audit_log"
```

---

## Task 2: Frontend theme — add `accent-warning`

**Files:**
- Modify: `dashboard/src/index.css` (one-line addition inside `@theme {...}`)

- [ ] **Step 1: Add the token**

Open `dashboard/src/index.css`. Inside the `@theme {...}` block (between `--color-accent-cyan` and `--color-pnl-positive`), insert:

```css
  --color-accent-warning: #f59e0b;
```

The full theme block should look like this excerpt after the change:

```css
  --color-accent-blue: #4f70ff;
  --color-accent-violet: #a855f7;
  --color-accent-cyan: #22d3ee;
  --color-accent-warning: #f59e0b;
  --color-pnl-positive: #22c55e;
  --color-pnl-negative: #ef4444;
```

- [ ] **Step 2: Verify Tailwind picks it up**

```bash
cd dashboard && npm run build
```

Expected: build exits 0 with no warnings about unknown classes (no class consumes it yet, but Tailwind v4 generates utilities lazily so this just confirms the syntax is valid).

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/index.css
git commit -m "feat(dashboard): add accent-warning theme token for EXIT cards"
```

---

## Task 3: Frontend `api.js` — `timeline()` URL builder

**Files:**
- Modify: `dashboard/src/api.js`

- [ ] **Step 1: Add the URL builder**

Open `dashboard/src/api.js`. Inside the `urls` export object, after the `audit:` line (around line 23), append:

```javascript
  timeline: ({ days = 7, wallet } = {}) => {
    const qs = new URLSearchParams({ days });
    if (wallet) qs.set("wallet", wallet);
    return `/timeline?${qs}`;
  },
```

The full `urls` object after the change reads:

```javascript
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
  timeline: ({ days = 7, wallet } = {}) => {
    const qs = new URLSearchParams({ days });
    if (wallet) qs.set("wallet", wallet);
    return `/timeline?${qs}`;
  },
};
```

- [ ] **Step 2: Verify build**

```bash
cd dashboard && npm run build
```

Expected: build exits 0.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/api.js
git commit -m "feat(dashboard): add urls.timeline() URL builder"
```

---

## Task 4: Frontend `formatHeld` helper

**Files:**
- Modify: `dashboard/src/lib/format.js`

- [ ] **Step 1: Add the helper**

Open `dashboard/src/lib/format.js`. Append at the bottom of the file:

```javascript
export function formatHeld(hours) {
  if (hours == null || isNaN(hours)) return "—";
  if (hours < 1) return "<1h";
  if (hours < 24) return `${Math.floor(hours)}h`;
  return `${Math.floor(hours / 24)}j`;
}
```

- [ ] **Step 2: Verify build**

```bash
cd dashboard && npm run build
```

Expected: build exits 0.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/lib/format.js
git commit -m "feat(dashboard): formatHeld helper for EXIT time-held display"
```

---

## Task 5: Frontend `ExitCard.jsx` component

**Files:**
- Create: `dashboard/src/components/domain/ExitCard.jsx`

- [ ] **Step 1: Create the file**

Create `dashboard/src/components/domain/ExitCard.jsx` with this content:

```jsx
import { useNavigate } from "react-router-dom";
import { ExternalLink, LogOut } from "lucide-react";
import GlassCard from "../primitives/GlassCard";
import AddressDisplay from "../primitives/AddressDisplay";
import { formatUSD, formatRelative, formatHeld } from "../../lib/format";

export default function ExitCard({ exit: e }) {
  const navigate = useNavigate();
  const polymarketUrl = e.market_slug
    ? `https://polymarket.com/event/${e.market_slug}`
    : null;
  const pnlSign = e.pnl_pct >= 0 ? "+" : "";
  const pnlColor =
    e.pnl_pct == null
      ? "text-text-secondary"
      : e.pnl_pct >= 0
      ? "text-pnl-positive"
      : "text-pnl-negative";

  return (
    <GlassCard className="card-hover">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-accent-warning/10 text-accent-warning">
            <LogOut size={12} />
            EXIT
          </span>
          <span className="text-xs text-text-secondary">
            {formatRelative(e.created_at)}
          </span>
        </div>
        <span className="text-[10px] font-mono text-text-tertiary">{e.id}</span>
      </div>

      <div className="mt-3 flex items-start justify-between gap-3">
        {polymarketUrl ? (
          <a
            href={polymarketUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-base font-semibold text-text-primary hover:text-accent-blue transition-colors inline-flex items-start gap-1.5"
          >
            {e.market_title || "Marché inconnu"}
            <ExternalLink size={13} className="mt-1 flex-shrink-0 opacity-60" />
          </a>
        ) : (
          <span className="text-base font-semibold text-text-primary">
            {e.market_title || "Marché inconnu"}
          </span>
        )}
        {e.category && (
          <span className="px-2 py-0.5 bg-white/[0.05] text-text-secondary rounded text-[10px] uppercase tracking-wider whitespace-nowrap flex-shrink-0">
            {e.category}
          </span>
        )}
      </div>

      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <span className="font-mono text-text-secondary">
          Entry{" "}
          <span className="text-text-primary">{e.entry_price?.toFixed(2)}</span>{" "}
          → Exit{" "}
          <span className="text-text-primary">{e.exit_price?.toFixed(2)}</span>
        </span>
        <span className={`font-semibold ${pnlColor}`}>
          {pnlSign}
          {e.pnl_pct?.toFixed(1)}%
        </span>
        <span className="text-text-secondary">
          Size <span className="text-text-primary">${formatUSD(e.exit_size_usd)}</span>
        </span>
        <span className="text-text-secondary">
          Held <span className="text-text-primary">{formatHeld(e.time_held_h)}</span>
        </span>
      </div>

      <div className="mt-2 flex items-center justify-between text-xs">
        <button
          onClick={() => navigate(`/wallets/${e.wallet_address}`)}
          className="text-text-secondary hover:text-accent-blue transition-colors"
        >
          {e.wallet_name ? (
            <span>
              {e.wallet_name}{" "}
              <AddressDisplay address={e.wallet_address} />
            </span>
          ) : (
            <AddressDisplay address={e.wallet_address} />
          )}
        </button>
        {e.original_alert_id && (
          <span className="font-mono text-text-tertiary">
            Original: {e.original_alert_id}
          </span>
        )}
      </div>
    </GlassCard>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd dashboard && npm run build
```

Expected: build exits 0. The component is unused at this point but must compile.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/domain/ExitCard.jsx
git commit -m "feat(dashboard): ExitCard component for EXIT timeline rows"
```

---

## Task 6: Frontend `BuyExitPair.jsx` component

**Files:**
- Create: `dashboard/src/components/domain/BuyExitPair.jsx`

- [ ] **Step 1: Create the file**

Create `dashboard/src/components/domain/BuyExitPair.jsx`:

```jsx
import { CornerDownRight } from "lucide-react";
import AlertCard from "./AlertCard";
import ExitCard from "./ExitCard";

export default function BuyExitPair({ buy, exit }) {
  return (
    <div className="relative flex flex-col gap-2">
      <AlertCard alert={buy} />
      <div className="flex items-center gap-2 pl-4 text-text-tertiary">
        <CornerDownRight size={14} />
        <span className="h-px flex-1 bg-white/[0.06]" />
      </div>
      <ExitCard exit={exit} />
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd dashboard && npm run build
```

Expected: build exits 0.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/domain/BuyExitPair.jsx
git commit -m "feat(dashboard): BuyExitPair component for wallet timeline lifecycle"
```

---

## Task 7: `Alerts.jsx` — Type filter + dual rendering

**Files:**
- Modify: `dashboard/src/pages/Alerts.jsx`

This task switches the data source from `/api/alerts` to `/api/timeline`, adds a 5th filter pill row (`Type`), and dispatches `AlertCard`/`ExitCard` per row type. Status filter drops EXIT rows; Category filter applies to both.

- [ ] **Step 1: Replace the file content**

Replace the entire content of `dashboard/src/pages/Alerts.jsx` with:

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
import ExitCard from "../components/domain/ExitCard";

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
const TYPE_OPTIONS = [
  { value: null, label: "Tous" },
  { value: "buy", label: "BUY" },
  { value: "exit", label: "EXIT" },
];

function buyStatus(buy) {
  if (!buy.resolution_outcome || buy.resolution_outcome === "PENDING") return "pending";
  return buy.was_direction_correct ? "correct" : "incorrect";
}

export default function Alerts() {
  const [params, setParams] = useSearchParams();
  const component = params.get("component");
  const days = params.get("days") || "7";
  const status = params.get("status");
  const category = params.get("category");
  const type = params.get("type");

  const { data, error, isLoading, mutate } = useSWR(
    urls.timeline({ days: parseInt(days) }),
    { refreshInterval: 60_000 }
  );

  function setParam(key, value) {
    const next = new URLSearchParams(params);
    if (value == null) next.delete(key);
    else next.set(key, value);
    setParams(next);
  }

  const categoryOptions = [
    { value: null, label: "Toutes" },
    ...Array.from(new Set((data || []).map((r) => r.category).filter(Boolean)))
      .sort()
      .map((c) => ({ value: c, label: c })),
  ];

  const filtered = (data || []).filter((r) => {
    if (type && r.type !== type) return false;
    if (component && r.type === "buy" && r.component !== component) return false;
    if (component && r.type === "exit") return false; // component filter excludes EXITs
    if (status) {
      if (r.type !== "buy") return false;
      if (buyStatus(r) !== status) return false;
    }
    if (category && r.category !== category) return false;
    return true;
  });

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl md:text-4xl font-light tracking-tight">Alertes</h1>

      <div className="flex flex-col md:flex-row md:items-center gap-4 flex-wrap">
        <div>
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-1">Type</div>
          <FilterPills options={TYPE_OPTIONS} value={type} onChange={(v) => setParam("type", v)} />
        </div>
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
        {categoryOptions.length > 1 && (
          <div>
            <div className="text-xs uppercase tracking-wider text-text-secondary mb-1">Catégorie</div>
            <FilterPills options={categoryOptions} value={category} onChange={(v) => setParam("category", v)} />
          </div>
        )}
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => mutate()} />
      ) : isLoading ? (
        <SkeletonList count={8} height={140} />
      ) : !filtered?.length ? (
        <EmptyState icon={Inbox} message="Aucune alerte sur ces critères" />
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((r) =>
            r.type === "buy" ? (
              <AlertCard key={r.id} alert={{ ...r, alert_id: r.id, emitted_at: r.created_at }} />
            ) : (
              <ExitCard key={r.id} exit={r} />
            )
          )}
        </div>
      )}
    </div>
  );
}
```

**Note on the AlertCard prop spread:** the existing `AlertCard` reads `alert.alert_id` and `alert.emitted_at`. The timeline row uses `id` and `created_at`. The spread `{ ...r, alert_id: r.id, emitted_at: r.created_at }` keeps `AlertCard` unchanged while feeding it the right field names. (We deliberately do not touch `AlertCard` in this task.)

- [ ] **Step 2: Verify build**

```bash
cd dashboard && npm run build
```

Expected: build exits 0.

- [ ] **Step 3: Manual smoke (optional, fast)**

```bash
cd dashboard && npm run dev
```

Open `http://localhost:5173/alerts`. Confirm:
- Page loads without errors in console.
- Existing BUY cards render (assuming there are BUY alerts in `days=7`).
- The new `Type` pill row is at the top of the filter row.
- Selecting `BUY` shows only BUY cards. Selecting `EXIT` shows only EXIT cards (or empty if none in window).

Stop the dev server when done.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/pages/Alerts.jsx
git commit -m "feat(dashboard): Alerts page uses /api/timeline + Type filter"
```

---

## Task 8: `Overview.jsx` — KPI swap + dual feed

**Files:**
- Modify: `dashboard/src/pages/Overview.jsx`

Replace the `Coûts mois` KPI with `Exits 7j` and switch the recent-alerts feed to dispatch by `type`.

- [ ] **Step 1: Replace the file content**

Replace the entire content of `dashboard/src/pages/Overview.jsx` with:

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
import ExitCard from "../components/domain/ExitCard";
import IndexerRow from "../components/domain/IndexerRow";
import HotMarketRow from "../components/domain/HotMarketRow";
import { formatUSD, formatPct } from "../lib/format";
import { pnlColor } from "../lib/colors";

export default function Overview() {
  const { data: perf, error: perfError } = useSWR(urls.performance(30), { refreshInterval: 60_000 });
  const { data: timeline, error: timelineError } = useSWR(urls.timeline({ days: 7 }), { refreshInterval: 60_000 });
  const { data: alerts24 } = useSWR(urls.alerts({ days: 1 }), { refreshInterval: 60_000 });
  const { data: status, error: statusError } = useSWR(urls.status(), { refreshInterval: 30_000 });
  const { data: hotMarkets } = useSWR(urls.hotMarkets(), { refreshInterval: 120_000 });
  const { data: wallets } = useSWR(urls.wallets());

  // Build pnl_series for hero chart from perf.daily
  const pnlSeries = (perf?.daily || []).reduce((acc, d) => {
    const existing = acc.find((x) => x.day === d.day);
    if (existing) existing.cum_pnl = (existing.cum_pnl || 0) + (d.pnl || 0);
    else acc.push({ day: d.day, cum_pnl: d.pnl || 0 });
    return acc;
  }, []);
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
  const exits7d = (timeline || []).filter((r) => r.type === "exit").length;

  const recent = (timeline || []).slice(0, 5);

  return (
    <div className="flex flex-col gap-6">
      {/* Hero */}
      <GlassCard hero className="p-8">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-wider text-text-secondary mb-2">
              Shadow P&L cumulé
            </div>
            <div className={`text-4xl md:text-6xl font-light tracking-tight ${pnlColor(totalPnl)}`}>
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
        <KpiCard label="Exits 7j" value={exits7d} />
      </div>

      {/* Bottom: Alerts (left) + Indexers (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Dernières alertes</h2>
            <Link to="/alerts" className="text-sm text-accent-blue hover:underline inline-flex items-center gap-1">
              Voir tout <ArrowRight size={14} />
            </Link>
          </div>
          {timelineError ? (
            <ErrorState error={timelineError} />
          ) : !timeline ? (
            <SkeletonList count={5} height={140} />
          ) : recent.length === 0 ? (
            <EmptyState icon={Inbox} message="Aucune alerte récente" />
          ) : (
            recent.map((r) =>
              r.type === "buy" ? (
                <AlertCard key={r.id} alert={{ ...r, alert_id: r.id, emitted_at: r.created_at }} />
              ) : (
                <ExitCard key={r.id} exit={r} />
              )
            )
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

Key changes:
- Removed `useSWR(urls.costs())` (no longer used after KPI swap).
- Renamed `alerts`/`alertsError` to `timeline`/`timelineError`, switched URL to `urls.timeline({ days: 7 })`.
- Replaced 4th KPI (`Coûts mois`) with `Exits 7j`.
- Recent-feed renderer dispatches `AlertCard` (with the same id/created_at spread as in `Alerts.jsx`) or `ExitCard` per `r.type`.

- [ ] **Step 2: Verify build**

```bash
cd dashboard && npm run build
```

Expected: build exits 0.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/pages/Overview.jsx
git commit -m "feat(dashboard): Overview shows Exits 7j KPI + EXIT in recent feed"
```

---

## Task 9: `WalletDetail.jsx` — Timeline section

**Files:**
- Modify: `dashboard/src/pages/WalletDetail.jsx`

Adds a new "Timeline" section above "Trades récents" that groups BUY+EXIT into lifecycle pairs.

- [ ] **Step 1: Add the imports and timeline data**

In `dashboard/src/pages/WalletDetail.jsx`, after the existing imports, add `BuyExitPair`, `AlertCard`, `ExitCard`, and the timeline URL. Replace the existing import block (lines 1–17) with:

```jsx
import { useState } from "react";
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
import FilterPills from "../components/primitives/FilterPills";
import ChartArea from "../components/charts/ChartArea";
import AlertCard from "../components/domain/AlertCard";
import ExitCard from "../components/domain/ExitCard";
import BuyExitPair from "../components/domain/BuyExitPair";
import { formatUSD, formatPct, formatRelative } from "../lib/format";
import { pnlColor, sideColor } from "../lib/colors";
```

- [ ] **Step 2: Add the SWR hook + grouping logic inside `WalletDetail()`**

Inside the `WalletDetail` function body, directly after the existing line `const { data: trades } = useSWR(urls.walletTrades(address, 100));` (around line 26), add:

```jsx
  const { data: timeline } = useSWR(urls.timeline({ wallet: address, days: 365 }));
```

Then, just before the existing `if (error)` early return (around line 30), add the grouping helper:

```jsx
  // Group BUY+EXIT into lifecycle pairs for the Timeline section.
  const timelineGroups = (() => {
    if (!timeline) return null;
    const buyToExit = {};
    for (const r of timeline) {
      if (r.type === "exit" && r.original_alert_id) {
        buyToExit[r.original_alert_id] = r;
      }
    }
    const groups = [];
    const pairedExitIds = new Set();
    for (const r of timeline) {
      if (r.type === "buy") {
        const exit = buyToExit[r.id];
        if (exit) {
          groups.push({ kind: "pair", buy: r, exit, sortKey: exit.created_at });
          pairedExitIds.add(exit.id);
        } else {
          groups.push({ kind: "buy_only", buy: r, sortKey: r.created_at });
        }
      } else if (!pairedExitIds.has(r.id)) {
        groups.push({ kind: "exit_orphan", exit: r, sortKey: r.created_at });
      }
    }
    groups.sort((a, b) => (a.sortKey < b.sortKey ? 1 : -1));
    return groups;
  })();
```

- [ ] **Step 3: Insert the Timeline section into the JSX**

Inside the JSX, between the closing `</GlassCard>` of the CEX-funding/cluster sections (around line 156) and the opening of the `Trades récents` section (`<div className="flex flex-col gap-3">` around line 159), insert:

```jsx
      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Timeline (BUY → EXIT)</h2>
        {!timeline ? (
          <SkeletonList count={3} height={140} />
        ) : timelineGroups.length === 0 ? (
          <EmptyState icon={Inbox} message="Aucune alerte ni exit pour ce wallet" />
        ) : (
          <div className="flex flex-col gap-3">
            {timelineGroups.map((g) => {
              if (g.kind === "pair") {
                return (
                  <BuyExitPair
                    key={`pair_${g.buy.id}`}
                    buy={{ ...g.buy, alert_id: g.buy.id, emitted_at: g.buy.created_at }}
                    exit={g.exit}
                  />
                );
              }
              if (g.kind === "buy_only") {
                return (
                  <AlertCard
                    key={`buy_${g.buy.id}`}
                    alert={{ ...g.buy, alert_id: g.buy.id, emitted_at: g.buy.created_at }}
                  />
                );
              }
              return <ExitCard key={`exit_${g.exit.id}`} exit={g.exit} />;
            })}
          </div>
        )}
      </div>
```

(The existing `Trades récents` block immediately follows.)

- [ ] **Step 4: Verify build**

```bash
cd dashboard && npm run build
```

Expected: build exits 0.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/pages/WalletDetail.jsx
git commit -m "feat(dashboard): wallet detail Timeline section with BUY-EXIT pairs"
```

---

## Task 10: Deploy + verify on the VPS

**Files:** none modified.

- [ ] **Step 1: Push commits**

```bash
git push origin main
```

Expected: 9 commits pushed (Tasks 1–9).

- [ ] **Step 2: Build the dashboard locally**

```bash
cd dashboard && npm run build
```

Expected: build exits 0; `dashboard/dist/` is regenerated.

- [ ] **Step 3: Rsync changed backend + frontend source + built dist**

From the project root:

```bash
rsync -Rv \
  src/polybot/dashboard/api.py \
  tests/unit/test_dashboard_api.py \
  dashboard/src/index.css \
  dashboard/src/api.js \
  dashboard/src/lib/format.js \
  dashboard/src/components/domain/ExitCard.jsx \
  dashboard/src/components/domain/BuyExitPair.jsx \
  dashboard/src/pages/Alerts.jsx \
  dashboard/src/pages/Overview.jsx \
  dashboard/src/pages/WalletDetail.jsx \
  polybot:/root/polybot/
rsync -av --delete dashboard/dist/ polybot:/root/polybot/dashboard/dist/
```

Expected: ~10 source files transferred + dist tree synced.

- [ ] **Step 4: Restart the daemon**

```bash
ssh polybot 'systemctl restart polybot-bot.service && sleep 5 && systemctl is-active polybot-bot.service'
```

Expected: `active`.

- [ ] **Step 5: Probe the new endpoint**

```bash
ssh polybot 'curl -s --max-time 5 "http://127.0.0.1:8000/api/timeline?days=7" | python3 -c "import json,sys; d=json.load(sys.stdin); print(\"rows:\", len(d)); types={}; [types.setdefault(r[\"type\"], 0) or types.update({r[\"type\"]: types[r[\"type\"]]+1}) for r in d]; print(\"types:\", types)"'
```

Expected: a JSON array, with type counts printed. If there are no recent EXITs in the window, only `{"buy": N}` will appear — that's normal.

- [ ] **Step 6: Manual UI smoke**

Open the dashboard URL in a browser. Verify:

1. **Alerts page** — existing BUY cards render. The new `Type` filter pill row is present at the top of the filters. Selecting `EXIT` filters down to EXIT cards (or empty if no recent EXITs). Selecting `BUY` shows only BUYs. Existing filters (Composant, Période, Status, Catégorie) still work.
2. **Overview page** — KPI grid shows `Exits 7j` instead of `Coûts mois`. Recent-alerts feed mixes BUY and EXIT cards if any EXITs exist.
3. **Wallet detail page** — pick any wallet (e.g. one of the recently-active ones from the wallets page). The new "Timeline (BUY → EXIT)" section appears above "Trades récents". If the wallet has both an alert and a corresponding EXIT, they render as a paired card with the `↳` connector.
4. **Mobile viewport** (≤375 px in devtools) — `ExitCard` metrics row wraps; market title is not truncated.

- [ ] **Step 7: Done**

The feature is live.

---

## Self-review notes

**Spec coverage:** Each spec section maps to a task:

- `/api/timeline` endpoint → Task 1
- `accent-warning` theme token → Task 2
- `urls.timeline()` builder → Task 3
- `formatHeld` helper → Task 4
- `ExitCard` component → Task 5
- `BuyExitPair` component → Task 6
- `Alerts.jsx` Type filter + dual rendering → Task 7
- `Overview.jsx` KPI swap + dual feed → Task 8
- `WalletDetail.jsx` Timeline section → Task 9
- Deploy + manual smoke → Task 10

The 5 backend tests in the spec's Test plan are all in Task 1, Step 1.

**No placeholders:** every code block is complete; no "TBD"; no "Add validation"; no "similar to Task N" — Tasks 7 and 8 each carry their full file content because partial diffs in agent prompts are error-prone.

**Type/name consistency:** `r.type === "buy"` / `"exit"` is the discriminator everywhere. `r.id` is the row id everywhere. `r.created_at` is the timestamp everywhere. `original_alert_id` is the field everywhere on EXIT rows. `urls.timeline({ days, wallet })` is the only call form. `formatHeld(hours)` consistent across `ExitCard` and the spec.
