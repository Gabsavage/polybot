# M8-A Orchestration Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add kill switches, rate limits, circuit breakers, and audit log to the unified daemon so the bot is robust before going live.

**Architecture:** Four standalone modules in `src/polybot/orchestrator/` with pure functions. C1/C2/C3/indexers import and call them directly. Circuit breaker is an async loop in `asyncio.gather`. Migration 007 recreates three empty tables with the correct schema.

**Tech Stack:** DuckDB, structlog, python-telegram-bot, asyncio

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `migrations/007_m8a_orchestration_tables.sql` | DROP+recreate kill_switches, rate_limit_counters, audit_log |
| Create | `src/polybot/orchestrator/__init__.py` | Package init |
| Create | `src/polybot/orchestrator/audit_log.py` | `log_audit()` function |
| Create | `src/polybot/orchestrator/kill_switches.py` | `is_component_enabled()`, `set_kill_switch()` with cache |
| Create | `src/polybot/orchestrator/rate_limits.py` | `check_rate_limit()`, `increment_counter()` |
| Create | `src/polybot/orchestrator/circuit_breakers.py` | `CircuitBreaker` class with `run_forever()` |
| Modify | `src/polybot/telegram/bot.py` | Extend `/toggle`, add `/audit` command |
| Modify | `src/polybot/components/c1_sharp_money.py` | Add kill switch + rate limit check before alert |
| Modify | `src/polybot/components/c2_informed_trading.py` | Add kill switch check, replace hardcoded rate limit |
| Modify | `src/polybot/components/c3_resolution_risk.py` | Add kill switch check before LLM call |
| Modify | `src/polybot/daemon.py` | Add circuit breaker to gather, add kill switch to indexer loop |
| Create | `tests/unit/test_kill_switches.py` | Tests 1-3 |
| Create | `tests/unit/test_rate_limits.py` | Tests 4-6 |
| Create | `tests/unit/test_circuit_breakers.py` | Tests 7-9 |
| Create | `tests/unit/test_audit_log.py` | Test 10 |
| Create | `tests/unit/test_toggle_audit_commands.py` | Tests 11-12 |

---

### Task 1: Migration 007

**Files:**
- Create: `migrations/007_m8a_orchestration_tables.sql`

- [ ] **Step 1: Write migration SQL**

```sql
-- M8-A: Recreate orchestration tables with correct schema
-- (existing tables are empty, safe to DROP)

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

- [ ] **Step 2: Verify migration applies locally**

Run: `PYTHONPATH=src uv run python -c "from polybot.db.migrations import apply_migrations; print(apply_migrations('data/pm.duckdb', 'migrations'))"`

Expected: `['007_m8a_orchestration_tables.sql']`

- [ ] **Step 3: Verify tables exist with correct schema**

Run: `PYTHONPATH=src uv run python -c "import duckdb; con=duckdb.connect('data/pm.duckdb'); print(con.execute('DESCRIBE kill_switches').fetchall()); print(con.execute('DESCRIBE rate_limit_counters').fetchall()); print(con.execute('DESCRIBE audit_log').fetchall()); con.close()"`

Expected: Column names match spec (target/enabled/reason/toggled_at/toggled_by for kill_switches, etc.)

- [ ] **Step 4: Commit**

```bash
git add migrations/007_m8a_orchestration_tables.sql
git commit -m "feat(M8): migration 007 — orchestration tables (kill_switches, rate_limits, audit_log)"
```

---

### Task 2: Audit Log Module

**Files:**
- Create: `src/polybot/orchestrator/__init__.py`
- Create: `src/polybot/orchestrator/audit_log.py`
- Create: `tests/unit/test_audit_log.py`

- [ ] **Step 1: Create package init**

Create `src/polybot/orchestrator/__init__.py` as an empty file.

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_audit_log.py`:

```python
"""Tests for audit log module."""

import duckdb
import pytest

from polybot.orchestrator.audit_log import log_audit


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("CREATE SEQUENCE audit_log_seq START 1")
    con.execute("""
        CREATE TABLE audit_log (
            id BIGINT DEFAULT nextval('audit_log_seq') PRIMARY KEY,
            event_type VARCHAR,
            target VARCHAR,
            action VARCHAR,
            reason VARCHAR,
            actor VARCHAR DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.close()
    return path


class TestLogAudit:
    def test_inserts_event(self, db_path):
        log_audit(db_path, "kill_switch", "c1", "on", reason="maintenance", actor="manual")

        con = duckdb.connect(db_path)
        rows = con.execute("SELECT event_type, target, action, reason, actor FROM audit_log").fetchall()
        con.close()

        assert len(rows) == 1
        assert rows[0] == ("kill_switch", "c1", "on", "maintenance", "manual")

    def test_default_actor_is_system(self, db_path):
        log_audit(db_path, "rate_limit", "c2", "exceeded")

        con = duckdb.connect(db_path)
        row = con.execute("SELECT actor FROM audit_log").fetchone()
        con.close()

        assert row[0] == "system"

    def test_multiple_events_get_sequential_ids(self, db_path):
        log_audit(db_path, "kill_switch", "c1", "on")
        log_audit(db_path, "kill_switch", "c1", "off")

        con = duckdb.connect(db_path)
        ids = [r[0] for r in con.execute("SELECT id FROM audit_log ORDER BY id").fetchall()]
        con.close()

        assert ids == [1, 2]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_audit_log.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'polybot.orchestrator'`

