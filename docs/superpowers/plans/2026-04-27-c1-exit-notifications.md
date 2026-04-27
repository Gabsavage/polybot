# C1 SELL Exit Notifications — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Notify Telegram when a Tier A wallet SELLs a position for which a C1 alert is currently pending (not yet resolved).

**Architecture:** A second code path inside `SharpMoneyDetector.poll_once`, dispatching SELL trades to a new `_process_exit` method. EXIT events persist to `audit_log` (no migration); in-memory dedup keyed on `(wallet, condition_id, outcome)`.

**Tech Stack:** Python 3.13, DuckDB, structlog, python-telegram-bot, pytest, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-04-27-c1-exit-notifications-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/polybot/config.py` | Adds `C1_EXIT_SIZE_MIN_USD` setting. |
| `src/polybot/components/c1_sharp_money.py` | Adds module-level helpers (`_humanize_time_held`, `_next_exit_id`, `_format_exit_message`, `_build_exit_keyboard`) and instance method `_process_exit`. `poll_once` dispatches BUY/SELL. `__init__` initialises the dedup set. |
| `tests/unit/test_c1_sharp_money.py` | Adds 4 new test classes (`TestHumanizeTimeHeld`, `TestNextExitId`, `TestFormatExitMessage`, `TestProcessExit`) covering all 8 acceptance tests. |

No new files; no migration.

---

## Conventions used throughout

- All `class TestXxx:` blocks live in `tests/unit/test_c1_sharp_money.py`; reuse the existing `db_path` and `settings` fixtures and the helpers `_seed_wallet`, `_seed_market`, `_insert_trade`.
- Imports of new helpers go at the top of the test file (alphabetised).
- Run unit tests with `uv run pytest tests/unit/test_c1_sharp_money.py -v`.
- Run a single test with `uv run pytest tests/unit/test_c1_sharp_money.py::TestX::test_y -v`.
- Each task ends with a commit using a Conventional Commit prefix (`feat`, `test`, `fix`, `chore`).

---

## Task 1: Add `C1_EXIT_SIZE_MIN_USD` setting

**Files:**
- Modify: `src/polybot/config.py` (add one line near `C1_SIZE_MIN_USD`)
- Test: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

Append this to `tests/unit/test_config.py`:

```python
def test_c1_exit_size_min_usd_default():
    from polybot.config import Settings

    s = Settings(
        R2_ACCESS_KEY_ID="t", R2_SECRET_ACCESS_KEY="t",
        R2_ENDPOINT="https://t.r2.cloudflarestorage.com",
        TELEGRAM_BOT_TOKEN="t:t", TELEGRAM_CHAT_ID=-1,
    )
    assert s.C1_EXIT_SIZE_MIN_USD == 500.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_config.py::test_c1_exit_size_min_usd_default -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'C1_EXIT_SIZE_MIN_USD'`.

- [ ] **Step 3: Add the setting**

In `src/polybot/config.py`, locate the line `C1_SIZE_MIN_USD: float = 1000.0` and add the new field directly below it:

```python
    C1_SIZE_MIN_USD: float = 1000.0
    C1_EXIT_SIZE_MIN_USD: float = 500.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: PASS (all tests in file).

- [ ] **Step 5: Commit**

```bash
git add src/polybot/config.py tests/unit/test_config.py
git commit -m "feat(config): add C1_EXIT_SIZE_MIN_USD (default \$500)"
```

---

## Task 2: Helper `_humanize_time_held`

Pure function; format a `timedelta` as "Xh" if under 24 hours, "Xj" otherwise (rounded down to whole hours/days).

**Files:**
- Modify: `src/polybot/components/c1_sharp_money.py` (add module-level helper near `_format_alert`)
- Test: `tests/unit/test_c1_sharp_money.py`

- [ ] **Step 1: Write the failing tests**

Append a new test class to `tests/unit/test_c1_sharp_money.py`:

```python
from datetime import timedelta


class TestHumanizeTimeHeld:
    def test_under_one_hour_rounds_to_hours(self):
        from polybot.components.c1_sharp_money import _humanize_time_held
        assert _humanize_time_held(timedelta(minutes=45)) == "0h"

    def test_hours_under_24(self):
        from polybot.components.c1_sharp_money import _humanize_time_held
        assert _humanize_time_held(timedelta(hours=3, minutes=30)) == "3h"
        assert _humanize_time_held(timedelta(hours=23, minutes=59)) == "23h"

    def test_24h_becomes_one_day(self):
        from polybot.components.c1_sharp_money import _humanize_time_held
        assert _humanize_time_held(timedelta(hours=24)) == "1j"

    def test_multi_day(self):
        from polybot.components.c1_sharp_money import _humanize_time_held
        assert _humanize_time_held(timedelta(days=3, hours=5)) == "3j"

    def test_negative_clamps_to_zero(self):
        from polybot.components.c1_sharp_money import _humanize_time_held
        assert _humanize_time_held(timedelta(seconds=-30)) == "0h"
```

