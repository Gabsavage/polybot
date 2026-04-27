# M9-1 CEX Hot Wallets + Migration 008 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up CEX hot wallet reference data and database tables for M9 funding detection.

**Architecture:** YAML config file → seed script → DuckDB tables. Two tables: `cex_hot_wallets` (reference data) and `cex_funding_map` (populated later by indexer). Seed script follows existing `seed_tier_a.py` pattern.

**Tech Stack:** DuckDB, PyYAML, pytest

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `migrations/008_m9_cex_funding.sql` | Schema for both tables + indexes |
| Create | `config/cex_hot_wallets.yaml` | Curated CEX hot wallet addresses on Polygon |
| Create | `scripts/seed_cex_hot_wallets.py` | Load YAML into DuckDB |
| Modify | `tests/unit/test_migrations.py` | Add M9 tables to migration test |
| Create | `tests/unit/test_seed_cex_hot_wallets.py` | Seed script tests |

---

### Task 1: Migration 008 — CEX tables

**Files:**
- Create: `migrations/008_m9_cex_funding.sql`
- Modify: `tests/unit/test_migrations.py`

- [ ] **Step 1: Write the migration SQL**

Create `migrations/008_m9_cex_funding.sql`:

```sql
-- M9: CEX funding detection tables

CREATE TABLE IF NOT EXISTS cex_hot_wallets (
    address VARCHAR PRIMARY KEY,
    exchange_name VARCHAR NOT NULL,
    label VARCHAR,
    verified BOOLEAN DEFAULT TRUE,
    source VARCHAR,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cex_funding_map (
    wallet_address VARCHAR PRIMARY KEY,
    funded_by VARCHAR,
    funded_by_hop2 VARCHAR,
    cex_source VARCHAR,
    deposit_address VARCHAR,
    confidence DECIMAL(3,2),
    method VARCHAR CHECK (method IN ('direct_hot_wallet', 'hop2_hot_wallet', 'deposit_address_match')),
    traced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cex_funding_deposit ON cex_funding_map (deposit_address);
CREATE INDEX IF NOT EXISTS idx_cex_funding_source ON cex_funding_map (cex_source);
```

- [ ] **Step 2: Update migration tests**

In `tests/unit/test_migrations.py`, add the M9 tables to the table list and update the migration count:

Change `M2_TABLES` definition to:

```python
M2_TABLES = M1_TABLES + ["indexer_state"]

M9_TABLES = M2_TABLES + ["cex_hot_wallets", "cex_funding_map"]
```

In `test_apply_migrations_creates_all_tables` and `test_apply_migrations_idempotent`, replace `M2_TABLES` references with `M9_TABLES`.

In `test_migrations_tracking`, change:
```python
assert len(applied) == 8
```
And add:
```python
assert applied[7][0] == "008_m9_cex_funding.sql"
```

- [ ] **Step 3: Run migration tests**

Run: `uv run pytest tests/unit/test_migrations.py -v`
Expected: 3 tests PASS

- [ ] **Step 4: Commit**

```bash
git add migrations/008_m9_cex_funding.sql tests/unit/test_migrations.py
git commit -m "feat(M9): add migration 008 — cex_hot_wallets + cex_funding_map tables"
```

---

### Task 2: CEX hot wallets YAML config

**Files:**
- Create: `config/cex_hot_wallets.yaml`

- [ ] **Step 1: Research CEX hot wallet addresses on Polygon**

Use web search to find publicly documented hot wallet addresses for each of the 10 exchanges on Polygon. Sources to check:
- Polygonscan labeled accounts pages
- Arkham Intelligence entity pages
- GitHub repos that aggregate CEX addresses (e.g., `0xBow/address-book`, `DefiLlama/DefiLlama-Adapters`)
- Dune analytics queries tagging CEX wallets on Polygon
- Blockchain analytics blog posts

Priority: Binance and Coinbase first (most critical for insider detection use cases).

Target: ~30-50 verified addresses total. Only hot wallets (high outgoing tx count), not deposit addresses.

- [ ] **Step 2: Create the YAML file**

Create `config/cex_hot_wallets.yaml` with the researched addresses:

