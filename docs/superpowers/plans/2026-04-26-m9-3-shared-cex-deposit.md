# M9-3 shared_cex_deposit Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 8th feature `shared_cex_deposit` to C2 informed trading detector — wallets sharing a CEX deposit address signal coordinated activity.

**Architecture:** New method `compute_shared_cex_deposit()` on `InformedTradingDetector` queries `cex_funding_map` joined with `trades_all` to find the most common deposit address among active wallets. Integrated into `compute_score()` as a boolean feature (ratio > 0.30). Alert format updated from /7 to /8.

**Tech Stack:** Python, DuckDB, existing `db_connect` pattern, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/polybot/components/c2_informed_trading.py` | Modify | Add `compute_shared_cex_deposit()`, update `compute_score()`, update `_format_alert()` |
| `tests/unit/test_c2_informed_trading.py` | Modify | Add 6 tests for the new feature |

---

### Task 1: Tests + Implementation for `compute_shared_cex_deposit()`

**Files:**
- Modify: `tests/unit/test_c2_informed_trading.py` (add new test class after line 420, before `class TestAlertFormat`)
- Modify: `src/polybot/components/c2_informed_trading.py:268` (add method before `compute_score`)

- [ ] **Step 1: Write failing tests for `compute_shared_cex_deposit`**

Add a helper function `_insert_cex_funding` and a new test class `TestSharedCexDeposit` in `tests/unit/test_c2_informed_trading.py`. Insert the new class **before** `class TestAlertFormat:` (line 422).

```python
def _insert_cex_funding(
    db_path: str,
    wallet: str,
    funded_by: str | None = None,
    funded_by_hop2: str | None = None,
    cex_source: str | None = None,
    deposit_address: str | None = None,
    confidence: float = 0.0,
    method: str | None = None,
):
    con = duckdb.connect(db_path)
    con.execute(
        "INSERT INTO cex_funding_map "
        "(wallet_address, funded_by, funded_by_hop2, cex_source, "
        "deposit_address, confidence, method) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [wallet, funded_by, funded_by_hop2, cex_source, deposit_address, confidence, method],
    )
    con.close()


class TestSharedCexDeposit:
    def test_above_threshold(self, c2, db_path):
        """2/3 wallets share deposit_address → ratio 0.67 > 0.30 → True."""
        _seed_market(db_path)
        now = datetime.now(UTC)
        for i, w in enumerate(["0xw1", "0xw2", "0xw3"]):
            _insert_trade_all(db_path, f"tx_cex_{i}", wallet=w, ts=now)
        _insert_cex_funding(
            db_path, "0xw1", funded_by="0xhot", funded_by_hop2="0xhot2",
            cex_source="Binance", deposit_address="0xdeposit1",
            confidence=0.9, method="hop2_hot_wallet",
        )
        _insert_cex_funding(
            db_path, "0xw2", funded_by="0xhot", funded_by_hop2="0xhot2",
            cex_source="Binance", deposit_address="0xdeposit1",
            confidence=0.9, method="hop2_hot_wallet",
        )
        ratio, source = c2.compute_shared_cex_deposit("cond1")
        assert ratio == pytest.approx(2 / 3, abs=0.01)
        assert source == "Binance"

    def test_below_threshold(self, c2, db_path):
        """1/5 wallets has deposit_address → ratio 0.20 < 0.30 → False."""
        _seed_market(db_path)
        now = datetime.now(UTC)
        for i in range(5):
            _insert_trade_all(db_path, f"tx_bt_{i}", wallet=f"0xbt{i}", ts=now)
        _insert_cex_funding(
            db_path, "0xbt0", funded_by="0xhot", funded_by_hop2="0xhot2",
            cex_source="Coinbase", deposit_address="0xdep_cb",
            confidence=0.9, method="hop2_hot_wallet",
        )
        ratio, source = c2.compute_shared_cex_deposit("cond1")
        assert ratio == pytest.approx(1 / 5, abs=0.01)
        assert source == "Coinbase"

    def test_no_funding_data(self, c2, db_path):
        """No cex_funding_map rows → ratio 0.0, source None."""
        _seed_market(db_path)
        now = datetime.now(UTC)
        _insert_trade_all(db_path, "tx_nf_0", wallet="0xnf1", ts=now)
        ratio, source = c2.compute_shared_cex_deposit("cond1")
        assert ratio == 0.0
        assert source is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_c2_informed_trading.py::TestSharedCexDeposit -v`
Expected: FAIL with `AttributeError: 'InformedTradingDetector' object has no attribute 'compute_shared_cex_deposit'`

- [ ] **Step 3: Implement `compute_shared_cex_deposit`**

Add this method to `src/polybot/components/c2_informed_trading.py` **after** `compute_single_dominance` (after line 268) and **before** the `# --- Scoring ---` comment (line 270):