- [ ] **Step 4: Write implementation**

Create `src/polybot/orchestrator/audit_log.py`:

```python
"""Audit log — persistent record of system events."""

import structlog

from polybot.db.connection import db_write_with_retry

logger = structlog.get_logger()


def log_audit(
    db_path: str,
    event_type: str,
    target: str,
    action: str,
    reason: str = None,
    actor: str = "system",
) -> None:
    """Insert an event into the audit_log table."""
    def _do(con):
        con.execute(
            "INSERT INTO audit_log (event_type, target, action, reason, actor) "
            "VALUES (?, ?, ?, ?, ?)",
            [event_type, target, action, reason, actor],
        )

    db_write_with_retry(db_path, _do)
    logger.info("audit_logged", event_type=event_type, target=target, action=action)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_audit_log.py -v`

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/polybot/orchestrator/__init__.py src/polybot/orchestrator/audit_log.py tests/unit/test_audit_log.py
git commit -m "feat(M8): audit_log module with log_audit()"
```

---

### Task 3: Kill Switches Module

**Files:**
- Create: `src/polybot/orchestrator/kill_switches.py`
- Create: `tests/unit/test_kill_switches.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_kill_switches.py`:

```python
"""Tests for kill switches module."""

import time
from unittest.mock import patch

import duckdb
import pytest