```yaml
# CEX Hot Wallets on Polygon
# Source: Polygonscan labels + Arkham + Dune + public repos
# Last updated: 2026-04-26
# Maintenance: quarterly review

version: 1
last_updated: "2026-04-26"

exchanges:
  binance:
    name: "Binance"
    hot_wallets:
      - address: "0x..."
        label: "Binance Hot Wallet 1"
        verified: true
        source: "polygonscan"
      # ... more wallets from research
  coinbase:
    name: "Coinbase"
    hot_wallets:
      - address: "0x..."
        label: "Coinbase Commerce"
        verified: true
        source: "polygonscan"
  okx:
    name: "OKX"
    hot_wallets:
      - address: "0x..."
        label: "OKX Hot Wallet"
        verified: true
        source: "arkham"
  kraken:
    name: "Kraken"
    hot_wallets:
      - address: "0x..."
        label: "Kraken Hot Wallet"
        verified: true
        source: "arkham"
  bybit:
    name: "Bybit"
    hot_wallets:
      - address: "0x..."
        label: "Bybit Hot Wallet"
        verified: true
        source: "arkham"
  kucoin:
    name: "Kucoin"
    hot_wallets:
      - address: "0x..."
        label: "Kucoin Hot Wallet"
        verified: true
        source: "polygonscan"
  gate_io:
    name: "Gate.io"
    hot_wallets:
      - address: "0x..."
        label: "Gate.io Hot Wallet"
        verified: true
        source: "arkham"
  crypto_com:
    name: "Crypto.com"
    hot_wallets:
      - address: "0x..."
        label: "Crypto.com Hot Wallet"
        verified: true
        source: "polygonscan"
  gemini:
    name: "Gemini"
    hot_wallets:
      - address: "0x..."
        label: "Gemini Hot Wallet"
        verified: true
        source: "arkham"
  mexc:
    name: "MEXC"
    hot_wallets:
      - address: "0x..."
        label: "MEXC Hot Wallet"
        verified: true
        source: "arkham"
```

All addresses must be lowercase hex. Replace `0x...` placeholders with actual researched addresses.

- [ ] **Step 3: Validate YAML parses**

```bash
uv run python -c "import yaml; data = yaml.safe_load(open('config/cex_hot_wallets.yaml')); print(f'{sum(len(e[\"hot_wallets\"]) for e in data[\"exchanges\"].values())} wallets across {len(data[\"exchanges\"])} exchanges')"
```

Expected: `N wallets across 10 exchanges` where N >= 20.

- [ ] **Step 4: Commit**

```bash
git add config/cex_hot_wallets.yaml
git commit -m "feat(M9): add CEX hot wallet addresses for Polygon (10 exchanges)"
```

---

### Task 3: Seed script

**Files:**
- Create: `scripts/seed_cex_hot_wallets.py`

- [ ] **Step 1: Write the failing test file**

Create `tests/unit/test_seed_cex_hot_wallets.py`:

```python
from pathlib import Path

import duckdb
import pytest
import yaml

from polybot.db.migrations import apply_migrations


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


MOCK_YAML = {
    "version": 1,
    "last_updated": "2026-04-26",
    "exchanges": {
        "binance": {
            "name": "Binance",
            "hot_wallets": [
                {"address": "0xaaa1", "label": "Binance HW 1", "verified": True, "source": "polygonscan"},
                {"address": "0xaaa2", "label": "Binance HW 2", "verified": True, "source": "arkham"},
            ],
        },
        "coinbase": {
            "name": "Coinbase",
            "hot_wallets": [
                {"address": "0xbbb1", "label": "Coinbase HW", "verified": True, "source": "polygonscan"},
            ],
        },
        "okx": {
            "name": "OKX",
            "hot_wallets": [
                {"address": "0xCCC1", "label": "OKX HW 1", "verified": True, "source": "arkham"},
                {"address": "0xCCC2", "label": "OKX HW 2", "verified": False, "source": "dune"},
            ],
        },
    },
}


@pytest.fixture()
def yaml_path(tmp_path: Path) -> Path:
    path = tmp_path / "cex_hot_wallets.yaml"
    with open(path, "w") as f:
        yaml.dump(MOCK_YAML, f)
    return path


def test_load_wallets(yaml_path: Path, db_path: str):
    from scripts.seed_cex_hot_wallets import load_wallets, seed

    wallets = load_wallets(yaml_path)
    result = seed(db_path, wallets)

    assert result["count"] == 5

    con = duckdb.connect(db_path)
    rows = con.execute("SELECT COUNT(*) FROM cex_hot_wallets").fetchone()[0]
    con.close()
    assert rows == 5


def test_idempotent(yaml_path: Path, db_path: str):
    from scripts.seed_cex_hot_wallets import load_wallets, seed

    wallets = load_wallets(yaml_path)
    seed(db_path, wallets)
    seed(db_path, wallets)

    con = duckdb.connect(db_path)
    rows = con.execute("SELECT COUNT(*) FROM cex_hot_wallets").fetchone()[0]
    con.close()
    assert rows == 5


def test_lowercase_normalization(yaml_path: Path, db_path: str):
    from scripts.seed_cex_hot_wallets import load_wallets, seed

    wallets = load_wallets(yaml_path)
    seed(db_path, wallets)

    con = duckdb.connect(db_path)
    addresses = [row[0] for row in con.execute("SELECT address FROM cex_hot_wallets").fetchall()]
    con.close()

    for addr in addresses:
        assert addr == addr.lower(), f"Address not lowercase: {addr}"
    assert "0xccc1" in addresses
    assert "0xccc2" in addresses


def test_yaml_structure():
    yaml_path = Path(__file__).parents[2] / "config" / "cex_hot_wallets.yaml"
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    assert "exchanges" in data
    total = 0
    for key, exchange in data["exchanges"].items():
        assert "name" in exchange
        assert "hot_wallets" in exchange
        for wallet in exchange["hot_wallets"]:
            assert "address" in wallet
            assert wallet["address"].startswith("0x")
            assert wallet["address"] == wallet["address"].lower(), f"Address not lowercase in YAML: {wallet['address']}"
            total += 1
    assert total >= 20, f"Expected >= 20 wallets, got {total}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_seed_cex_hot_wallets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.seed_cex_hot_wallets'`