Also add `from datetime import timedelta` to the existing imports if it isn't already there (it is — line 3).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestHumanizeTimeHeld -v`
Expected: FAIL — `ImportError: cannot import name '_humanize_time_held'`.

- [ ] **Step 3: Implement the helper**

In `src/polybot/components/c1_sharp_money.py`, add this module-level function directly after `_format_alert` (the function ending around line 126):

```python
def _humanize_time_held(delta: timedelta) -> str:
    """Format a timedelta as 'Xh' (< 24h) or 'Xj' (>= 24h). Negative → '0h'."""
    total_seconds = max(0.0, delta.total_seconds())
    hours = int(total_seconds // 3600)
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}j"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestHumanizeTimeHeld -v`
Expected: PASS (5/5).

- [ ] **Step 5: Commit**

```bash
git add src/polybot/components/c1_sharp_money.py tests/unit/test_c1_sharp_money.py
git commit -m "feat(c1): _humanize_time_held helper for exit notifications"
```

---

## Task 3: Helper `_next_exit_id`

Sequential daily counter scanned from `audit_log.target` rows whose `event_type='position_exit'` and prefix matches today.

**Files:**
- Modify: `src/polybot/components/c1_sharp_money.py` (add module-level helper near `_next_alert_id`)
- Test: `tests/unit/test_c1_sharp_money.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_c1_sharp_money.py`:

```python
class TestNextExitId:
    def test_empty_audit_log_returns_0001(self, db_path):
        from polybot.components.c1_sharp_money import _next_exit_id
        from datetime import datetime, UTC

        con = duckdb.connect(db_path)
        today = datetime.now(UTC).strftime("%Y%m%d")
        result = _next_exit_id(con)
        con.close()

        assert result == f"EXIT_{today}_0001"

    def test_increments_when_today_row_exists(self, db_path):
        from polybot.components.c1_sharp_money import _next_exit_id
        from datetime import datetime, UTC

        today = datetime.now(UTC).strftime("%Y%m%d")
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO audit_log (event_type, target, action) VALUES (?, ?, ?)",
            ["position_exit", f"EXIT_{today}_0001", "0xwallet1"],
        )
        result = _next_exit_id(con)
        con.close()

        assert result == f"EXIT_{today}_0002"

    def test_ignores_other_days(self, db_path):
        from polybot.components.c1_sharp_money import _next_exit_id
        from datetime import datetime, UTC

        today = datetime.now(UTC).strftime("%Y%m%d")
        con = duckdb.connect(db_path)
        # A row from a different day must not influence today's counter.
        con.execute(
            "INSERT INTO audit_log (event_type, target, action) VALUES (?, ?, ?)",
            ["position_exit", "EXIT_19990101_0042", "0xwallet1"],
        )
        result = _next_exit_id(con)
        con.close()

        assert result == f"EXIT_{today}_0001"

    def test_ignores_other_event_types(self, db_path):
        from polybot.components.c1_sharp_money import _next_exit_id
        from datetime import datetime, UTC

        today = datetime.now(UTC).strftime("%Y%m%d")
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO audit_log (event_type, target, action) VALUES (?, ?, ?)",
            ["kill_switch_toggled", f"EXIT_{today}_0007", "manual"],
        )
        result = _next_exit_id(con)
        con.close()

        assert result == f"EXIT_{today}_0001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestNextExitId -v`
Expected: FAIL — `ImportError: cannot import name '_next_exit_id'`.

- [ ] **Step 3: Implement the helper**

In `src/polybot/components/c1_sharp_money.py`, add this directly after the existing `_next_alert_id` function (around line 35–45):

```python
def _next_exit_id(con: duckdb.DuckDBPyConnection) -> str:
    """Generate next EXIT id: EXIT_YYYYMMDD_NNNN scanning audit_log.target."""
    today = datetime.now(UTC).strftime("%Y%m%d")
    prefix = f"EXIT_{today}_"
    row = con.execute(
        "SELECT target FROM audit_log "
        "WHERE event_type = 'position_exit' AND target LIKE ? "
        "ORDER BY target DESC LIMIT 1",
        [f"{prefix}%"],
    ).fetchone()
    if row is None:
        return f"{prefix}0001"
    last = row[0]
    n = int(last.rsplit("_", 1)[1]) + 1
    return f"{prefix}{n:04d}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestNextExitId -v`
Expected: PASS (4/4).

- [ ] **Step 5: Commit**

```bash
git add src/polybot/components/c1_sharp_money.py tests/unit/test_c1_sharp_money.py
git commit -m "feat(c1): _next_exit_id sequential daily counter from audit_log"
```

---

## Task 4: Helper `_format_exit_message`

Formats the EXIT Telegram message (HTML, mobile-first, mirrors `_format_alert` style).

**Files:**
- Modify: `src/polybot/components/c1_sharp_money.py`
- Test: `tests/unit/test_c1_sharp_money.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_c1_sharp_money.py`:

