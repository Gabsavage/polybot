# M8-C Weekly Report + Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a weekly performance report (auto Sunday 20:00 CEST + `/weekly` command) and deploy M8-A + M8-C to VPS.

**Architecture:** New `weekly_report.py` module with `generate_weekly_report(db_path, weeks)` containing 8 sections via helper functions. Scheduler coroutine in daemon.py added to `asyncio.gather()`. `/weekly` command in bot.py. Deploy via git push + ssh.

**Tech Stack:** DuckDB, structlog, python-telegram-bot, asyncio

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/polybot/components/weekly_report.py` | `generate_weekly_report()` with 8 report sections |
| Create | `tests/unit/test_weekly_report.py` | 4 tests: full format, empty, /weekly command, LLM coûts |
| Modify | `src/polybot/daemon.py:14,131,122` | Import + `schedule_weekly_report()` + add to gather + add to set_my_commands |
| Modify | `src/polybot/telegram/bot.py:51,421` | Register `/weekly` handler + add `_cmd_weekly` method + update help |

---

### Task 1: Weekly Report Module — Tests + Implementation

**Files:**
- Create: `src/polybot/components/weekly_report.py`
- Create: `tests/unit/test_weekly_report.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_weekly_report.py`:

```python
"""Tests for weekly report module."""

from datetime import datetime, timezone

import duckdb
import pytest

from polybot.components.weekly_report import generate_weekly_report


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("""
        CREATE TABLE alerts (
            alert_id VARCHAR PRIMARY KEY,
            component VARCHAR,
            emitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            trade_hash VARCHAR,
            wallet_address VARCHAR,
            condition_id VARCHAR,
            side VARCHAR,
            size_usd DECIMAL(18,2),
            price DECIMAL(6,4),
            size_suggested_usd DECIMAL(18,2),
            resolution_risk_score DECIMAL(3,2),
            resolution_risk_category VARCHAR,
            telegram_message_id BIGINT,
            alignment_score INTEGER,
            score INTEGER,
            features_passed VARCHAR,
            momentum_4h DECIMAL(6,4)
        )
    """)
    con.execute("""
        CREATE TABLE alert_outcomes (
            alert_id VARCHAR PRIMARY KEY,
            condition_id VARCHAR NOT NULL,
            resolved_at TIMESTAMP,
            resolution_outcome VARCHAR,
            direction_traded VARCHAR,
            was_direction_correct BOOLEAN,
            price_at_alert DECIMAL(6,4),
            price_at_resolution DECIMAL(6,4),
            shadow_pnl_simulated DECIMAL(18,2),
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE tracked_wallets (
            address VARCHAR PRIMARY KEY,
            tier VARCHAR,
            active BOOLEAN,
            source VARCHAR,
            added_at TIMESTAMP,
            last_reviewed_at TIMESTAMP,
            honeypot_flag BOOLEAN,
            honeypot_score DECIMAL(3,2),
            notes TEXT,
            last_seen_timestamp BIGINT DEFAULT 0
        )
    """)
    con.execute("""
        CREATE TABLE trades (
            transaction_hash VARCHAR PRIMARY KEY,
            proxy_wallet VARCHAR NOT NULL,
            condition_id VARCHAR NOT NULL,
            asset_id VARCHAR NOT NULL,
            side VARCHAR,
            size_usd DECIMAL(18,2) NOT NULL,
            price DECIMAL(6,4) NOT NULL,
            outcome VARCHAR,
            outcome_index INTEGER,
            timestamp_unix BIGINT NOT NULL,
            timestamp_ts TIMESTAMP NOT NULL,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        CREATE TABLE indexer_state (
            indexer_name VARCHAR PRIMARY KEY,
            last_synced_at TIMESTAMP,
            last_block_number BIGINT,
            last_cursor VARCHAR,
            last_run_status VARCHAR,
            last_run_duration_ms INTEGER,
            last_error VARCHAR,
            ingested_count BIGINT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE resolution_risk_cache (
            condition_id VARCHAR PRIMARY KEY,
            llm_score DECIMAL(3,2),
            llm_reasons TEXT[],
            llm_red_flags TEXT[],
            llm_model_version VARCHAR,
            computed_at TIMESTAMP
        )
    """)
    con.close()
    return path