from polybot.orchestrator.kill_switches import (
    is_component_enabled,
    set_kill_switch,
    _invalidate_cache,
)


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("""
        CREATE TABLE kill_switches (
            target VARCHAR PRIMARY KEY,
            enabled BOOLEAN DEFAULT FALSE,
            reason VARCHAR,
            toggled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            toggled_by VARCHAR DEFAULT 'manual'
        )
    """)
    con.execute("CREATE SEQUENCE audit_log_seq START 1")
    con.execute("""
        CREATE TABLE audit_log (
            id BIGINT DEFAULT nextval('audit_log_seq') PRIMARY KEY,
            event_type VARCHAR, target VARCHAR, action VARCHAR,
            reason VARCHAR, actor VARCHAR DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.close()
    _invalidate_cache()
    return path


class TestKillSwitchOnOff:
    def test_component_enabled_by_default(self, db_path):
        assert is_component_enabled(db_path, "c1") is True

    def test_activate_disables_component(self, db_path):
        set_kill_switch(db_path, "c1", enabled=True, reason="test")
        assert is_component_enabled(db_path, "c1") is False

    def test_deactivate_re_enables_component(self, db_path):
        set_kill_switch(db_path, "c1", enabled=True)
        set_kill_switch(db_path, "c1", enabled=False)
        assert is_component_enabled(db_path, "c1") is True


class TestKillSwitchAllAlerts:
    def test_all_alerts_disables_c1_and_c2(self, db_path):
        set_kill_switch(db_path, "all_alerts", enabled=True)
        assert is_component_enabled(db_path, "c1") is False
        assert is_component_enabled(db_path, "c2") is False

    def test_all_alerts_does_not_affect_indexers(self, db_path):
        set_kill_switch(db_path, "all_alerts", enabled=True)
        assert is_component_enabled(db_path, "trades") is True


class TestKillSwitchCache:
    def test_cache_avoids_repeated_db_reads(self, db_path):
        is_component_enabled(db_path, "c1")
        # Insert directly into DB — cache should NOT see it within TTL
        con = duckdb.connect(db_path)
        con.execute("INSERT INTO kill_switches (target, enabled) VALUES ('c1', TRUE)")
        con.close()
        # Within TTL, still returns True (cached)
        assert is_component_enabled(db_path, "c1") is True

    def test_cache_refreshes_after_ttl(self, db_path):
        is_component_enabled(db_path, "c1")
        con = duckdb.connect(db_path)
        con.execute("INSERT INTO kill_switches (target, enabled) VALUES ('c1', TRUE)")
        con.close()
        # Force cache expiry
        _invalidate_cache()
        assert is_component_enabled(db_path, "c1") is False


class TestKillSwitchAuditIntegration:
    def test_set_kill_switch_logs_to_audit(self, db_path):
        set_kill_switch(db_path, "c1", enabled=True, reason="maintenance", actor="manual")
        con = duckdb.connect(db_path)
        row = con.execute(
            "SELECT event_type, target, action, reason, actor FROM audit_log"
        ).fetchone()
        con.close()
        assert row == ("kill_switch", "c1", "on", "maintenance", "manual")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_kill_switches.py -v`

Expected: FAIL — `ImportError`

- [ ] **Step 3: Write implementation**

Create `src/polybot/orchestrator/kill_switches.py`:

```python
"""Kill switches — disable components without restarting the daemon."""

import time

import structlog

from polybot.db.connection import db_read_with_retry, db_write_with_retry
from polybot.orchestrator.audit_log import log_audit

logger = structlog.get_logger()

VALID_TARGETS = frozenset({
    "c1", "c2", "c3", "all_alerts",
    "trades", "markets", "onchain", "resolutions",
})

ALERT_COMPONENTS = frozenset({"c1", "c2"})

_cache: set[str] = set()
_cache_time: float = 0.0
_CACHE_TTL = 10.0


def _invalidate_cache() -> None:
    global _cache, _cache_time
    _cache = set()
    _cache_time = 0.0


def _refresh_cache(db_path: str) -> None:
    global _cache, _cache_time

    now = time.monotonic()
    if now - _cache_time < _CACHE_TTL:
        return

    def _read(con):
        rows = con.execute(
            "SELECT target FROM kill_switches WHERE enabled = TRUE"
        ).fetchall()
        return {r[0] for r in rows}

    _cache = db_read_with_retry(db_path, _read)
    _cache_time = time.monotonic()


def is_component_enabled(db_path: str, component: str) -> bool:
    """Returns True if the component can operate.

    For alert components (c1, c2), also checks 'all_alerts'.
    """
    _refresh_cache(db_path)

    if component in _cache:
        return False
    if component in ALERT_COMPONENTS and "all_alerts" in _cache:
        return False
    return True


def set_kill_switch(
    db_path: str,
    target: str,
    enabled: bool,
    reason: str = None,
    actor: str = "manual",
) -> None:
    """Toggle a kill switch. Persists to DB, invalidates cache, logs to audit."""
    if target not in VALID_TARGETS:
        raise ValueError(f"Invalid kill switch target: {target}")

    def _do(con):
        con.execute(
            "INSERT INTO kill_switches (target, enabled, reason, toggled_at, toggled_by) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?) "
            "ON CONFLICT (target) DO UPDATE SET "
            "enabled = EXCLUDED.enabled, reason = EXCLUDED.reason, "
            "toggled_at = EXCLUDED.toggled_at, toggled_by = EXCLUDED.toggled_by",
            [target, enabled, reason, actor],
        )

    db_write_with_retry(db_path, _do)
    _invalidate_cache()

    action = "on" if enabled else "off"
    log_audit(db_path, "kill_switch", target, action, reason=reason, actor=actor)
    logger.info("kill_switch_set", target=target, enabled=enabled, reason=reason, actor=actor)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_kill_switches.py -v`

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/polybot/orchestrator/kill_switches.py tests/unit/test_kill_switches.py
git commit -m "feat(M8): kill_switches module with cache TTL"
```

---

### Task 4: Rate Limits Module

**Files:**
- Create: `src/polybot/orchestrator/rate_limits.py`
- Create: `tests/unit/test_rate_limits.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_rate_limits.py`:

```python
"""Tests for rate limits module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import duckdb
import pytest

from polybot.orchestrator.rate_limits import check_rate_limit, increment_counter


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("""
        CREATE TABLE rate_limit_counters (
            component VARCHAR,
            window VARCHAR,
            count INTEGER DEFAULT 0,
            window_start TIMESTAMP,
            PRIMARY KEY (component, window)
        )
    """)
    con.close()
    return path


class TestRateLimitUnder:
    def test_first_call_is_under_limit(self, db_path):
        assert check_rate_limit(db_path, "c1") is True

    def test_five_calls_under_hourly_ten(self, db_path):
        for _ in range(5):
            increment_counter(db_path, "c1")
        assert check_rate_limit(db_path, "c1") is True


class TestRateLimitExceeded:
    def test_hourly_limit_exceeded(self, db_path):
        for _ in range(10):
            increment_counter(db_path, "c1")
        assert check_rate_limit(db_path, "c1") is False

    def test_daily_limit_exceeded(self, db_path):
        # c2 has daily limit of 5
        for _ in range(5):
            increment_counter(db_path, "c2")
        assert check_rate_limit(db_path, "c2") is False


class TestRateLimitWindowReset:
    def test_hourly_window_resets_after_one_hour(self, db_path):
        for _ in range(10):
            increment_counter(db_path, "c1")
        assert check_rate_limit(db_path, "c1") is False

        # Move window_start back 2 hours so it looks stale
        con = duckdb.connect(db_path)
        con.execute(
            "UPDATE rate_limit_counters SET window_start = window_start - INTERVAL 2 HOUR "
            "WHERE component = 'c1' AND window = 'hourly'"
        )
        con.close()

        assert check_rate_limit(db_path, "c1") is True

    def test_daily_window_resets_after_24h(self, db_path):
        for _ in range(5):
            increment_counter(db_path, "c2")
        assert check_rate_limit(db_path, "c2") is False

        con = duckdb.connect(db_path)
        con.execute(
            "UPDATE rate_limit_counters SET window_start = window_start - INTERVAL 25 HOUR "
            "WHERE component = 'c2' AND window = 'daily'"
        )
        con.close()

        assert check_rate_limit(db_path, "c2") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_rate_limits.py -v`

Expected: FAIL — `ImportError`

- [ ] **Step 3: Write implementation**

Create `src/polybot/orchestrator/rate_limits.py`:

```python
"""Rate limits — throttle alert emission and API calls."""

from datetime import datetime, timedelta, timezone

import structlog

from polybot.db.connection import db_read_with_retry, db_write_with_retry

logger = structlog.get_logger()

LIMITS: dict[str, dict[str, int]] = {
    "c1":   {"hourly": 10, "daily": 40},
    "c2":   {"hourly": 2,  "daily": 5},
    "risk": {"hourly": 20, "daily": 100},
    "llm":  {"hourly": 50, "daily": 200},
}

WINDOW_DURATIONS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(hours=24),
}

