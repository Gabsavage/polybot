# M8-A Design — Kill Switches, Rate Limits, Circuit Breakers, Audit Log

## Overview

Add an orchestration layer to the unified daemon: guard-rails that make the bot robust before going live. Four modules in `src/polybot/orchestrator/`, plus a migration to clean up the existing empty tables.

## Migration 007

DROP and recreate three tables (currently empty):

```sql
DROP TABLE IF EXISTS kill_switches;
CREATE TABLE kill_switches (
    target       VARCHAR PRIMARY KEY,
    enabled      BOOLEAN DEFAULT FALSE,
    reason       VARCHAR,
    toggled_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    toggled_by   VARCHAR DEFAULT 'manual'
);

DROP TABLE IF EXISTS rate_limit_counters;
CREATE TABLE rate_limit_counters (
    component    VARCHAR,
    window       VARCHAR,
    count        INTEGER DEFAULT 0,
    window_start TIMESTAMP,
    PRIMARY KEY (component, window)
);

DROP SEQUENCE IF EXISTS audit_log_seq;
DROP TABLE IF EXISTS audit_log;
CREATE SEQUENCE audit_log_seq START 1;
CREATE TABLE audit_log (
    id           BIGINT DEFAULT nextval('audit_log_seq') PRIMARY KEY,
    event_type   VARCHAR,
    target       VARCHAR,
    action       VARCHAR,
    reason       VARCHAR,
    actor        VARCHAR DEFAULT 'system',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Module 1 — Kill Switches

File: `src/polybot/orchestrator/kill_switches.py`

### Targets

| Target | Effect |
|--------|--------|
| `c1` | Stop C1 alert emission (trades indexer continues) |
| `c2` | Stop C2 alert emission (scan continues) |
| `c3` | Stop LLM scoring (rules-only fallback) |
| `all_alerts` | Mute C1 + C2 (indexers continue) |
| `trades` | Skip trades indexer runs |
| `markets` | Skip markets indexer runs |
| `onchain` | Skip onchain indexer runs |
| `resolutions` | Skip resolutions indexer runs |

### API

```python
def is_component_enabled(db_path: str, component: str) -> bool:
    """Returns True if component can operate.
    Checks both the specific target and 'all_alerts' (for c1/c2)."""

def set_kill_switch(db_path: str, target: str, enabled: bool,
                    reason: str = None, actor: str = 'manual'):
    """Toggle switch in DB, invalidate cache, log to audit_log."""
```

### Cache

Module-level dict `_cache` with 10s TTL. On read: if cache age > 10s, reload all active switches from DB in one query. Avoids a DB read on every C1/C2 cycle.

### Integration

- C1: check before `send_alert()` in `_process_trade()`
- C2: check before `send_alert()` in `_emit_telegram()`
- C3: check before LLM call in `score_market()` — if killed, return rules-only score
- Indexers: check at top of `run_scheduled_indexer` loop — if killed, skip and sleep

## Module 2 — Rate Limits

File: `src/polybot/orchestrator/rate_limits.py`

### Limits

| Component | Max/hour | Max/day |
|-----------|----------|---------|
| `c1` | 10 | 40 |
| `c2` | 2 | 5 |
| `risk` | 20 | 100 |
| `llm` | 50 | 200 |

### API

```python
def check_rate_limit(db_path: str, component: str) -> bool:
    """Returns True if under limit. Resets stale windows automatically."""

def increment_counter(db_path: str, component: str):
    """Increment both hourly and daily counters."""
```

### Window logic

Each (component, window) row has a `window_start` timestamp. On check: if window_start is older than 1h (hourly) or 24h (daily), reset count to 0 and update window_start.

### Exceeded behavior

- C1/C2: skip alert, log warning, send one digest to #ops per window (module-level `_digest_sent` set)
- `/risk`: reply with "Rate limit atteint" + minutes until reset
- LLM: activate kill switch `c3` + warn #errors

### Replaces

- C2's hardcoded hourly/daily check moves to centralized limiter
- C1's `_check_rate_limit()` stays (it's a per-wallet dedup, different concern)

## Module 3 — Circuit Breakers

File: `src/polybot/orchestrator/circuit_breakers.py`

### Triggers

| Trigger | Action |
|---------|--------|
| Indexer fail >= 3 consecutive runs | Activate kill switch for that indexer + alert #errors |
| LLM cost > $3/month estimated | Activate kill switch `c3` + warn #errors |
| Disk usage > 80% | Alert #errors (warn only, no kill) |

### Implementation

```python
class CircuitBreaker:
    def __init__(self, db_path, bot=None):
        self._indexer_failures: dict[str, int] = {}  # in-memory

    def check_indexer_health(self): ...
    def check_llm_cost(self): ...
    def check_disk_usage(self): ...

    async def run_forever(self):
        """Check all triggers every 5 min."""
```

### Consecutive failure tracking

In-memory dict, reset on restart. Reads `indexer_state.last_run_status`: if `failed`, increment; if `success`, reset to 0. Threshold: 3 consecutive failures.

### LLM cost estimation

Count `resolution_risk_cache` entries this month x $0.001/call.

### Daemon integration

Added to `asyncio.gather()` alongside existing coroutines.

## Module 4 — Audit Log

File: `src/polybot/orchestrator/audit_log.py`

### API

```python
def log_audit(db_path: str, event_type: str, target: str, action: str,
              reason: str = None, actor: str = 'system'):
    """Insert into audit_log via db_write_with_retry."""
```

### Events logged

- Kill switch activated/deactivated
- Rate limit exceeded
- Circuit breaker triggered
- Config changes (bankroll, thresholds)
- Wallet added/removed/demoted

## Bot Commands

### `/toggle` extension

```
/toggle shadow           — flip shadow mode (existing)
/toggle c1 off [reason]  — activate kill switch
/toggle c2 on            — deactivate kill switch
/toggle all_alerts off maintenance
/toggle trades off
```

Valid targets: `c1`, `c2`, `c3`, `all_alerts`, `trades`, `markets`, `onchain`, `resolutions`.

On toggle: update DB, log audit, notify #ops.

### `/audit [N]` (new)

Show last N audit events (default 10). Formatted with icons per event_type.

## Tests (12)

1. Kill switch on/off: activate c1 -> `is_component_enabled('c1')` returns False
2. Kill switch all_alerts: activate -> c1 and c2 both disabled
3. Kill switch cache TTL: activate, verify 10s cache behavior
4. Rate limit under: 5 calls on limit 10/h -> check returns True
5. Rate limit exceeded: 11 calls on limit 10/h -> check returns False
6. Rate limit window reset: exceed, advance clock 1h -> resets
7. Circuit breaker indexer: 3 consecutive failures -> kill switch ON
8. Circuit breaker LLM cost: simulate 4000 calls -> cost > $3 -> c3 off
9. Circuit breaker disk: mock statvfs > 80% -> warning
10. Audit log: toggle c1 -> entry in audit_log
11. /toggle command: mock Telegram -> response + DB updated
12. /audit command: mock DB with 5 events -> formatted output

## What NOT to do

- Do not implement Streamlit dashboard (M8-B)
- Do not implement weekly report (M8-C)
- Do not modify C1/C2/C3 internal logic (only add guard checks)
- Do not remove `/toggle shadow` (it stays as a special case)
- Do not deploy to VPS
