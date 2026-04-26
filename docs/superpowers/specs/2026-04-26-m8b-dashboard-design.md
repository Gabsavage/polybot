# M8-B Design — Dashboard Web (FastAPI + React)

## Overview

Read-only web dashboard for monitoring Polybot. FastAPI backend reads DuckDB, React SPA frontend served by Caddy with basic auth. Dark theme, data-dense, trading-terminal aesthetic.

## Architecture

```
Browser → Caddy (:3000, basicauth)
  ├── /api/* → reverse_proxy → uvicorn (:8000, 127.0.0.1 only)
  └── /* → static files (dashboard/dist/)

uvicorn reads DuckDB read-only (open/close per request)
daemon writes DuckDB (no conflict — different processes, short-lived reads)
```

Two systemd services: `polybot-bot.service` (existing daemon) + `polybot-dashboard.service` (new API). Frontend is static files, no service needed.

## Module — FastAPI Backend

File: `src/polybot/dashboard/api.py`

### DB Access

```python
import duckdb

def get_db():
    """Open read-only connection per request, close after."""
    con = duckdb.connect(str(settings.DUCKDB_PATH), read_only=True)
    try:
        yield con
    finally:
        con.close()
```

Uses FastAPI `Depends(get_db)`. Always read-only. Open/close per request to avoid locks with the daemon writer.

**Important**: The dashboard process is separate from the daemon — no shared-process DuckDB constraint. `read_only=True` is safe here because the daemon (separate process) holds write connections.

### Settings

Reuse `polybot.config.Settings` for `DUCKDB_PATH`. Add one optional setting:

```python
DASHBOARD_BASIC_AUTH_PASSWORD: str = ""  # bcrypt hash for Caddy basic auth
```

### Endpoints

#### `GET /api/status`

System health overview.

```sql
-- Uptime: read from daemon start time in indexer_state (proxy via last success)
-- Kill switches
SELECT target, enabled, reason, toggled_at FROM kill_switches WHERE enabled = TRUE

-- Rate limit counters
SELECT component, "window", count, window_start FROM rate_limit_counters

-- Indexer states
SELECT indexer_name, last_run_status, last_synced_at, last_run_duration_ms, ingested_count
FROM indexer_state ORDER BY indexer_name
```

Returns:
```json
{
  "kill_switches": [{"target": "c1", "enabled": true, "reason": "test", "toggled_at": "..."}],
  "rate_limits": [{"component": "c1", "window": "hourly", "count": 3, "window_start": "..."}],
  "indexers": [{"name": "markets_gamma", "status": "success", "last_synced_at": "...", "duration_ms": 123, "ingested_count": 46000}]
}
```

#### `GET /api/alerts?days=7&component=C1`

Alert history with outcomes.

```sql
SELECT
    a.alert_id, a.component, a.emitted_at, a.wallet_address, a.condition_id,
    a.side, a.size_usd, a.price, a.score, a.alignment_score,
    a.shadow_mode, a.features_passed,
    m.title as market_title, m.slug as market_slug,
    ao.resolution_outcome, ao.was_direction_correct, ao.shadow_pnl_simulated,
    ao.price_at_alert, ao.price_at_resolution
FROM alerts a
LEFT JOIN markets m ON a.condition_id = m.condition_id
LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
WHERE a.emitted_at >= CURRENT_DATE - INTERVAL '{days} DAY'
  AND (? IS NULL OR a.component = ?)
ORDER BY a.emitted_at DESC
LIMIT 200
```

Parameters: `days` (int, default 7), `component` (str, optional: "C1" or "C2").

#### `GET /api/wallets`

Tier A wallet metrics.

```sql
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
```

Also joins alert_outcomes for per-wallet win rate:
```sql
SELECT
    a.wallet_address,
    COUNT(*) FILTER (WHERE ao.resolution_outcome NOT IN ('PENDING')) as resolved,
    COUNT(*) FILTER (WHERE ao.was_direction_correct = TRUE) as correct,
    SUM(ao.shadow_pnl_simulated) FILTER (WHERE ao.resolution_outcome NOT IN ('PENDING')) as pnl
FROM alerts a
JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
WHERE a.wallet_address IN (SELECT address FROM tracked_wallets WHERE tier = 'A')
GROUP BY a.wallet_address
```

#### `GET /api/performance?days=30`

Shadow P&L and accuracy stats.