```python
    def compute_shared_cex_deposit(self, condition_id: str) -> tuple[float, str | None]:
        """Ratio of active wallets sharing the most common CEX deposit address."""
        con = db_connect(self.db_path, read_only=True)
        total_row = con.execute(
            """
            SELECT COUNT(DISTINCT proxy_wallet)
            FROM trades_all
            WHERE condition_id = ? AND proxy_wallet IS NOT NULL
            """,
            [condition_id],
        ).fetchone()
        total = int(total_row[0]) if total_row else 0
        if total == 0:
            con.close()
            return 0.0, None

        row = con.execute(
            """
            WITH active_wallets AS (
                SELECT DISTINCT proxy_wallet
                FROM trades_all
                WHERE condition_id = ? AND proxy_wallet IS NOT NULL
            ),
            funded AS (
                SELECT aw.proxy_wallet, cfm.deposit_address, cfm.cex_source
                FROM active_wallets aw
                JOIN cex_funding_map cfm ON aw.proxy_wallet = cfm.wallet_address
                WHERE cfm.deposit_address IS NOT NULL
            )
            SELECT deposit_address, cex_source, COUNT(*) as cnt
            FROM funded
            GROUP BY deposit_address, cex_source
            ORDER BY cnt DESC
            LIMIT 1
            """,
            [condition_id],
        ).fetchone()
        con.close()

        if not row:
            return 0.0, None
        return row[2] / total, row[1]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_c2_informed_trading.py::TestSharedCexDeposit -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/polybot/components/c2_informed_trading.py tests/unit/test_c2_informed_trading.py
git commit -m "feat(M9-3): add compute_shared_cex_deposit method to C2"
```

---

### Task 2: Integrate into `compute_score()` + Test

**Files:**
- Modify: `src/polybot/components/c2_informed_trading.py:272-308` (update `compute_score`)
- Modify: `tests/unit/test_c2_informed_trading.py` (add test in `TestSharedCexDeposit`)

- [ ] **Step 1: Write failing test for score integration**

Add this test to the `TestSharedCexDeposit` class:

```python
    def test_in_compute_score(self, c2, db_path):
        """shared_cex_deposit fires → appears in features_passed, score incremented."""
        _seed_market(db_path)
        now = datetime.now(UTC)
        for i, w in enumerate(["0xsc1", "0xsc2", "0xsc3"]):
            _insert_trade_all(db_path, f"tx_sc_{i}", wallet=w, ts=now)
        _insert_cex_funding(
            db_path, "0xsc1", funded_by="0xhot", funded_by_hop2="0xhot2",
            cex_source="Binance", deposit_address="0xdep_sc",
            confidence=0.9, method="hop2_hot_wallet",
        )
        _insert_cex_funding(
            db_path, "0xsc2", funded_by="0xhot", funded_by_hop2="0xhot2",
            cex_source="Binance", deposit_address="0xdep_sc",
            confidence=0.9, method="hop2_hot_wallet",
        )
        result = c2.compute_score("cond1")
        assert "shared_cex_deposit" in result["features"]
        assert result["features"]["shared_cex_deposit"] is True
        assert "shared_cex_deposit" in result["features_passed"]
        assert result["raw_values"]["shared_cex_deposit"] == pytest.approx(2 / 3, abs=0.01)
        assert result["raw_values"]["shared_cex_deposit_source"] == "Binance"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_c2_informed_trading.py::TestSharedCexDeposit::test_in_compute_score -v`
Expected: FAIL with `KeyError: 'shared_cex_deposit'`

- [ ] **Step 3: Update `compute_score()` to include the 8th feature**

In `src/polybot/components/c2_informed_trading.py`, modify `compute_score()`:

**After line 280** (`dominance = self.compute_single_dominance(condition_id)`), add:

```python
        cex_deposit_ratio, cex_source = self.compute_shared_cex_deposit(condition_id)
```

**In the `features` dict** (after `"single_dominance": dominance > 0.60,`), add:

```python
            "shared_cex_deposit": cex_deposit_ratio > 0.30,
```

**In the `raw_values` dict** (after `"single_dominance": round(dominance, 4),`), add:

```python
            "shared_cex_deposit": round(cex_deposit_ratio, 4),
            "shared_cex_deposit_source": cex_source,
```