- [ ] **Step 3: Write the seed script**

Create `scripts/seed_cex_hot_wallets.py`:

```python
#!/usr/bin/env python3
"""Seed cex_hot_wallets table from YAML config."""

from pathlib import Path

import duckdb
import yaml

PROJECT_ROOT = Path(__file__).parents[1]
DB_PATH = PROJECT_ROOT / "data" / "pm.duckdb"
YAML_PATH = PROJECT_ROOT / "config" / "cex_hot_wallets.yaml"

UPSERT_SQL = """
INSERT INTO cex_hot_wallets (address, exchange_name, label, verified, source)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (address) DO UPDATE SET
    exchange_name = EXCLUDED.exchange_name,
    label = EXCLUDED.label,
    verified = EXCLUDED.verified,
    source = EXCLUDED.source
"""


def load_wallets(yaml_path: Path) -> list[dict]:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    wallets = []
    for _key, exchange in data["exchanges"].items():
        for wallet in exchange["hot_wallets"]:
            wallets.append({
                "address": wallet["address"].lower(),
                "exchange_name": exchange["name"],
                "label": wallet.get("label"),
                "verified": wallet.get("verified", True),
                "source": wallet.get("source"),
            })
    return wallets


def seed(db_path: str | Path, wallets: list[dict]) -> dict:
    con = duckdb.connect(str(db_path))
    for w in wallets:
        con.execute(UPSERT_SQL, [
            w["address"],
            w["exchange_name"],
            w["label"],
            w["verified"],
            w["source"],
        ])
    con.close()
    return {"count": len(wallets)}


def main():
    wallets = load_wallets(YAML_PATH)
    result = seed(DB_PATH, wallets)
    print(f"Loaded {result['count']} CEX hot wallet addresses")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_seed_cex_hot_wallets.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/seed_cex_hot_wallets.py tests/unit/test_seed_cex_hot_wallets.py
git commit -m "feat(M9): add seed script for CEX hot wallets"
```

---

### Task 4: Full verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/unit/ -v
```

Expected: All tests PASS (including existing tests — no regressions).

- [ ] **Step 2: Run lint**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: Clean.

- [ ] **Step 3: Seed the real database**

```bash
uv run python scripts/seed_cex_hot_wallets.py
```

Expected: `Loaded N CEX hot wallet addresses` where N >= 20.

- [ ] **Step 4: Verify data in DuckDB**

```bash
uv run python -c "
import duckdb
con = duckdb.connect('data/pm.duckdb')
print('=== cex_hot_wallets schema ===')
print(con.execute('DESCRIBE cex_hot_wallets').fetchall())
print()
print('=== cex_funding_map schema ===')
print(con.execute('DESCRIBE cex_funding_map').fetchall())
print()
print('=== Wallets per exchange ===')
for row in con.execute('SELECT exchange_name, COUNT(*) FROM cex_hot_wallets GROUP BY exchange_name ORDER BY COUNT(*) DESC').fetchall():
    print(f'  {row[0]}: {row[1]}')
print()
total = con.execute('SELECT COUNT(*) FROM cex_hot_wallets').fetchone()[0]
print(f'Total: {total} wallets')
con.close()
"
```

Expected: Both tables exist with correct schemas, >= 20 wallets distributed across exchanges.

- [ ] **Step 5: Final commit (if any lint fixes needed)**

```bash
git add -A
git commit -m "chore(M9): lint fixes for cex hot wallets"
```