```sql
-- Daily P&L series for chart
SELECT
    DATE_TRUNC('day', a.emitted_at) as day,
    a.component,
    COUNT(*) FILTER (WHERE ao.resolution_outcome NOT IN ('PENDING')) as resolved,
    COUNT(*) FILTER (WHERE ao.was_direction_correct = TRUE) as correct,
    SUM(ao.shadow_pnl_simulated) FILTER (WHERE ao.resolution_outcome NOT IN ('PENDING')) as pnl
FROM alerts a
LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
WHERE a.emitted_at >= CURRENT_DATE - INTERVAL '{days} DAY'
GROUP BY day, a.component
ORDER BY day

-- Cumulative stats (all time)
SELECT
    component,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE ao.resolution_outcome IS NOT NULL AND ao.resolution_outcome != 'PENDING') as resolved,
    COUNT(*) FILTER (WHERE ao.was_direction_correct = TRUE) as correct,
    SUM(ao.shadow_pnl_simulated) FILTER (WHERE ao.resolution_outcome IS NOT NULL AND ao.resolution_outcome != 'PENDING') as pnl
FROM alerts a
LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
GROUP BY component

-- Alignment distribution
SELECT alignment_score, COUNT(*)
FROM alerts WHERE alignment_score IS NOT NULL
GROUP BY alignment_score
```

#### `GET /api/markets/hot`

Current C2 hot markets (last scan results).

```sql
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
```

#### `GET /api/audit?limit=50`

Audit log events.

```sql
SELECT id, event_type, target, action, reason, actor, created_at
FROM audit_log
ORDER BY created_at DESC
LIMIT ?
```

#### `GET /api/costs`

Cost estimation.

```sql
-- LLM calls this month
SELECT COUNT(*) FROM resolution_risk_cache
WHERE computed_at >= DATE_TRUNC('month', CURRENT_DATE)
```

Returns:
```json
{
  "llm_calls_month": 142,
  "llm_cost_estimate": 0.14,
  "vps_monthly": 4.0
}
```

#### `GET /api/c2/features?condition_id=...`

C2 feature detail for a specific market (for alert drill-down).

```sql
SELECT
    a.alert_id, a.score, a.features_passed, a.momentum_4h,
    a.side, a.size_usd, a.emitted_at,
    ao.resolution_outcome, ao.was_direction_correct, ao.shadow_pnl_simulated
FROM alerts a
LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
WHERE a.condition_id = ? AND a.component = 'C2'
ORDER BY a.emitted_at DESC
```

### Launch

```bash
uvicorn polybot.dashboard.api:app --host 127.0.0.1 --port 8000
```

Systemd service file: `deploy/polybot-dashboard.service`

## Module — React Frontend

Directory: `dashboard/` at project root.

### Tech Stack

- React 19 + Vite
- Tailwind CSS v4
- Recharts for charts
- Fetch API (no axios)

### Design System

Dark theme, trading-terminal aesthetic:
- Background: `#0a0a0f` (near-black)
- Card background: `#12121a`
- Border: `#1e1e2e`
- Text primary: `#e4e4e7` (zinc-200)
- Text secondary: `#71717a` (zinc-500)
- Accent: `#06b6d4` (cyan-500)
- Positive: `#22c55e` (green-500)
- Negative: `#ef4444` (red-500)
- Warning: `#f59e0b` (amber-500)
- Font: `JetBrains Mono` for numbers, system sans for labels

### Pages

#### 1. Overview (route: `/`)

- Header: "POLYBOT" + status dot (green if all indexers ok, red otherwise) + last sync time
- 4 KPI cards in a grid:
  - Alertes 24h (count)
  - Shadow P&L cumulé (with +/- color)
  - Win Rate % (with color: green >55%, amber 45-55%, red <45%)
  - Wallets Tier A actifs (active/total)
- Alerts sparkline: alerts per day, last 7 days (area chart, cyan)
- P&L sparkline: cumulative shadow P&L, last 30 days (line chart, green/red)
- Indexers table: name, status dot, last sync, duration, ingested count
- Kill switches: only shown if any active (red banner)
- Costs: LLM month-to-date, VPS

#### 2. Alerts (route: `/alerts`)

- Filter bar: component toggle (All/C1/C2), date range (7d/30d/All)
- Table columns: date, component, market, side, size, price, score, alignment, status
- Status color: green (correct), red (incorrect), gray (pending)
- Row click expands detail panel: C2 features, risk score, P&L outcome
- Pagination: 50 per page

#### 3. Wallets (route: `/wallets`)