**Update the docstring** on line 273 from `"""Compute all 7 features + score for a market."""` to `"""Compute all 8 features + score for a market."""`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_c2_informed_trading.py::TestSharedCexDeposit -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/polybot/components/c2_informed_trading.py tests/unit/test_c2_informed_trading.py
git commit -m "feat(M9-3): integrate shared_cex_deposit as 8th feature in compute_score"
```

---

### Task 3: Update Alert Format + Tests

**Files:**
- Modify: `src/polybot/components/c2_informed_trading.py:498-557` (update `_format_alert`)
- Modify: `tests/unit/test_c2_informed_trading.py` (update existing test + add new test)

- [ ] **Step 1: Write failing tests for alert format changes**

**First**, update the existing `test_format_contains_sections` in `TestAlertFormat` class (line 422). The `raw_values` dict needs `shared_cex_deposit` and `shared_cex_deposit_source` keys, and the assertion must check `/8` instead of `/7`:

Replace the entire `test_format_contains_sections` method:

```python
    def test_format_contains_sections(self, c2, db_path):
        """C2 alert message contains all expected sections."""
        market = {
            "condition_id": "cond1",
            "title": "Will X happen?",
            "event_slug": "test-event",
            "vol_1h": 5000,
            "price_now": 0.65,
            "price_1h_ago": 0.55,
        }
        result = {
            "score": 5,
            "features_passed": ["fresh_wallets", "niche_market", "volume_zscore"],
            "raw_values": {
                "fresh_wallets": 0.62,
                "top5_concentration": 0.5,
                "time_to_event": None,
                "niche_market": True,
                "momentum_1h": 0.08,
                "volume_zscore": 4.2,
                "single_dominance": 0.3,
                "shared_cex_deposit": 0.0,
                "shared_cex_deposit_source": None,
            },
        }
        alignment = {"alignment_score": 1, "momentum_4h": 0.05, "direction": "BUY"}

        msg = c2._format_alert(
            market=market, result=result, alignment=alignment,
            risk_score=0.3, risk_category="MEDIUM", alert_id="AL_TEST_0001",
        )
        assert "C2" in msg
        assert "Will X happen?" in msg
        assert "5/8" in msg
        assert "Fresh wallets" in msg
        assert "Suit le mouvement" in msg
        assert "MEDIUM" in msg
        assert "AL_TEST_0001" in msg
```

**Second**, add a new test for the shared_cex_deposit feature line in the same `TestAlertFormat` class:

```python
    def test_format_shared_cex_line(self, c2, db_path):
        """shared_cex_deposit in features_passed → CEX deposit line with source."""
        market = {
            "condition_id": "cond1",
            "title": "Test",
            "event_slug": "test-event",
            "vol_1h": 1000,
            "price_now": 0.50,
            "price_1h_ago": 0.45,
        }
        result = {
            "score": 4,
            "features_passed": ["shared_cex_deposit"],
            "raw_values": {
                "fresh_wallets": 0.1,
                "top5_concentration": 0.3,
                "time_to_event": None,
                "niche_market": False,
                "momentum_1h": 0.01,
                "volume_zscore": 1.0,
                "single_dominance": 0.2,
                "shared_cex_deposit": 0.67,
                "shared_cex_deposit_source": "Binance",
            },
        }
        alignment = {"alignment_score": None, "momentum_4h": None, "direction": None}

        msg = c2._format_alert(
            market=market, result=result, alignment=alignment,
            risk_score=0.3, risk_category="MEDIUM", alert_id="AL_TEST_0002",
        )
        assert "CEX deposit partage" in msg
        assert "67%" in msg
        assert "(Binance)" in msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_c2_informed_trading.py::TestAlertFormat -v`
Expected: FAIL — `test_format_contains_sections` fails on `"5/8"` (still shows `/7`), `test_format_shared_cex_line` fails on missing `CEX deposit partage`.

- [ ] **Step 3: Update `_format_alert()` with new feature line and /8 score**

In `src/polybot/components/c2_informed_trading.py`:

**Add the shared_cex_deposit case** in the feature lines for-loop (after the `single_dominance` elif block, around line 520):

```python
            elif f == "shared_cex_deposit":
                src = raw.get("shared_cex_deposit_source", "")
                src_str = f" ({src})" if src else ""
                feature_lines.append(
                    f"  ✓ CEX deposit partage : {raw['shared_cex_deposit']:.0%}{src_str}"
                )
```

**Change the score label** on line 557 from:

```python
            f"🧬 Score : <b>{result['score']}/7</b>",
```

to:

```python
            f"🧬 Score : <b>{result['score']}/8</b>",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_c2_informed_trading.py::TestAlertFormat -v`
Expected: 2 passed

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/unit/test_c2_informed_trading.py -v`
Expected: All tests pass (previous 221 + 6 new = ~227, some existing tests may need raw_values update if they construct result dicts — check output carefully)

- [ ] **Step 6: Run lint**

Run: `uv run ruff check src/polybot/components/c2_informed_trading.py tests/unit/test_c2_informed_trading.py`
Run: `uv run ruff format --check src/polybot/components/c2_informed_trading.py tests/unit/test_c2_informed_trading.py`

Fix any issues.

- [ ] **Step 7: Commit**

```bash
git add src/polybot/components/c2_informed_trading.py tests/unit/test_c2_informed_trading.py
git commit -m "feat(M9-3): update alert format to /8, add shared_cex_deposit line"
```