```python
class TestFormatExitMessage:
    def _kwargs(self, **overrides):
        defaults = {
            "exit_id": "EXIT_20260427_0001",
            "wallet_name": "sbimbg",
            "tier_label": "A1",
            "market_title": "Fed rate decision by April 2026?",
            "outcome": "Yes",
            "entry_price": 0.65,
            "exit_price": 0.72,
            "exit_size_usd": 3200.0,
            "pnl_pct": 10.77,
            "time_held": "3j",
        }
        defaults.update(overrides)
        return defaults

    def test_contains_required_fields(self):
        from polybot.components.c1_sharp_money import _format_exit_message
        msg = _format_exit_message(**self._kwargs())
        assert "Position Exit" in msg
        assert "EXIT_20260427_0001" in msg
        assert "sbimbg" in msg
        assert "A1" in msg
        assert "Fed rate decision" in msg
        assert "BUY Yes @ 0.65" in msg
        assert "SELL @ 0.72" in msg
        assert "3j" in msg  # time held
        assert "$3,200" in msg  # size with thousands separator

    def test_positive_pnl_has_plus_sign(self):
        from polybot.components.c1_sharp_money import _format_exit_message
        msg = _format_exit_message(**self._kwargs(pnl_pct=10.77))
        assert "+10.8%" in msg  # rounded to 1 decimal, plus sign

    def test_negative_pnl_has_minus_sign(self):
        from polybot.components.c1_sharp_money import _format_exit_message
        msg = _format_exit_message(
            **self._kwargs(entry_price=0.70, exit_price=0.55, pnl_pct=-21.43)
        )
        assert "-21.4%" in msg
        assert "+" not in msg.split("\n")[5]  # no plus sign on the SELL line

    def test_no_outcome_is_yes_by_default(self):
        from polybot.components.c1_sharp_money import _format_exit_message
        msg = _format_exit_message(**self._kwargs(outcome="No"))
        assert "BUY No @" in msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestFormatExitMessage -v`
Expected: FAIL — `ImportError: cannot import name '_format_exit_message'`.

- [ ] **Step 3: Implement the helper**

In `src/polybot/components/c1_sharp_money.py`, add this module-level function directly after `_humanize_time_held` (added in Task 2):

```python
def _format_exit_message(
    exit_id: str,
    wallet_name: str,
    tier_label: str,
    market_title: str,
    outcome: str,
    entry_price: float,
    exit_price: float,
    exit_size_usd: float,
    pnl_pct: float,
    time_held: str,
) -> str:
    """Format an EXIT notification message for Telegram (HTML)."""
    pnl_sign = "+" if pnl_pct >= 0 else ""
    parts = [
        f"⚠️ <b>Position Exit</b>  ·  <code>{exit_id}</code>",
        "",
        f"<b>{market_title}</b>",
        f"👤 {wallet_name}  ·  Tier {tier_label}",
        "",
        f"💰 Entrée : BUY {outcome} @ <b>{entry_price:.2f}</b>  (il y a {time_held})",
        f"📤 Sortie : SELL @ <b>{exit_price:.2f}</b>  ({pnl_sign}{pnl_pct:.1f}%)",
        f"💵 Size exit : ${exit_size_usd:,.0f}",
        "",
        "💡 Si vous avez copié, envisagez de sortir aussi.",
    ]
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestFormatExitMessage -v`
Expected: PASS (4/4).

- [ ] **Step 5: Commit**

```bash
git add src/polybot/components/c1_sharp_money.py tests/unit/test_c1_sharp_money.py
git commit -m "feat(c1): _format_exit_message Telegram formatter"
```

---

## Task 5: `_process_exit` skeleton — early returns

Adds the dedup set to `__init__`, the `_process_exit` method handling all the cases that should NOT emit a notification, and a small inline keyboard builder. No `audit_log` write or Telegram send yet — those land in Task 6.

**Files:**
- Modify: `src/polybot/components/c1_sharp_money.py`
- Test: `tests/unit/test_c1_sharp_money.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_c1_sharp_money.py`. Note the new helper `_seed_alert` near the existing seed helpers — add it once if it isn't already there:

```python
def _seed_alert(
    db_path: str,
    alert_id: str = "AL_20260427_0001",
    wallet: str = "0xwallet1",
    condition_id: str = "cond1",
    trade_hash: str = "0xtx_buy",
    price: float = 0.65,
    emitted_offset_hours: float = 72.0,
):
    """Insert a C1 alert row plus the corresponding BUY trade (so JOIN works)."""
    con = duckdb.connect(db_path)
    emitted = datetime.now(UTC) - timedelta(hours=emitted_offset_hours)
    # The BUY trade the alert references.
    con.execute(
        """INSERT OR REPLACE INTO trades (
            transaction_hash, proxy_wallet, condition_id, asset_id,
            side, size_usd, price, outcome, outcome_index,
            timestamp_unix, timestamp_ts, market_title, market_slug,
            event_slug, wallet_name
        ) VALUES (?, ?, ?, 'token1', 'BUY', 1500.0, ?, 'Yes', 0, ?, ?,
                  'Test Market', 'test-market', 'test-event', 'SharpTrader')""",
        [trade_hash, wallet, condition_id, price,
         int(emitted.timestamp()), emitted],
    )
    con.execute(
        """INSERT INTO alerts (
            alert_id, component, emitted_at, trade_hash, wallet_address,
            condition_id, side, size_usd, price, size_suggested_usd,
            shadow_mode, dedup_hash
        ) VALUES (?, 'C1', ?, ?, ?, ?, 'BUY', 1500.0, ?, 30.0, TRUE, ?)""",
        [alert_id, emitted, trade_hash, wallet, condition_id, price,
         f"dedup_{alert_id}"],
    )
    con.close()


class TestProcessExit:
    def _make_detector(self, db_path, settings):
        bot = MagicMock()
        bot.send_alert = AsyncMock(return_value=42)
        det = SharpMoneyDetector(bot=bot, settings=settings)
        det.db_path = db_path
        return det, bot

    def _sell_trade(self, **overrides):
        defaults = {
            "transaction_hash": "0xtx_sell",
            "proxy_wallet": "0xwallet1",
            "condition_id": "cond1",
            "side": "SELL",
            "size_usd": 3200.0,
            "price": 0.72,
            "outcome": "Yes",
            "timestamp_ts": datetime.now(UTC),
            "market_title": "Test Market",
            "event_slug": "test-event",
            "tier_a_confidence": 0.95,
            "wallet_name": "SharpTrader",
            "liquidity_usd": 5000.0,
        }
        defaults.update(overrides)
        return defaults

    def test_returns_false_when_size_below_floor(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_alert(db_path)
        det, bot = self._make_detector(db_path, settings)

        import asyncio
        result = asyncio.new_event_loop().run_until_complete(
            det._process_exit(self._sell_trade(size_usd=100.0))
        )
        assert result is False
        bot.send_alert.assert_not_called()
        # Dedup must NOT be marked when we early-returned for size.
        assert ("0xwallet1", "cond1", "Yes") not in det._exit_notified

    def test_returns_false_when_no_pending_alert(self, db_path, settings):
        _seed_wallet(db_path)
        # No alert seeded.
        det, bot = self._make_detector(db_path, settings)

        import asyncio
        result = asyncio.new_event_loop().run_until_complete(
            det._process_exit(self._sell_trade())
        )
        assert result is False
        bot.send_alert.assert_not_called()

    def test_returns_false_when_alert_resolved(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_alert(db_path, alert_id="AL_20260427_0001")
        # Mark resolved.
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO alert_outcomes (alert_id, resolution_outcome) "
            "VALUES (?, 'YES')",
            ["AL_20260427_0001"],
        )
        con.close()
        det, bot = self._make_detector(db_path, settings)

        import asyncio
        result = asyncio.new_event_loop().run_until_complete(
            det._process_exit(self._sell_trade())
        )
        assert result is False
        bot.send_alert.assert_not_called()

    def test_returns_false_when_outcome_mismatch(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_alert(db_path)  # BUY trade has outcome='Yes'
        det, bot = self._make_detector(db_path, settings)

        import asyncio
        result = asyncio.new_event_loop().run_until_complete(
            det._process_exit(self._sell_trade(outcome="No"))
        )
        assert result is False
        bot.send_alert.assert_not_called()

    def test_init_creates_empty_exit_notified_set(self, settings):
        bot = MagicMock()
        det = SharpMoneyDetector(bot=bot, settings=settings)
        assert det._exit_notified == set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestProcessExit -v`
Expected: FAIL — `AttributeError: 'SharpMoneyDetector' object has no attribute '_process_exit'` (or `_exit_notified`).

- [ ] **Step 3: Initialise the dedup set**

In `src/polybot/components/c1_sharp_money.py`, in `SharpMoneyDetector.__init__`, append a line at the end of the existing `__init__`:

```python
        self._exit_notified: set[tuple[str, str, str]] = set()
```

- [ ] **Step 4: Add the `_process_exit` method (early-return cases only)**

Insert this method directly below `_process_trade` (around line 400):