- Table: address (truncated), name, tier, confidence, trades (total/7d), win rate, P&L, last trade
- Sortable columns (click header)
- Row highlighting: yellow if inactive >7d, red+strikethrough if `active=false`
- No drill-down in v1

#### 4. Performance (route: `/performance`)

- Main chart: cumulative shadow P&L over time (line chart)
- Component breakdown: C1 vs C2 lines on same chart
- Stats cards: total alerts, resolved, pending, correct %, incorrect %
- Alignment bar chart: distribution of +1/0/-1 scores
- Warning banner if resolved < 30

#### 5. System (route: `/system`)

- Audit log table: scrollable, 50 most recent events
- Indexer detail cards: last 5 statuses with timestamps
- Rate limit counters: current state per component
- Kill switches: full list with toggle timestamps and reasons

### Routing

React Router with 5 routes. Sidebar navigation on desktop, bottom tab bar on mobile.

### Data Fetching

Custom `useFetch(url)` hook with:
- Loading state
- Error state with retry button
- Auto-refresh every 60s for Overview page
- No auto-refresh on other pages (manual refresh button)

### Responsive

- Desktop: sidebar + main content
- Tablet: collapsed sidebar
- Mobile: bottom tabs, tables scroll horizontally, cards stack vertically
- Breakpoints: `sm:640px`, `md:768px`, `lg:1024px`

### Build

```bash
cd dashboard
npm install
npm run build  # output → dashboard/dist/
```

Build locally, rsync `dist/` to VPS. No Node.js on VPS.

## Deploy Config

### Caddy

File: `deploy/Caddyfile`

```
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

Password bcrypt hash stored in env var `DASHBOARD_BCRYPT_HASH` on VPS.

### Systemd Service

File: `deploy/polybot-dashboard.service`

```ini
[Unit]
Description=Polybot Dashboard API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/polybot
Environment=PYTHONPATH=/root/polybot/src
EnvironmentFile=/root/polybot/.env
ExecStart=/root/polybot/.venv/bin/uvicorn polybot.dashboard.api:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Deploy Steps

1. Build frontend locally: `cd dashboard && npm run build`
2. Rsync everything: `rsync -avz --exclude node_modules --exclude .git . polybot:/root/polybot/`
3. Install Python deps on VPS: `ssh polybot "cd /root/polybot && uv sync"`
4. Install Caddy: `ssh polybot "apt install -y caddy"`
5. Copy Caddyfile: `ssh polybot "cp /root/polybot/deploy/Caddyfile /etc/caddy/Caddyfile"`
6. Set bcrypt hash env: `ssh polybot "echo 'DASHBOARD_BCRYPT_HASH=...' >> /root/polybot/.env"`
7. Copy systemd service: `ssh polybot "cp /root/polybot/deploy/polybot-dashboard.service /etc/systemd/system/ && systemctl daemon-reload"`
8. Start services: `ssh polybot "systemctl enable --now polybot-dashboard caddy"`
9. Open firewall port: `ssh polybot "ufw allow 3000/tcp"`
10. Test: `curl -u polybot:password http://<vps_ip>:3000/api/status`

## Dependencies

### Backend (add to pyproject.toml)

```toml
"fastapi>=0.115",
"uvicorn[standard]>=0.30",
```

### Frontend (dashboard/package.json)

```json
{
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

## Tests (6 backend)

1. **GET /api/status**: mock DB with indexers + kill switches → JSON with all fields
2. **GET /api/alerts**: 3 alerts in DB → returns 3, with outcomes joined
3. **GET /api/alerts?component=C1**: filter → returns only C1 alerts
4. **GET /api/wallets**: 5 tracked wallets → returns 5 with computed metrics
5. **GET /api/performance**: alerts + outcomes → correct P&L series
6. **GET /api/costs**: 50 cache entries this month → `{"llm_cost_estimate": 0.05}`

Test pattern: create temp DuckDB in `/tmp`, insert test data, override `get_db` dependency, use `TestClient`.

Frontend: manual verification only in v1.

## What NOT to do

- Do not expose API on 0.0.0.0 (127.0.0.1 only, Caddy reverse proxies)
- Do not allow writes via API (all queries read-only)
- Do not use MUI, Ant Design, or other heavy UI frameworks
- Do not store basic auth password in cleartext in Caddyfile (use env var)
- Do not modify the daemon, indexers, or components
- Do not create migrations (dashboard reads existing tables)
- Do not install Node.js on VPS (build locally, rsync dist/)