def _seed_data(db_path):
    """Insert test data: C1 + C2 alerts, outcomes, wallets, trades, audit events, LLM cache."""
    con = duckdb.connect(db_path)
    # C1 alerts
    for i in range(8):
        con.execute(
            "INSERT INTO alerts (alert_id, component, side, emitted_at, condition_id, size_usd) "
            "VALUES (?, 'C1', ?, CURRENT_TIMESTAMP - INTERVAL 1 DAY, ?, 500)",
            [f"AL_C1_{i}", "BUY" if i < 6 else "SELL", f"cond_c1_{i}"],
        )
    # C2 alerts
    for i in range(3):
        con.execute(
            "INSERT INTO alerts (alert_id, component, score, emitted_at, condition_id, alignment_score) "
            "VALUES (?, 'C2', ?, CURRENT_TIMESTAMP - INTERVAL 2 DAY, ?, ?)",
            [f"AL_C2_{i}", 4 + i, f"cond_c2_{i}", [1, -1, 0][i]],
        )
    # Outcomes (5 resolved, 6 pending)
    for i in range(5):
        con.execute(
            "INSERT INTO alert_outcomes (alert_id, condition_id, resolution_outcome, was_direction_correct, shadow_pnl_simulated) "
            "VALUES (?, ?, 'YES', ?, ?)",
            [f"AL_C1_{i}", f"cond_c1_{i}", i < 4, 25.0 if i < 4 else -12.60],
        )
    # Wallets (15 tier A, 11 active with trades, 4 silent)
    for i in range(15):
        con.execute(
            "INSERT INTO tracked_wallets (address, tier, active, notes) VALUES (?, 'A', TRUE, ?)",
            [f"0xwallet_{i}", f"wallet_{i}"],
        )
    # Trades for 11 wallets
    for i in range(11):
        for j in range(3):
            con.execute(
                "INSERT INTO trades (transaction_hash, proxy_wallet, condition_id, asset_id, "
                "side, size_usd, price, timestamp_unix, timestamp_ts) "
                "VALUES (?, ?, 'cond_x', 'asset_x', 'BUY', 100, 0.65, 1714100000, CURRENT_TIMESTAMP - INTERVAL 1 DAY)",
                [f"tx_{i}_{j}", f"0xwallet_{i}"],
            )
    # Audit events
    con.execute(
        "INSERT INTO audit_log (event_type, target, action) VALUES ('rate_limit', 'c2', 'exceeded')"
    )
    # Indexer errors
    con.execute(
        "INSERT INTO indexer_state (indexer_name, last_synced_at, last_run_status) VALUES ('markets_gamma', CURRENT_TIMESTAMP, 'failed')"
    )
    con.execute(
        "INSERT INTO indexer_state (indexer_name, last_synced_at, last_run_status) VALUES ('onchain_alchemy', CURRENT_TIMESTAMP, 'success')"
    )
    # LLM cache
    for i in range(50):
        con.execute(
            "INSERT INTO resolution_risk_cache (condition_id, llm_score, computed_at) VALUES (?, 0.5, CURRENT_TIMESTAMP)",
            [f"risk_{i}"],
        )
    con.close()


class TestWeeklyReportFormat:
    def test_all_sections_present(self, db_path):
        _seed_data(db_path)
        report = generate_weekly_report(db_path, weeks=1)

        assert "Weekly Report" in report
        assert "Alertes" in report
        assert "C1" in report
        assert "C2" in report
        assert "Performance shadow" in report
        assert "Performance cumul" in report
        assert "Wallets Tier A" in report
        assert "Alignment" in report
        assert "Orchestrateur" in report
        assert "Co" in report  # Coûts (accented char)

    def test_c1_count_correct(self, db_path):
        _seed_data(db_path)
        report = generate_weekly_report(db_path, weeks=1)
        assert "8 alertes" in report

    def test_shadow_pnl_present(self, db_path):
        _seed_data(db_path)
        report = generate_weekly_report(db_path, weeks=1)
        assert "$" in report
        assert "4/5" in report or "80%" in report


class TestWeeklyReportEmpty:
    def test_no_alerts_short_message(self, db_path):
        report = generate_weekly_report(db_path, weeks=1)
        assert "Aucune alerte" in report