```python
    async def _process_exit(self, trade: dict) -> bool:
        """Emit an EXIT notification if SELL closes a pending C1 position.

        Returns True if a notification was emitted.
        """
        # Filter: SELL only (defensive — caller already routes by side).
        if trade["side"] != "SELL":
            return False

        # Filter: minimum size for EXIT.
        size_usd = float(trade["size_usd"])
        if size_usd < self.settings.C1_EXIT_SIZE_MIN_USD:
            return False

        wallet = trade["proxy_wallet"]
        condition_id = trade["condition_id"]
        sell_outcome = trade["outcome"]

        # In-memory dedup: one notification per (wallet, market, outcome).
        key = (wallet, condition_id, sell_outcome)
        if key in self._exit_notified:
            return False

        # Look up a pending C1 alert that matches outcome.
        pending = self._find_pending_buy_alert(wallet, condition_id, sell_outcome)
        if pending is None:
            return False

        # Happy path lands in Task 6.
        return False

    def _find_pending_buy_alert(
        self, wallet: str, condition_id: str, outcome: str
    ) -> dict | None:
        """Return the most recent unresolved C1 BUY alert on (wallet, market, outcome)."""
        con = db_connect(self.db_path, read_only=True)
        try:
            row = con.execute(
                """
                SELECT a.alert_id, t_buy.outcome, a.price AS entry_price,
                       a.size_suggested_usd, a.emitted_at
                FROM alerts a
                JOIN trades t_buy ON a.trade_hash = t_buy.transaction_hash
                LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
                WHERE a.component = 'C1'
                  AND a.wallet_address = ?
                  AND a.condition_id = ?
                  AND t_buy.outcome = ?
                  AND (ao.resolution_outcome IS NULL
                       OR ao.resolution_outcome = 'PENDING')
                ORDER BY a.emitted_at DESC LIMIT 1
                """,
                [wallet, condition_id, outcome],
            ).fetchone()
        finally:
            con.close()

        if row is None:
            return None
        return {
            "alert_id": row[0],
            "outcome": row[1],
            "entry_price": float(row[2]),
            "size_suggested_usd": float(row[3]) if row[3] is not None else None,
            "emitted_at": row[4],
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestProcessExit -v`
Expected: PASS (5/5).

- [ ] **Step 6: Commit**

```bash
git add src/polybot/components/c1_sharp_money.py tests/unit/test_c1_sharp_money.py
git commit -m "feat(c1): _process_exit skeleton (size floor, dedup, pending-alert lookup)"
```

---

## Task 6: `_process_exit` happy path — audit_log + Telegram + dedup mark

Wire the audit_log write, Telegram send (with topic routing by `SHADOW_MODE`), and dedup mark. Add error-handling for audit_log write and Telegram send.

**Files:**
- Modify: `src/polybot/components/c1_sharp_money.py`
- Test: `tests/unit/test_c1_sharp_money.py`

- [ ] **Step 1: Write the failing tests**

Append to `TestProcessExit` (same class as Task 5):

```python
    def test_emits_notification_on_match(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_alert(db_path, price=0.65, emitted_offset_hours=72.0)
        det, bot = self._make_detector(db_path, settings)

        import asyncio
        result = asyncio.new_event_loop().run_until_complete(
            det._process_exit(self._sell_trade(price=0.72, size_usd=3200.0))
        )

        assert result is True
        bot.send_alert.assert_called_once()
        # Topic routing: SHADOW_MODE default is True, so topic == "ops".
        topic, message = bot.send_alert.call_args.args[:2]
        assert topic == "ops"
        assert "EXIT_" in message
        assert "+10.8%" in message  # (0.72 - 0.65) / 0.65 ≈ 10.77 → "+10.8%"
        # Dedup is now marked.
        assert ("0xwallet1", "cond1", "Yes") in det._exit_notified

    def test_audit_log_row_persisted(self, db_path, settings):
        import json

        _seed_wallet(db_path)
        _seed_alert(db_path)
        det, bot = self._make_detector(db_path, settings)

        import asyncio
        asyncio.new_event_loop().run_until_complete(
            det._process_exit(self._sell_trade())
        )

        con = duckdb.connect(db_path)
        row = con.execute(
            "SELECT event_type, target, action, reason FROM audit_log "
            "WHERE event_type = 'position_exit'"
        ).fetchone()
        con.close()

        assert row is not None
        assert row[0] == "position_exit"
        assert row[1].startswith("EXIT_")
        assert row[2] == "0xwallet1"
        payload = json.loads(row[3])
        assert payload["alert_id"] == "AL_20260427_0001"
        assert payload["outcome"] == "Yes"
        assert payload["entry_price"] == 0.65
        assert payload["exit_price"] == 0.72
        assert payload["exit_size_usd"] == 3200.0
        assert abs(payload["pnl_pct"] - 10.77) < 0.05

    def test_dedup_blocks_second_sell(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_alert(db_path)
        det, bot = self._make_detector(db_path, settings)

        import asyncio
        loop = asyncio.new_event_loop()
        first = loop.run_until_complete(det._process_exit(self._sell_trade()))
        second = loop.run_until_complete(
            det._process_exit(self._sell_trade(transaction_hash="0xtx_sell2"))
        )
        assert first is True
        assert second is False
        assert bot.send_alert.call_count == 1

    def test_telegram_failure_does_not_mark_dedup(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_alert(db_path)
        det, bot = self._make_detector(db_path, settings)
        bot.send_alert = AsyncMock(side_effect=RuntimeError("telegram down"))

        import asyncio
        with pytest.raises(RuntimeError):
            asyncio.new_event_loop().run_until_complete(
                det._process_exit(self._sell_trade())
            )
        assert ("0xwallet1", "cond1", "Yes") not in det._exit_notified

    def test_alerts_topic_when_not_shadow(self, db_path, settings):
        settings.SHADOW_MODE = False
        _seed_wallet(db_path)
        _seed_alert(db_path)
        det, bot = self._make_detector(db_path, settings)

        import asyncio
        asyncio.new_event_loop().run_until_complete(
            det._process_exit(self._sell_trade())
        )

        topic = bot.send_alert.call_args.args[0]
        assert topic == "alerts"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestProcessExit -v`