_digest_sent: set[tuple[str, str]] = set()


def check_rate_limit(db_path: str, component: str) -> bool:
    """Returns True if the component is under both hourly and daily limits."""
    limits = LIMITS.get(component)
    if not limits:
        return True

    now = datetime.now(timezone.utc)

    def _check(con):
        for window, max_count in limits.items():
            duration = WINDOW_DURATIONS[window]
            row = con.execute(
                "SELECT count, window_start FROM rate_limit_counters "
                "WHERE component = ? AND window = ?",
                [component, window],
            ).fetchone()

            if row is None:
                continue

            count, window_start = row
            if window_start.tzinfo is None:
                window_start = window_start.replace(tzinfo=timezone.utc)

            if now - window_start > duration:
                con.execute(
                    "UPDATE rate_limit_counters SET count = 0, window_start = ? "
                    "WHERE component = ? AND window = ?",
                    [now, component, window],
                )
                continue

            if count >= max_count:
                return False
        return True

    return db_read_with_retry(db_path, _check)


def increment_counter(db_path: str, component: str) -> None:
    """Increment both hourly and daily counters for this component."""
    now = datetime.now(timezone.utc)

    def _do(con):
        for window in ("hourly", "daily"):
            row = con.execute(
                "SELECT count, window_start FROM rate_limit_counters "
                "WHERE component = ? AND window = ?",
                [component, window],
            ).fetchone()

            if row is None:
                con.execute(
                    "INSERT INTO rate_limit_counters (component, window, count, window_start) "
                    "VALUES (?, ?, 1, ?)",
                    [component, window, now],
                )
            else:
                count, window_start = row
                if window_start.tzinfo is None:
                    window_start = window_start.replace(tzinfo=timezone.utc)
                duration = WINDOW_DURATIONS[window]
                if now - window_start > duration:
                    con.execute(
                        "UPDATE rate_limit_counters SET count = 1, window_start = ? "
                        "WHERE component = ? AND window = ?",
                        [now, component, window],
                    )
                else:
                    con.execute(
                        "UPDATE rate_limit_counters SET count = count + 1 "
                        "WHERE component = ? AND window = ?",
                        [component, window],
                    )

    db_write_with_retry(db_path, _do)


def clear_digest_sent() -> None:
    """Reset digest tracking (called at window boundaries or for testing)."""
    _digest_sent.clear()


def mark_digest_sent(component: str, window: str) -> bool:
    """Mark that a digest was sent for this window. Returns True if already sent."""
    key = (component, window)
    if key in _digest_sent:
        return True
    _digest_sent.add(key)
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_rate_limits.py -v`

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/polybot/orchestrator/rate_limits.py tests/unit/test_rate_limits.py
git commit -m "feat(M8): rate_limits module with window reset logic"
```

---

### Task 5: Circuit Breakers Module

**Files:**
- Create: `src/polybot/orchestrator/circuit_breakers.py`
- Create: `tests/unit/test_circuit_breakers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_circuit_breakers.py`:

```python
"""Tests for circuit breakers module."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import duckdb
import pytest

from polybot.orchestrator.circuit_breakers import CircuitBreaker


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("""
        CREATE TABLE indexer_state (
            indexer_name VARCHAR PRIMARY KEY,
            last_synced_at TIMESTAMP,
            last_block_number BIGINT,
            last_cursor VARCHAR,
            last_run_status VARCHAR CHECK (last_run_status IN ('success', 'failed', 'running')),
            last_run_duration_ms INTEGER,
            last_error VARCHAR,
            ingested_count BIGINT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE kill_switches (
            target VARCHAR PRIMARY KEY,
            enabled BOOLEAN DEFAULT FALSE,
            reason VARCHAR,
            toggled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            toggled_by VARCHAR DEFAULT 'manual'
        )
    """)
    con.execute("CREATE SEQUENCE audit_log_seq START 1")
    con.execute("""
        CREATE TABLE audit_log (
            id BIGINT DEFAULT nextval('audit_log_seq') PRIMARY KEY,
            event_type VARCHAR, target VARCHAR, action VARCHAR,
            reason VARCHAR, actor VARCHAR DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE resolution_risk_cache (
            condition_id VARCHAR PRIMARY KEY,
            ambiguity_score DOUBLE,
            reasons JSON,
            red_flags JSON,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.close()
    return path


class TestCircuitBreakerIndexer:
    def test_three_consecutive_failures_triggers_kill_switch(self, db_path):
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO indexer_state (indexer_name, last_synced_at, last_run_status) "
            "VALUES ('onchain_alchemy', CURRENT_TIMESTAMP, 'failed')"
        )
        con.close()

        cb = CircuitBreaker(db_path)
        # Simulate 3 consecutive checks seeing 'failed'
        cb.check_indexer_health()
        cb.check_indexer_health()
        cb.check_indexer_health()

        from polybot.orchestrator.kill_switches import is_component_enabled, _invalidate_cache
        _invalidate_cache()
        assert is_component_enabled(db_path, "onchain") is False

    def test_success_resets_failure_count(self, db_path):
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO indexer_state (indexer_name, last_synced_at, last_run_status) "
            "VALUES ('onchain_alchemy', CURRENT_TIMESTAMP, 'failed')"
        )
        con.close()

        cb = CircuitBreaker(db_path)
        cb.check_indexer_health()
        cb.check_indexer_health()

        # Now flip to success
        con = duckdb.connect(db_path)
        con.execute("UPDATE indexer_state SET last_run_status = 'success' WHERE indexer_name = 'onchain_alchemy'")
        con.close()

        cb.check_indexer_health()
        assert cb._indexer_failures.get("onchain_alchemy", 0) == 0


class TestCircuitBreakerLLMCost:
    def test_high_cost_triggers_c3_kill(self, db_path):
        con = duckdb.connect(db_path)
        for i in range(3500):
            con.execute(
                "INSERT INTO resolution_risk_cache (condition_id, ambiguity_score, computed_at) "
                "VALUES (?, 0.5, CURRENT_TIMESTAMP)",
                [f"cond_{i}"],
            )
        con.close()

        cb = CircuitBreaker(db_path)
        cb.check_llm_cost()

        from polybot.orchestrator.kill_switches import is_component_enabled, _invalidate_cache
        _invalidate_cache()
        assert is_component_enabled(db_path, "c3") is False


class TestCircuitBreakerDisk:
    def test_high_disk_usage_logs_warning(self, db_path):
        mock_stat = MagicMock()
        mock_stat.f_blocks = 1000
        mock_stat.f_bavail = 100  # 90% used

        cb = CircuitBreaker(db_path)
        with patch("os.statvfs", return_value=mock_stat):
            cb.check_disk_usage()

        assert cb._disk_warning_sent is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_circuit_breakers.py -v`

Expected: FAIL — `ImportError`

- [ ] **Step 3: Write implementation**

Create `src/polybot/orchestrator/circuit_breakers.py`:

```python
"""Circuit breakers — automatic safeguards based on system health."""

import asyncio
import os

import structlog

from polybot.db.connection import db_read_with_retry
from polybot.orchestrator.audit_log import log_audit
from polybot.orchestrator.kill_switches import set_kill_switch, is_component_enabled, _invalidate_cache

logger = structlog.get_logger()

INDEXER_NAME_TO_TARGET = {
    "onchain_alchemy": "onchain",
    "resolutions_uma": "resolutions",
    "markets_gamma": "markets",
    "proxy_factory": "markets",
    "trades_dataapi": "trades",
}

FAILURE_THRESHOLD = 3
LLM_COST_PER_CALL = 0.001
LLM_MONTHLY_LIMIT = 3.0
DISK_USAGE_THRESHOLD = 0.80
CHECK_INTERVAL = 300


class CircuitBreaker:
    def __init__(self, db_path: str, bot=None):
        self.db_path = db_path
        self.bot = bot
        self._indexer_failures: dict[str, int] = {}
        self._disk_warning_sent = False

    def check_indexer_health(self) -> None:
        """Check indexer_state for consecutive failures."""
        def _read(con):
            return con.execute(
                "SELECT indexer_name, last_run_status FROM indexer_state"
            ).fetchall()

        rows = db_read_with_retry(self.db_path, _read)

        for name, status in rows:
            target = INDEXER_NAME_TO_TARGET.get(name)
            if not target:
                continue

            if status == "failed":
                self._indexer_failures[name] = self._indexer_failures.get(name, 0) + 1
                if self._indexer_failures[name] >= FAILURE_THRESHOLD:
                    if is_component_enabled(self.db_path, target):
                        reason = f"{name}: {self._indexer_failures[name]} consecutive failures"
                        set_kill_switch(
                            self.db_path, target, enabled=True,
                            reason=reason, actor="circuit_breaker",
                        )
                        logger.error("circuit_breaker_indexer", indexer=name, failures=self._indexer_failures[name])
            else:
                self._indexer_failures[name] = 0

    def check_llm_cost(self) -> None:
        """Estimate monthly LLM cost and kill C3 if over budget."""
        def _read(con):
            return con.execute(
                "SELECT COUNT(*) FROM resolution_risk_cache "
                "WHERE computed_at >= date_trunc('month', CURRENT_DATE)"
            ).fetchone()[0]

        monthly_calls = db_read_with_retry(self.db_path, _read)
        estimated_cost = monthly_calls * LLM_COST_PER_CALL

        if estimated_cost > LLM_MONTHLY_LIMIT:
            if is_component_enabled(self.db_path, "c3"):
                _invalidate_cache()
                set_kill_switch(
                    self.db_path, "c3", enabled=True,
                    reason=f"LLM cost ${estimated_cost:.2f} > ${LLM_MONTHLY_LIMIT:.2f} limit",
                    actor="circuit_breaker",
                )
                logger.error("circuit_breaker_llm_cost", estimated=estimated_cost, limit=LLM_MONTHLY_LIMIT)

    def check_disk_usage(self) -> None:
        """Warn if disk usage exceeds threshold."""
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        stat = os.statvfs(db_dir)
        usage_pct = 1 - (stat.f_bavail / stat.f_blocks)

        if usage_pct > DISK_USAGE_THRESHOLD:
            if not self._disk_warning_sent:
                self._disk_warning_sent = True
                logger.error("circuit_breaker_disk", usage_pct=f"{usage_pct:.1%}")
                log_audit(
                    self.db_path, "circuit_breaker", "disk",
                    "warning", reason=f"Disk usage {usage_pct:.1%}", actor="system",
                )
        else:
            self._disk_warning_sent = False

    async def run_forever(self) -> None:
        """Check all circuit breakers every 5 minutes."""
        while True:
            try:
                self.check_indexer_health()
                self.check_llm_cost()
                self.check_disk_usage()
            except Exception:
                logger.exception("circuit_breaker_error")
            await asyncio.sleep(CHECK_INTERVAL)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_circuit_breakers.py -v`

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/polybot/orchestrator/circuit_breakers.py tests/unit/test_circuit_breakers.py
git commit -m "feat(M8): circuit_breakers module (indexer health, LLM cost, disk)"
```

---

### Task 6: Extend /toggle and Add /audit Commands

**Files:**
- Modify: `src/polybot/telegram/bot.py`
- Create: `tests/unit/test_toggle_audit_commands.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_toggle_audit_commands.py`:

```python
"""Tests for /toggle and /audit bot commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import duckdb
import pytest

from polybot.orchestrator.kill_switches import _invalidate_cache


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("""
        CREATE TABLE kill_switches (
            target VARCHAR PRIMARY KEY, enabled BOOLEAN DEFAULT FALSE,
            reason VARCHAR, toggled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            toggled_by VARCHAR DEFAULT 'manual'
        )
    """)
    con.execute("CREATE SEQUENCE audit_log_seq START 1")
    con.execute("""
        CREATE TABLE audit_log (
            id BIGINT DEFAULT nextval('audit_log_seq') PRIMARY KEY,
            event_type VARCHAR, target VARCHAR, action VARCHAR,
            reason VARCHAR, actor VARCHAR DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.close()
    _invalidate_cache()
    return path


def _make_update_context(args):
    update = MagicMock()
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = args
    return update, context


class TestToggleCommand:
    @pytest.mark.asyncio
    async def test_toggle_c1_off(self, db_path):
        from polybot.telegram.bot import PolyBot

        settings = MagicMock()
        settings.DUCKDB_PATH = db_path
        settings.LOG_LEVEL = "INFO"
        settings.LOG_DIR = "/tmp"
        settings.SHADOW_MODE = True

        with patch.object(PolyBot, "__init__", lambda self, s: None):
            bot = PolyBot.__new__(PolyBot)
            bot.settings = settings
            bot.db_path = db_path
            bot.send_alert = AsyncMock()

        update, context = _make_update_context(["c1", "off", "test", "reason"])
        await bot._cmd_toggle(update, context)

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "c1" in reply.lower()
        assert "off" in reply.lower() or "ON" in reply  # kill switch ON = component OFF

        from polybot.orchestrator.kill_switches import is_component_enabled
        _invalidate_cache()
        assert is_component_enabled(db_path, "c1") is False


class TestAuditCommand:
    @pytest.mark.asyncio
    async def test_audit_shows_events(self, db_path):
        from polybot.orchestrator.audit_log import log_audit
        log_audit(db_path, "kill_switch", "c1", "on", reason="test", actor="manual")
        log_audit(db_path, "rate_limit", "c2", "exceeded", actor="system")

        from polybot.telegram.bot import PolyBot

        with patch.object(PolyBot, "__init__", lambda self, s: None):
            bot = PolyBot.__new__(PolyBot)
            bot.db_path = db_path
            bot.settings = MagicMock()

        update, context = _make_update_context([])
        await bot._cmd_audit(update, context)

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "c1" in reply
        assert "c2" in reply
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_toggle_audit_commands.py -v`

Expected: FAIL — `AttributeError: 'PolyBot' object has no attribute '_cmd_audit'`

- [ ] **Step 3: Modify bot.py — extend /toggle**

In `src/polybot/telegram/bot.py`, replace the `_cmd_toggle` method (lines 309-326) with:

```python
    async def _cmd_toggle(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        from polybot.orchestrator.kill_switches import VALID_TARGETS, set_kill_switch

        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Usage: /toggle shadow | /toggle <target> on|off [raison]",
                parse_mode="HTML",
            )
            return

        target = args[0].lower()

        if target == "shadow":
            self.settings.SHADOW_MODE = not self.settings.SHADOW_MODE
            state = "ON" if self.settings.SHADOW_MODE else "OFF"
            channel = "#ops" if self.settings.SHADOW_MODE else "#alerts"
            await update.message.reply_text(
                f"Shadow mode: <b>{state}</b> — alertes dans {channel}",
                parse_mode="HTML",
            )
            logger.info("shadow_mode_toggled", shadow_mode=self.settings.SHADOW_MODE)
            return

        if target not in VALID_TARGETS:
            await update.message.reply_text(
                f"Target invalide. Valides: shadow, {', '.join(sorted(VALID_TARGETS))}",
            )
            return

        if len(args) < 2 or args[1].lower() not in ("on", "off"):
            await update.message.reply_text("Usage: /toggle <target> on|off [raison]")
            return

        action = args[1].lower()
        enabled = action == "off"  # "off" means kill switch ON (component disabled)
        reason = " ".join(args[2:]) if len(args) > 2 else None

        set_kill_switch(self.db_path, target, enabled=enabled, reason=reason, actor="manual")

        state_label = "OFF (kill switch actif)" if enabled else "ON (kill switch levé)"
        await update.message.reply_text(
            f"<b>{target}</b> : {state_label}" + (f"\nRaison: {reason}" if reason else ""),
            parse_mode="HTML",
        )
        await self.send_alert(
            "ops",
            f"Kill switch <b>{target}</b> → {state_label}" + (f"\nRaison: {reason}" if reason else ""),
        )
```

- [ ] **Step 4: Add /audit command to bot.py**

Add this method to the `PolyBot` class:

```python
    async def _cmd_audit(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        from polybot.db.connection import db_read_with_retry

        args = context.args or []
        n = int(args[0]) if args and args[0].isdigit() else 10

        def _read(con):
            return con.execute(
                "SELECT event_type, target, action, reason, actor, created_at "
                "FROM audit_log ORDER BY created_at DESC LIMIT ?",
                [n],
            ).fetchall()

        rows = db_read_with_retry(self.db_path, _read)
        if not rows:
            await update.message.reply_text("Audit log vide.")
            return

        icons = {
            "kill_switch": "\u2699\ufe0f",
            "rate_limit": "\u26a0\ufe0f",
            "circuit_breaker": "\U0001f527",
            "config_change": "\U0001f4b0",
        }

        lines = [f"<b>Audit Log ({len(rows)} derniers)</b>\n"]
        for event_type, target, action, reason, actor, created_at in rows:
            icon = icons.get(event_type, "\U0001f4cb")
            ts = created_at.strftime("%H:%M") if created_at else "?"
            line = f"{icon} {ts} — {event_type} <b>{target}</b> {action}"
            if reason:
                line += f' "{reason}"'
            line += f" ({actor})"
            lines.append(line)

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
```

- [ ] **Step 5: Register /audit handler**

In `_register_handlers` (around line 47 of bot.py), add:

```python
        self.app.add_handler(CommandHandler("audit", self._cmd_audit))
```

And in the `set_my_commands` block in `daemon.py` (around line 105), add:

```python
            BotCommand("audit", "Derniers événements d'audit"),
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_toggle_audit_commands.py -v`

Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add src/polybot/telegram/bot.py tests/unit/test_toggle_audit_commands.py
git commit -m "feat(M8): extend /toggle for kill switches, add /audit command"
```

---

### Task 7: Integrate Kill Switches + Rate Limits into C1

**Files:**
- Modify: `src/polybot/components/c1_sharp_money.py:326-330`

- [ ] **Step 1: Add kill switch + rate limit check before C1 alert emission**

In `src/polybot/components/c1_sharp_money.py`, before the `# Route based on shadow mode` line (line 328), add:

```python
        from polybot.orchestrator.kill_switches import is_component_enabled
        from polybot.orchestrator.rate_limits import check_rate_limit, increment_counter

        if not is_component_enabled(self.db_path, "c1"):
            logger.info("c1_killed", alert_id=alert_id)
            return

        if not check_rate_limit(self.db_path, "c1"):
            logger.warning("c1_rate_limit_exceeded", alert_id=alert_id)
            return
```

And after the successful `send_alert` call (after line 329), add:

```python
        increment_counter(self.db_path, "c1")
```

- [ ] **Step 2: Run existing C1 tests to verify no regression**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py -v`

Expected: All existing tests pass

- [ ] **Step 3: Commit**

```bash
git add src/polybot/components/c1_sharp_money.py
git commit -m "feat(M8): integrate kill switch + rate limit into C1"
```

---

### Task 8: Integrate Kill Switches + Rate Limits into C2

**Files:**
- Modify: `src/polybot/components/c2_informed_trading.py`

- [ ] **Step 1: Replace C2 hardcoded rate limit with centralized one**

In `src/polybot/components/c2_informed_trading.py`, replace the `check_rate_limit` method call in `scan_once` (around line 601):

Change:
```python
            if not self.check_rate_limit():
                logger.info("c2_rate_limit_reached")
                break
```

To:
```python
            from polybot.orchestrator.rate_limits import check_rate_limit as check_rl
            if not check_rl(self.db_path, "c2"):
                logger.info("c2_rate_limit_reached")
                break
```

- [ ] **Step 2: Add kill switch check before C2 alert emission**

In the `_emit_telegram` method (before line 676), add:

```python
        from polybot.orchestrator.kill_switches import is_component_enabled

        if not is_component_enabled(self.db_path, "c2"):
            logger.info("c2_killed", alert_id=alert["alert_id"])
            return
```

And after the successful `send_alert` call, add:

```python
        from polybot.orchestrator.rate_limits import increment_counter
        increment_counter(self.db_path, "c2")
```

- [ ] **Step 3: Run existing C2 tests to verify no regression**

Run: `uv run pytest tests/unit/test_c2_informed_trading.py -v`

Expected: All existing tests pass

- [ ] **Step 4: Commit**

```bash
git add src/polybot/components/c2_informed_trading.py
git commit -m "feat(M8): integrate kill switch + centralized rate limit into C2"
```

---

### Task 9: Integrate Kill Switch into C3

**Files:**
- Modify: `src/polybot/components/c3_resolution_risk.py:270-278`

- [ ] **Step 1: Add kill switch check before LLM call**

In `score_market()`, replace the `else` branch that calls `self.call_haiku(market)` (around lines 270-278):

Change:
```python
        else:
            try:
                result = self.call_haiku(market)
```

To:
```python
        else:
            from polybot.orchestrator.kill_switches import is_component_enabled
            if not is_component_enabled(self.db_path, "c3"):
                logger.info("c3_killed_rules_only", condition_id=condition_id[:16])
                return self.score_market_fallback(condition_id, market)
            try:
                result = self.call_haiku(market)
```

- [ ] **Step 2: Run existing C3 tests to verify no regression**

Run: `uv run pytest tests/unit/test_c3_resolution_risk.py -v`

Expected: All existing tests pass

- [ ] **Step 3: Commit**

```bash
git add src/polybot/components/c3_resolution_risk.py
git commit -m "feat(M8): integrate kill switch into C3 (rules-only fallback)"
```

---

### Task 10: Integrate Kill Switches into Daemon + Circuit Breaker

**Files:**
- Modify: `src/polybot/daemon.py`

- [ ] **Step 1: Add kill switch check to run_scheduled_indexer**

In `src/polybot/daemon.py`, modify the `run_scheduled_indexer` function. Add an import at the top of the file:

```python
from polybot.orchestrator.kill_switches import is_component_enabled
```

Inside the `while True` loop of `run_scheduled_indexer`, before the `try` block, add:

```python
        if not is_component_enabled(kwargs.get("db_path", ""), name):
            logger.info("indexer_killed", indexer=name)
            await asyncio.sleep(interval)
            continue
```

- [ ] **Step 2: Add circuit breaker to asyncio.gather**

Add import at the top of `daemon.py`:

```python
from polybot.orchestrator.circuit_breakers import CircuitBreaker
```

In `main()`, after the `db_executor` creation (around line 96), add:

```python
    circuit = CircuitBreaker(db_path=db_path, bot=bot)
```

Add `circuit.run_forever()` to the `asyncio.gather()` call:

```python
                circuit.run_forever(),
```

- [ ] **Step 3: Add /audit to bot commands list**

In the `set_my_commands` block, add:

```python
            BotCommand("audit", "Derniers événements d'audit"),
```

And update the `/toggle` description:

```python
            BotCommand("toggle", "Kill switch / shadow mode"),
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest tests/ -x -q --ignore=tests/integration/test_clob_snapshot_e2e.py`

Expected: All tests pass (164+ existing + new tests)

- [ ] **Step 5: Commit**

```bash
git add src/polybot/daemon.py
git commit -m "feat(M8): integrate kill switches + circuit breaker into daemon"
```

---

### Task 11: Final Integration Test

**Files:** None new — verify everything works together

- [ ] **Step 1: Run the complete test suite**

Run: `uv run pytest tests/ -q --ignore=tests/integration/test_clob_snapshot_e2e.py`

Expected: All tests pass (176+ tests)

- [ ] **Step 2: Verify import chain works**

Run: `PYTHONPATH=src uv run python -c "from polybot.daemon import main; print('import OK')"`

Expected: `import OK`

- [ ] **Step 3: Verify lint is clean**

Run: `uv run ruff check src/polybot/orchestrator/ src/polybot/daemon.py src/polybot/telegram/bot.py src/polybot/components/c1_sharp_money.py src/polybot/components/c2_informed_trading.py src/polybot/components/c3_resolution_risk.py`

Expected: `All checks passed!`

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix(M8): lint and integration fixes"
```