class TestWeeklyReportCosts:
    def test_llm_cost_shown(self, db_path):
        _seed_data(db_path)
        report = generate_weekly_report(db_path, weeks=1)
        assert "$0.05" in report or "0.05" in report
        assert "50" in report  # 50 calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/gabsav/Documents/Polycasquette/Code && uv run pytest tests/unit/test_weekly_report.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'polybot.components.weekly_report'`

- [ ] **Step 3: Write implementation**

Create `src/polybot/components/weekly_report.py`:

```python
"""Weekly report generation for Polybot — full 8-section performance summary."""

from datetime import UTC, datetime

from polybot.db.connection import connect as db_connect

FRENCH_MONTHS = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def generate_weekly_report(db_path: str, weeks: int = 1) -> str:
    """Generate a weekly performance report. Returns formatted HTML string."""
    con = db_connect(db_path, read_only=True)
    try:
        return _build_report(con, weeks)
    finally:
        con.close()


def _build_report(con, weeks: int) -> str:
    interval = f"{7 * weeks} DAY"

    now = datetime.now(UTC)
    year, week_num, _ = now.isocalendar()
    month_name = FRENCH_MONTHS[now.month]

    # Check if any alerts exist in window
    total_alerts = con.execute(
        f"SELECT COUNT(*) FROM alerts WHERE emitted_at >= CURRENT_DATE - INTERVAL {interval}"
    ).fetchone()[0]

    if total_alerts == 0:
        return f"📊 <b>Weekly Report — Sem {week_num}</b>\n\nAucune alerte cette semaine."

    parts = [f"📊 <b>Weekly Report — Sem {week_num} ({month_name} {year})</b>"]
    parts.append(_section_alerts(con, interval))
    parts.append(_section_shadow(con, interval, weeks))
    parts.append(_section_cumulative(con))
    parts.append(_section_wallets(con, interval, weeks))
    alignment = _section_alignment(con, interval)
    if alignment:
        parts.append(alignment)
    parts.append(_section_orchestrator(con, interval))
    parts.append(_section_costs(con, interval))

    return "\n".join(parts)


def _section_alerts(con, interval: str) -> str:
    rows = con.execute(
        f"""
        SELECT component, COUNT(*), AVG(score)
        FROM alerts
        WHERE emitted_at >= CURRENT_DATE - INTERVAL {interval}
        GROUP BY component
        """
    ).fetchall()

    comp = {r[0]: (r[1], r[2]) for r in rows}
    c1_cnt = comp.get("C1", (0, None))[0]
    c2_cnt, c2_avg = comp.get("C2", (0, None))
    total = c1_cnt + c2_cnt

    lines = ["\n🎯 <b>Alertes émises</b>"]

    if c1_cnt:
        sides = con.execute(
            f"""
            SELECT side, COUNT(*) FROM alerts
            WHERE component = 'C1'
              AND emitted_at >= CURRENT_DATE - INTERVAL {interval}
            GROUP BY side
            """
        ).fetchall()
        side_str = ", ".join(f"{cnt} {s}" for s, cnt in sides) if sides else ""
        lines.append(f"  C1 : {c1_cnt} alertes ({side_str})")

    if c2_cnt:
        avg_str = f" (score moyen {c2_avg:.1f}/7)" if c2_avg else ""
        lines.append(f"  C2 : {c2_cnt} alertes{avg_str}")

    lines.append(f"  Total : {total}")
    return "\n".join(lines)


def _section_shadow(con, interval: str, weeks: int) -> str:
    row = con.execute(
        f"""
        SELECT
            COUNT(*) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL
                  AND ao.resolution_outcome != 'PENDING'
            ) as resolved,
            COUNT(*) FILTER (
                WHERE ao.was_direction_correct = TRUE
            ) as correct,
            SUM(ao.shadow_pnl_simulated) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL
                  AND ao.resolution_outcome != 'PENDING'
            ) as pnl
        FROM alerts a
        JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
        WHERE a.emitted_at >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()
    resolved, correct, pnl = row
    pnl = float(pnl) if pnl else 0.0

    lines = [f"\n⚖️ <b>Performance shadow ({weeks * 7} jours)</b>"]
    if resolved == 0:
        lines.append("  Aucune alerte résolue")
    else:
        pct = correct / resolved * 100
        sign = "+" if pnl >= 0 else ""
        lines.append(f"  Résolues : {resolved}")
        lines.append(f"  Direction correcte : {correct}/{resolved} ({pct:.0f}%)")
        lines.append(f"  Shadow P&amp;L : {sign}${abs(pnl):,.2f}")

    return "\n".join(lines)


def _section_cumulative(con) -> str:
    total = con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    row = con.execute(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL
                  AND ao.resolution_outcome != 'PENDING'
            ) as resolved,
            COUNT(*) FILTER (
                WHERE ao.was_direction_correct = TRUE
            ) as correct,
            SUM(ao.shadow_pnl_simulated) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL
                  AND ao.resolution_outcome != 'PENDING'
            ) as pnl
        FROM alerts a
        LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
        """
    ).fetchone()
    resolved, correct, pnl = row
    pnl = float(pnl) if pnl else 0.0

    lines = ["\n📈 <b>Performance cumulée</b>"]
    lines.append(f"  Total alertes : {total}")
    if resolved == 0:
        lines.append("  Aucune résolue")
    else:
        pct = correct / resolved * 100
        sign = "+" if pnl >= 0 else ""
        lines.append(f"  Résolues : {resolved}")
        lines.append(f"  Direction correcte : {correct}/{resolved} ({pct:.0f}%)")
        lines.append(f"  Shadow P&amp;L cumulé : {sign}${abs(pnl):,.2f}")

    if resolved < 30:
        lines.append("  <i>⚠️ Échantillon &lt; 30 — trop tôt pour conclure</i>")

    return "\n".join(lines)


def _section_wallets(con, interval: str, weeks: int) -> str:
    total_a = con.execute(
        "SELECT COUNT(*) FROM tracked_wallets WHERE tier = 'A' AND active = TRUE"
    ).fetchone()[0]

    active_wallets = con.execute(
        f"""
        SELECT COUNT(DISTINCT t.proxy_wallet)
        FROM trades t
        JOIN tracked_wallets tw ON t.proxy_wallet = tw.address
        WHERE tw.tier = 'A' AND tw.active = TRUE
          AND t.timestamp_ts >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()[0]

    silent_rows = con.execute(
        f"""
        SELECT tw.address, tw.notes
        FROM tracked_wallets tw
        WHERE tw.tier = 'A' AND tw.active = TRUE
        AND NOT EXISTS (
            SELECT 1 FROM trades t
            WHERE t.proxy_wallet = tw.address
            AND t.timestamp_ts >= CURRENT_DATE - INTERVAL {interval}
        )
        """
    ).fetchall()

    trades_total = con.execute(
        f"SELECT COUNT(*) FROM trades WHERE timestamp_ts >= CURRENT_DATE - INTERVAL {interval}"
    ).fetchone()[0]

    silent_names = [r[1] or r[0][:10] for r in silent_rows]
    silent_str = ", ".join(silent_names[:5]) if silent_names else "aucun"

    lines = ["\n👛 <b>Wallets Tier A</b>"]
    lines.append(f"  Actifs : {active_wallets}/{total_a}")
    lines.append(f"  Silencieux &gt; {weeks}sem : {len(silent_rows)} ({silent_str})")
    lines.append(f"  Trades : {trades_total}")

    return "\n".join(lines)


def _section_alignment(con, interval: str) -> str | None:
    rows = con.execute(
        f"""
        SELECT alignment_score, COUNT(*)
        FROM alerts
        WHERE component = 'C2'
          AND alignment_score IS NOT NULL
          AND emitted_at >= CURRENT_DATE - INTERVAL {interval}
        GROUP BY alignment_score
        ORDER BY alignment_score DESC
        """
    ).fetchall()

    if not rows:
        return None

    dist = {int(r[0]): int(r[1]) for r in rows}
    lines = ["\n🧭 <b>Alignment C2</b>"]
    lines.append(f"  📈 Suit mouvement : {dist.get(1, 0)}")
    lines.append(f"  📉 Contrariant : {dist.get(-1, 0)}")
    lines.append(f"  ➡️ Neutre : {dist.get(0, 0)}")

    return "\n".join(lines)


def _section_orchestrator(con, interval: str) -> str:
    ks = con.execute(
        f"""
        SELECT COUNT(*) FROM audit_log
        WHERE event_type = 'kill_switch' AND action = 'on'
          AND created_at >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()[0]

    rl = con.execute(
        f"""
        SELECT COUNT(*) FROM audit_log
        WHERE event_type = 'rate_limit' AND action = 'exceeded'
          AND created_at >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()[0]

    cb = con.execute(
        f"""
        SELECT COUNT(*) FROM audit_log
        WHERE event_type = 'circuit_breaker'
          AND created_at >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()[0]

    idx_errors = con.execute(
        "SELECT COUNT(*) FROM indexer_state WHERE last_run_status = 'failed'"
    ).fetchone()[0]

    lines = ["\n⚙️ <b>Orchestrateur</b>"]
    lines.append(f"  Kill switches activés : {ks}")
    lines.append(f"  Rate limits atteints : {rl}")
    lines.append(f"  Circuit breakers : {cb}")
    lines.append(f"  Erreurs indexers : {idx_errors}")

    return "\n".join(lines)


def _section_costs(con, interval: str) -> str:
    llm_calls = con.execute(
        f"""
        SELECT COUNT(*) FROM resolution_risk_cache
        WHERE computed_at >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()[0]

    llm_cost = llm_calls * 0.001

    lines = ["\n💰 <b>Coûts</b>"]
    lines.append(f"  LLM Haiku : ~${llm_cost:.2f} ({llm_calls} calls)")
    lines.append("  VPS : $4/mois")

    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/gabsav/Documents/Polycasquette/Code && uv run pytest tests/unit/test_weekly_report.py -v`

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git add src/polybot/components/weekly_report.py tests/unit/test_weekly_report.py
git commit -m "feat(M8-C): weekly report module with 8 sections + tests"
```

---

### Task 2: /weekly Command + Daemon Integration

**Files:**
- Modify: `src/polybot/telegram/bot.py:51,421`
- Modify: `src/polybot/daemon.py:14,122,131`

- [ ] **Step 1: Add /weekly test to test_toggle_audit_commands.py**

Append to `tests/unit/test_toggle_audit_commands.py`:

```python
class TestWeeklyCommand:
    @pytest.mark.asyncio
    async def test_weekly_returns_report(self, db_path):
        from polybot.telegram.bot import PolyBot

        with patch.object(PolyBot, "__init__", lambda self, s: None):
            bot = PolyBot.__new__(PolyBot)
            bot.db_path = db_path
            bot.settings = MagicMock()

        update, context = _make_update_context([])
        await bot._cmd_weekly(update, context)

        update.message.reply_text.assert_called_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "Weekly Report" in reply or "Aucune alerte" in reply
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/gabsav/Documents/Polycasquette/Code && uv run pytest tests/unit/test_toggle_audit_commands.py::TestWeeklyCommand -v`

Expected: FAIL — `AttributeError: 'PolyBot' object has no attribute '_cmd_weekly'`

- [ ] **Step 3: Add _cmd_weekly to bot.py**

In `src/polybot/telegram/bot.py`, add the `/weekly` handler registration after the `/audit` line (line 51):

```python
        self.app.add_handler(CommandHandler("weekly", self._cmd_weekly))