Expected: 5 new failures (the 5 tests above), 5 prior tests still PASS.

- [ ] **Step 3: Add `_build_exit_keyboard` helper**

Add this module-level function in `src/polybot/components/c1_sharp_money.py` directly after `_build_inline_keyboard` (around line 153):

```python
def _build_exit_keyboard(event_slug: str | None, wallet: str):
    """Inline keyboard for an EXIT notification: market + wallet URL buttons only."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    market_url = (
        f"https://polymarket.com/event/{event_slug}"
        if event_slug
        else "https://polymarket.com"
    )
    wallet_url = f"https://polymarket.com/portfolio/{wallet}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Marché", url=market_url),
            InlineKeyboardButton("👤 Wallet", url=wallet_url),
        ],
    ])
```

- [ ] **Step 4: Implement the happy path**

Replace the `# Happy path lands in Task 6.\n        return False` block in `_process_exit` with:

```python
        # Compute pnl + time held.
        entry_price = pending["entry_price"]
        exit_price = float(trade["price"])
        pnl_pct = (exit_price - entry_price) / entry_price * 100 if entry_price else 0.0

        emitted_at = pending["emitted_at"]
        if emitted_at.tzinfo is None:
            emitted_at = emitted_at.replace(tzinfo=UTC)
        time_delta = datetime.now(UTC) - emitted_at
        time_held = _humanize_time_held(time_delta)

        # Allocate EXIT id and persist to audit_log (JSON in `reason`).
        import json

        payload = {
            "alert_id": pending["alert_id"],
            "condition_id": condition_id,
            "outcome": sell_outcome,
            "entry_price": round(entry_price, 4),
            "exit_price": round(exit_price, 4),
            "exit_size_usd": round(size_usd, 2),
            "pnl_pct": round(pnl_pct, 2),
            "time_held_h": round(time_delta.total_seconds() / 3600.0, 2),
        }

        def _insert_audit(con):
            exit_id_local = _next_exit_id(con)
            con.execute(
                "INSERT INTO audit_log (event_type, target, action, reason) "
                "VALUES ('position_exit', ?, ?, ?)",
                [exit_id_local, wallet, json.dumps(payload)],
            )
            return exit_id_local

        try:
            exit_id = db_write_with_retry(self.db_path, _insert_audit)
        except Exception:
            logger.exception("c1_exit_audit_failed", wallet=wallet[:12])
            # Fall back to a synthetic id so the user-facing notification still goes out.
            exit_id = f"EXIT_{datetime.now(UTC).strftime('%Y%m%d')}_xxxx"

        # Build the message + keyboard.
        tier_label = "A1" if float(trade.get("tier_a_confidence") or 0.5) >= 0.90 else "A2"
        message = _format_exit_message(
            exit_id=exit_id,
            wallet_name=trade.get("wallet_name") or wallet[:12],
            tier_label=tier_label,
            market_title=trade.get("market_title") or condition_id[:20],
            outcome=sell_outcome,
            entry_price=entry_price,
            exit_price=exit_price,
            exit_size_usd=size_usd,
            pnl_pct=pnl_pct,
            time_held=time_held,
        )
        keyboard = _build_exit_keyboard(
            event_slug=trade.get("event_slug"),
            wallet=wallet,
        )

        # Send Telegram first; mark dedup ONLY on success.
        topic = "ops" if self.settings.SHADOW_MODE else "alerts"
        await self.bot.send_alert(topic, message, reply_markup=keyboard)
        self._exit_notified.add(key)
        logger.info(
            "c1_exit_notified",
            exit_id=exit_id,
            wallet=wallet[:12],
            pnl_pct=round(pnl_pct, 2),
        )
        return True
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestProcessExit -v`
Expected: PASS (10/10) — 5 prior + 5 new.

- [ ] **Step 6: Commit**

```bash
git add src/polybot/components/c1_sharp_money.py tests/unit/test_c1_sharp_money.py
git commit -m "feat(c1): emit EXIT notification on SELL closing a pending position"
```

---

## Task 7: Wire SELL → `_process_exit` in `poll_once`

The dispatch change. `_fetch_new_trades` already returns SELL rows; only the BUY filter inside `_process_trade` discards them today.

**Files:**
- Modify: `src/polybot/components/c1_sharp_money.py`
- Test: `tests/unit/test_c1_sharp_money.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_c1_sharp_money.py`:

```python
class TestPollOnceDispatch:
    def test_sell_with_pending_alert_emits_exit(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_market(db_path)
        _seed_alert(db_path)  # pending C1 BUY YES @ 0.65
        # The SELL trade that should trigger the EXIT.
        _insert_trade(
            db_path,
            tx_hash="0xtx_sell",
            side="SELL",
            size_usd=3200.0,
            price=0.72,
        )

        bot = MagicMock()
        bot.send_alert = AsyncMock(return_value=42)
        det = SharpMoneyDetector(bot=bot, settings=settings)
        det.db_path = db_path
        det.last_check_ts = datetime.now(UTC) - timedelta(minutes=10)

        import asyncio
        asyncio.new_event_loop().run_until_complete(det.poll_once())

        bot.send_alert.assert_called_once()
        topic, message = bot.send_alert.call_args.args[:2]
        assert "Position Exit" in message

    def test_buy_path_unchanged(self, db_path, settings):
        _seed_wallet(db_path)
        _seed_bankroll(db_path)
        _seed_market(db_path)
        _insert_trade(db_path, size_usd=1500.0)  # plain BUY

        bot = MagicMock()
        bot.send_alert = AsyncMock(return_value=999)
        det = SharpMoneyDetector(bot=bot, settings=settings)
        det.db_path = db_path
        det.last_check_ts = datetime.now(UTC) - timedelta(minutes=5)

        import asyncio
        count = asyncio.new_event_loop().run_until_complete(det.poll_once())
        assert count == 1
        message = bot.send_alert.call_args.args[1]
        assert "C1 Sharp Money" in message  # BUY alert format, not EXIT
        assert "Position Exit" not in message
```

- [ ] **Step 2: Run tests to verify the SELL one fails**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestPollOnceDispatch -v`
Expected: `test_sell_with_pending_alert_emits_exit` FAILS (SELL trades currently discarded by `_process_trade`'s BUY-only filter, which short-circuits before our new code runs); `test_buy_path_unchanged` PASSES.

- [ ] **Step 3: Add the dispatch in `poll_once`**

Locate the existing loop in `poll_once` (around line 416) which reads:

```python
        for trade in trades:
            try:
                if await self._process_trade(trade):
                    emitted += 1
            except Exception:
                logger.exception(
                    "c1_trade_processing_error",
                    tx=trade.get("transaction_hash", "?")[:16],
                )
```

Replace with:

```python
        exits = 0
        for trade in trades:
            try:
                if trade["side"] == "BUY":
                    if await self._process_trade(trade):
                        emitted += 1
                elif trade["side"] == "SELL":
                    if await self._process_exit(trade):
                        exits += 1
            except Exception:
                logger.exception(
                    "c1_trade_processing_error",
                    tx=trade.get("transaction_hash", "?")[:16],
                )
```

Then update the closing log line in `poll_once` (currently `logger.info("c1_poll_complete", new_alerts=emitted, trades_checked=len(trades))`) to include exits:

```python
        if emitted or exits:
            logger.info(
                "c1_poll_complete",
                new_alerts=emitted,
                new_exits=exits,
                trades_checked=len(trades),
            )
        return emitted
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_c1_sharp_money.py::TestPollOnceDispatch -v`
Expected: PASS (2/2).

- [ ] **Step 5: Run full unit suite to confirm no regression**

Run: `uv run pytest tests/unit/ -q`
Expected: all tests PASS (existing + new).

- [ ] **Step 6: Commit**

```bash
git add src/polybot/components/c1_sharp_money.py tests/unit/test_c1_sharp_money.py
git commit -m "feat(c1): poll_once dispatches SELL trades to _process_exit"
```

---

## Task 8: Deploy + manual smoke test on VPS

The implementation is local-complete. Deploy and verify with a forged scenario (per the spec's acceptance criteria #2).

**Files:** none modified.

- [ ] **Step 1: Push commits to origin**

```bash
git push origin main
```

Expected: 6 commits pushed (Tasks 1–7).

- [ ] **Step 2: Rsync changed files to VPS**

```bash
rsync -Rv \
  src/polybot/config.py \
  src/polybot/components/c1_sharp_money.py \
  tests/unit/test_c1_sharp_money.py \
  tests/unit/test_config.py \
  polybot:/root/polybot/
```

Expected: 4 files transferred.

- [ ] **Step 3: Verify symbols landed**

```bash
ssh polybot 'grep -c "_process_exit\|_format_exit_message\|_next_exit_id\|_humanize_time_held\|C1_EXIT_SIZE_MIN_USD" /root/polybot/src/polybot/components/c1_sharp_money.py /root/polybot/src/polybot/config.py'
```

Expected: each file path returns a positive count (≥ 4 in c1_sharp_money.py, 1 in config.py).

- [ ] **Step 4: Restart the daemon**

```bash
ssh polybot 'systemctl restart polybot-bot.service && sleep 5 && systemctl is-active polybot-bot.service'
```

Expected: `active`.

- [ ] **Step 5: Forge an EXIT scenario**

Pick a recently-traded Tier A wallet (`0x44c1dfe432…` or `0x0c0e270cf8…` from earlier) and a market they bought into.

Run on the VPS to insert a synthetic pending alert + a synthetic SELL trade — replace `<COND>`, `<WALLET>`, `<TXBUY>`, `<TXSELL>` with real values:

```bash
ssh polybot '/root/polybot/.venv/bin/python -c "
import duckdb
from datetime import datetime, UTC, timedelta
con = duckdb.connect(\"/root/polybot/data/pm.duckdb\")
emitted = datetime.now(UTC) - timedelta(hours=72)
# 1) Synthetic BUY trade
con.execute(\"INSERT OR REPLACE INTO trades (transaction_hash, proxy_wallet, condition_id, asset_id, side, size_usd, price, outcome, outcome_index, timestamp_unix, timestamp_ts, market_title, market_slug, event_slug, wallet_name) VALUES (?, ?, ?, ?token1?, ?BUY?, 1500.0, 0.65, ?Yes?, 0, ?, ?, ?Smoke market?, ?smoke?, ?smoke?, ?smoke_wallet?)\", [\"0xsmoke_buy\", \"<WALLET>\", \"<COND>\", int(emitted.timestamp()), emitted])
# 2) Pending alert
con.execute(\"INSERT INTO alerts (alert_id, component, emitted_at, trade_hash, wallet_address, condition_id, side, size_usd, price, size_suggested_usd, shadow_mode, dedup_hash) VALUES (?SMOKE_AL_001?, ?C1?, ?, ?0xsmoke_buy?, ?<WALLET>?, ?<COND>?, ?BUY?, 1500.0, 0.65, 30.0, TRUE, ?smoke_dedup?)\", [emitted])
# 3) SELL trade arriving NOW
now = datetime.now(UTC)
con.execute(\"INSERT INTO trades (transaction_hash, proxy_wallet, condition_id, asset_id, side, size_usd, price, outcome, outcome_index, timestamp_unix, timestamp_ts, market_title, market_slug, event_slug, wallet_name) VALUES (?0xsmoke_sell?, ?<WALLET>?, ?<COND>?, ?token1?, ?SELL?, 3200.0, 0.72, ?Yes?, 0, ?, ?, ?Smoke market?, ?smoke?, ?smoke?, ?smoke_wallet?)\", [int(now.timestamp()), now])
con.close()
print(\"forged\")
"'
```

Wait up to 60 seconds (C1 polls every `C1_POLL_INTERVAL`, default 60s) and check `#ops` Telegram topic — an EXIT message should arrive.

- [ ] **Step 6: Verify audit_log row**

```bash
ssh polybot '/root/polybot/.venv/bin/python -c "
import duckdb
con = duckdb.connect(\"/root/polybot/data/pm.duckdb\", read_only=False)
rows = con.execute(\"SELECT target, action, reason FROM audit_log WHERE event_type = '\\''position_exit'\\'' ORDER BY id DESC LIMIT 1\").fetchall()
for r in rows: print(r)
"'
```

Expected: one row with `target=EXIT_YYYYMMDD_NNNN`, `action=<WALLET>`, `reason` containing JSON with `alert_id`, `entry_price=0.65`, `exit_price=0.72`, `pnl_pct≈10.77`.

- [ ] **Step 7: Verify dedup — second SELL produces no message**

Re-run the forged SELL insert (different `transaction_hash`, e.g. `0xsmoke_sell2`) and confirm no second message arrives in `#ops`.

- [ ] **Step 8: Cleanup forged rows**

```bash
ssh polybot '/root/polybot/.venv/bin/python -c "
import duckdb
con = duckdb.connect(\"/root/polybot/data/pm.duckdb\")
con.execute(\"DELETE FROM trades WHERE transaction_hash LIKE '\\''0xsmoke_%'\\''\")
con.execute(\"DELETE FROM alerts WHERE alert_id = '\\''SMOKE_AL_001'\\''\")
con.execute(\"DELETE FROM audit_log WHERE target LIKE '\\''EXIT_%_xxxx'\\'' OR (event_type = '\\''position_exit'\\'' AND action = '\\''<WALLET>'\\''  AND created_at > NOW() - INTERVAL 10 MINUTE)\")
con.close()
print(\"cleaned\")
"'
```

(Replace `<WALLET>` with the actual wallet used in step 5.)

- [ ] **Step 9: Done**

The feature is live. New EXIT notifications will land in `#ops` when any Tier A wallet sells a position that has a pending C1 alert with matching outcome.

---

## Self-review notes

**Spec coverage:** Each of the 8 acceptance tests in the spec maps to a test in the plan:
- Test 1 (EXIT on match) → Task 6 `test_emits_notification_on_match`
- Test 2 (no EXIT if resolved) → Task 5 `test_returns_false_when_alert_resolved`
- Test 3 (no EXIT if no alert) → Task 5 `test_returns_false_when_no_pending_alert`
- Test 4 (no EXIT on outcome mismatch) → Task 5 `test_returns_false_when_outcome_mismatch`
- Test 5 (dedup) → Task 6 `test_dedup_blocks_second_sell`
- Test 6 (size floor) → Task 5 `test_returns_false_when_size_below_floor`
- Test 7 (P&L computation) → Task 6 `test_emits_notification_on_match` asserts `+10.8%`
- Test 8 (message format) → Task 4 `TestFormatExitMessage` (4 sub-tests)

Acceptance criteria #1 (tests + suite green) → Task 7 step 5; #2 (manual VPS smoke) → Task 8 steps 5–7; #3 (audit_log row parseable) → Task 8 step 6.