```

Add the `_cmd_weekly` method after `_cmd_audit` (before `_cmd_help`):

```python
    async def _cmd_weekly(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        from polybot.components.weekly_report import generate_weekly_report

        args = context.args or []
        weeks = 1
        if args:
            with contextlib.suppress(ValueError):
                weeks = min(int(args[0]), 4)

        report = generate_weekly_report(self.db_path, weeks=weeks)
        await update.message.reply_text(report, parse_mode="HTML")
```

Update the `_cmd_help` text to add:

```python
            "/weekly [N] — Rapport hebdo (N semaines, défaut 1)\n"
```

- [ ] **Step 4: Add schedule_weekly_report to daemon.py**

In `src/polybot/daemon.py`, add import (after the `generate_report` import, line 14):

```python
from polybot.components.weekly_report import generate_weekly_report
```

Add the scheduler function after `schedule_daily_report` (after line 59):

```python
async def schedule_weekly_report(bot: PolyBot, db_path: str) -> None:
    """Send weekly report every Sunday at 20:00 CEST."""
    while True:
        now = datetime.now(CEST)
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour >= 20:
            days_until_sunday = 7
        target = datetime.combine(
            now.date() + timedelta(days=days_until_sunday),
            time(20, 0), CEST,
        )
        wait = (target - now).total_seconds()
        logger.info("weekly_report_scheduled", next_at=target.isoformat(), wait_s=int(wait))
        await asyncio.sleep(wait)
        try:
            report = generate_weekly_report(db_path)
            await bot.send_alert("ops", report)
            logger.info("weekly_report_sent")
        except Exception:
            logger.exception("weekly_report_failed")
```

Add to `asyncio.gather()` (after `schedule_daily_report(bot, db_path),` around line 131):

```python
                schedule_weekly_report(bot, db_path),
```

Add to `set_my_commands` (after the audit line, around line 122):

```python
            BotCommand("weekly", "Rapport hebdomadaire"),
```

- [ ] **Step 5: Run all tests**

Run: `cd /Users/gabsav/Documents/Polycasquette/Code && uv run pytest tests/unit/test_toggle_audit_commands.py -v`

Expected: 3 passed (toggle, audit, weekly)

- [ ] **Step 6: Run full suite + lint**

Run: `cd /Users/gabsav/Documents/Polycasquette/Code && uv run pytest tests/ -q --ignore=tests/integration/test_clob_snapshot_e2e.py && uv run ruff check src/polybot/components/weekly_report.py src/polybot/daemon.py src/polybot/telegram/bot.py`

Expected: All tests pass, lint clean

- [ ] **Step 7: Commit**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git add src/polybot/telegram/bot.py src/polybot/daemon.py tests/unit/test_toggle_audit_commands.py
git commit -m "feat(M8-C): /weekly command + schedule_weekly_report in daemon"
```

---

### Task 3: Deploy M8 (A + C) to VPS

**Files:** None new — deployment only

- [ ] **Step 1: Push to remote**

```bash
cd /Users/gabsav/Documents/Polycasquette/Code
git push origin main
```

- [ ] **Step 2: Sync VPS**

```bash
ssh polybot "cd /root/polybot && git pull origin main && uv sync"
```

- [ ] **Step 3: Run migration**

```bash
ssh polybot "cd /root/polybot && PYTHONPATH=src uv run python -c \"from polybot.db.migrations import apply_migrations; print(apply_migrations('data/pm.duckdb', 'migrations'))\""
```

Expected: `['007_m8a_orchestration_tables.sql']` (or empty list if already applied)

- [ ] **Step 4: Restart daemon**

```bash
ssh polybot "systemctl restart polybot-bot.service && sleep 5 && systemctl status polybot-bot.service --no-pager"
```

Expected: Active (running)

- [ ] **Step 5: Check logs — no errors**

```bash
ssh polybot "journalctl -u polybot-bot.service --since '3 min ago' --no-pager -p err"
```

Expected: No output (0 errors)

```bash
ssh polybot "journalctl -u polybot-bot.service --since '3 min ago' --no-pager | head -40"
```

Expected: daemon_starting, telegram_bot_started, indexer_scheduled entries, weekly_report_scheduled

- [ ] **Step 6: Test Telegram commands**

Test these commands via Telegram (manually):

1. `/toggle c1 off test orchestrateur` → message confirms kill switch + #ops notified
2. `/toggle c1 on` → restored
3. `/audit` → shows the 2 toggle events
4. `/weekly` → weekly report displays all sections
5. `/status` → still functional
6. `/help` → shows audit, weekly, toggle

- [ ] **Step 7: Verify DB tables**

```bash
ssh polybot "cd /root/polybot && .venv/bin/python -c \"
import duckdb
con = duckdb.connect('data/pm.duckdb', read_only=True)
print('kill_switches:', con.execute('SELECT COUNT(*) FROM kill_switches').fetchone()[0])
print('audit_log:', con.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0])
print('rate_limit_counters:', con.execute('SELECT COUNT(*) FROM rate_limit_counters').fetchone()[0])
print()
for r in con.execute('SELECT indexer_name, last_run_status, last_synced_at FROM indexer_state ORDER BY indexer_name').fetchall():
    print(f'  {r}')
con.close()
\""
```

- [ ] **Step 8: Check resources**

```bash
ssh polybot "free -h && df -h /root"
```

Expected: RAM and disk within acceptable range
