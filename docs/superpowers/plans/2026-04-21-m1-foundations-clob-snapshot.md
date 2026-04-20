# M1 — Foundations Infra + CLOB Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure repo for Phase B, set up DuckDB schema with 10 M1 tables + snapshot_universe, build config module, R2 storage wrapper, CLOB snapshot indexer writing Parquet to R2, healthcheck, validation script, and CI. VPS provisioning is last.

**Architecture:** Monorepo `src/polybot/` package with clear module boundaries: `config.py` (pydantic-settings), `db/` (DuckDB + migrations), `storage/` (R2 via boto3), `indexers/` (CLOB snapshot), plus scripts. Local-first: all paths configurable via .env, defaults to local `data/` and `logs/`. DuckDB file at configurable path, migrations applied via simple Python runner.

**Tech Stack:** Python 3.13, uv, DuckDB, polars, httpx, boto3 (R2), pydantic-settings, structlog, pytest, ruff, GitHub Actions CI.

---

## File Structure

```
polymarket-bot/                          # existing repo root
├── pyproject.toml                       # MODIFY: rename package, add deps
├── .env.example                         # MODIFY: add all M1 vars
├── .gitignore                           # MODIFY: add polybot-specific ignores
├── README.md                            # MODIFY: Phase B setup instructions
├── GATES.md                             # CREATE: decision gate log
├── .github/workflows/ci.yml             # CREATE: ruff + pytest
├── config/
│   └── tracked_wallets_seed.yaml        # CREATE: placeholder for M2
├── migrations/
│   └── 001_initial_schema.sql           # CREATE: 10 tables + snapshot_universe
├── src/
│   └── polybot/
│       ├── __init__.py                  # CREATE
│       ├── config.py                    # CREATE: pydantic-settings
│       ├── db/
│       │   ├── __init__.py              # CREATE
│       │   └── migrations.py            # CREATE: migration runner
│       ├── storage/
│       │   ├── __init__.py              # CREATE
│       │   └── r2.py                    # CREATE: boto3 R2 wrapper
│       ├── indexers/
│       │   ├── __init__.py              # CREATE
│       │   └── clob_snapshot.py         # CREATE: main indexer
│       └── healthcheck.py               # CREATE: connectivity checks
├── scripts/
│   ├── init_db.py                       # CREATE: apply migrations
│   ├── validate_snapshot.py             # CREATE: validate R2 snapshots
│   └── enrich_ground_truth.py           # KEEP: existing phase C
├── tests/
│   ├── __init__.py                      # CREATE
│   ├── conftest.py                      # CREATE: shared fixtures
│   ├── unit/
│   │   ├── __init__.py                  # CREATE
│   │   ├── test_config.py              # CREATE
│   │   ├── test_migrations.py          # CREATE
│   │   └── test_clob_snapshot.py       # CREATE
│   └── integration/
│       ├── __init__.py                  # CREATE
│       ├── test_r2.py                  # CREATE
│       └── test_clob_snapshot_e2e.py   # CREATE
├── notebooks/
│   └── phase_c/                         # MOVE: existing notebook
│       └── 01_pilote_iran_cluster.ipynb
├── data/                                # KEEP: existing
├── logs/                                # CREATE: local log dir
└── docs/                                # KEEP: existing
```

---

### Task 1: Repo Restructure + pyproject.toml

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Modify: `.env.example`
- Create: `GATES.md`
- Create: `src/polybot/__init__.py`
- Create: `src/polybot/db/__init__.py`
- Create: `src/polybot/storage/__init__.py`
- Create: `src/polybot/indexers/__init__.py`
- Create: `config/tracked_wallets_seed.yaml`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Move: `notebooks/01_pilote_iran_cluster.ipynb` → `notebooks/phase_c/`

- [ ] **Step 1: Move Phase C notebook**

```bash
mkdir -p notebooks/phase_c
git mv notebooks/01_pilote_iran_cluster.ipynb notebooks/phase_c/
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p src/polybot/db src/polybot/storage src/polybot/indexers
mkdir -p tests/unit tests/integration
mkdir -p config logs
```

- [ ] **Step 3: Create all `__init__.py` files**

`src/polybot/__init__.py`:
```python
"""Polymarket Bot — signals-only, human-in-the-loop."""
```

`src/polybot/db/__init__.py`, `src/polybot/storage/__init__.py`, `src/polybot/indexers/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`:
```python
```
(empty files)

- [ ] **Step 4: Rewrite `pyproject.toml`**

```toml
[project]
name = "polybot"
version = "0.1.0"
description = "Polymarket signals bot — CLOB snapshots, informed trading alerts, sharp money tracking"
requires-python = ">=3.13"
dependencies = [
    "duckdb>=1.0",
    "polars>=1.0",
    "pyarrow>=17.0",
    "httpx>=0.27",
    "tenacity>=9.0",
    "boto3>=1.35",
    "pydantic>=2.5",
    "pydantic-settings>=2.4",
    "structlog>=24.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.6",
]
phase-c = [
    "pandas",
    "jupyter",
    "matplotlib",
    "seaborn",
    "py-clob-client",
    "subgrounds",
    "dune-client",
    "requests",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/polybot"]

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: requires external services (R2, Polymarket APIs)",
]
```

- [ ] **Step 5: Update `.gitignore`**

```gitignore
# Environment
.env
.venv/

# Data (raw and processed only — ground_truth must be tracked)
data/raw/
data/processed/
data/*.duckdb
data/*.duckdb.wal

# Logs
logs/

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/

# Jupyter
.ipynb_checkpoints/

# OS
.DS_Store

# Claude Code
.claude/

# IDE
.vscode/
.idea/
```

- [ ] **Step 6: Update `.env.example`**

```env
# DuckDB
DUCKDB_PATH=data/pm.duckdb

# Cloudflare R2
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=polybot-snapshots
R2_ENDPOINT_URL=https://{account_id}.r2.cloudflarestorage.com

# Polymarket APIs (no auth needed for read)
GAMMA_API_URL=https://gamma-api.polymarket.com
CLOB_API_URL=https://clob.polymarket.com

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs
```

- [ ] **Step 7: Create `GATES.md`**

```markdown
# Decision Gates — Polymarket Bot

Format: bilan écrit obligatoire avec questions méthodologiques avant passage au milestone suivant.

---

## Gate M1 — Fondations infra + snapshot CLOB

Date :
Sessions passées sur M1 :
Lignes de code ajoutées :

### Questions méthodologiques

1. La stratégie snapshot R2 tient-elle le volume réel observé ? (Extrapoler 12 mois, vérifier < 10 GB free tier) — Réponse :
2. Y a-t-il eu un échec de snapshot sur les 48h de run ? Si oui, nature et mitigation ? — Réponse :
3. Le heartbeat fonctionne-t-il, ou bruit > rassurance ? — Réponse :
4. ADR à figer (choix VPS provider, format Parquet, partitionnement) ? — Réponse :

### Décisions prises
-

### Backlog créé (à traiter plus tard)
-

### ADRs ajoutés
-

### GO/NO-GO M2 :
```

- [ ] **Step 8: Create `config/tracked_wallets_seed.yaml`**

```yaml
# Tier A wallets — to be populated in M2
# Format:
#   - address: "0x..."
#     source: seed_manual
#     confidence: A1
#     notes: "Domer — WSJ identified"
wallets: []
```

- [ ] **Step 9: Sync uv dependencies**

```bash
uv sync
uv sync --extra dev
```

- [ ] **Step 10: Verify structure**

```bash
python -c "import polybot; print(polybot.__doc__)"
```
Expected: `Polymarket Bot — signals-only, human-in-the-loop.`

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "refactor: restructure repo for Phase B — polybot package, M1 deps, GATES.md"
```

---

### Task 2: DuckDB Schema + Migration Runner

**Files:**
- Create: `migrations/001_initial_schema.sql`
- Create: `src/polybot/db/migrations.py`
- Create: `scripts/init_db.py`
- Create: `tests/unit/test_migrations.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_migrations.py`:
```python
import tempfile
from pathlib import Path

import duckdb

from polybot.db.migrations import apply_migrations

M1_TABLES = [
    "markets",
    "trades",
    "wallets",
    "tracked_wallets",
    "alerts",
    "kill_switches",
    "audit_log",
    "rate_limit_counters",
    "bankroll_state",
    "resolution_risk_cache",
    "snapshot_universe",
]


def test_apply_migrations_creates_m1_tables(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(db_path), str(migrations_dir))

    con = duckdb.connect(str(db_path))
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    con.close()

    for table in M1_TABLES:
        assert table in tables, f"Missing table: {table}"


def test_apply_migrations_idempotent(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(db_path), str(migrations_dir))
    apply_migrations(str(db_path), str(migrations_dir))

    con = duckdb.connect(str(db_path))
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    con.close()

    for table in M1_TABLES:
        assert table in tables


def test_migrations_tracking(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(db_path), str(migrations_dir))

    con = duckdb.connect(str(db_path))
    applied = con.execute(
        "SELECT filename FROM _migrations ORDER BY applied_at"
    ).fetchall()
    con.close()

    assert len(applied) == 1
    assert applied[0][0] == "001_initial_schema.sql"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_migrations.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'polybot.db.migrations'`

- [ ] **Step 3: Write migration runner**

`src/polybot/db/migrations.py`:
```python
"""Lightweight migration runner for DuckDB — no external deps."""

from pathlib import Path

import duckdb


def apply_migrations(db_path: str, migrations_dir: str) -> list[str]:
    """Apply pending SQL migrations in filename order. Returns list of newly applied filenames."""
    con = duckdb.connect(db_path)

    con.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            filename VARCHAR PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    applied = {
        row[0] for row in con.execute("SELECT filename FROM _migrations").fetchall()
    }

    migrations_path = Path(migrations_dir)
    sql_files = sorted(migrations_path.glob("*.sql"))
    newly_applied = []

    for sql_file in sql_files:
        if sql_file.name in applied:
            continue
        sql = sql_file.read_text()
        con.execute(sql)
        con.execute("INSERT INTO _migrations (filename) VALUES (?)", [sql_file.name])
        newly_applied.append(sql_file.name)

    con.close()
    return newly_applied
```

- [ ] **Step 4: Write migration `001_initial_schema.sql`**

`migrations/001_initial_schema.sql`:
```sql
-- M1 initial schema — 10 tables + snapshot_universe
-- Ref: A_architecture_technique.md §3.2 + B_plan_developpement.md §3

CREATE TABLE IF NOT EXISTS markets (
    condition_id           VARCHAR PRIMARY KEY,
    question_id            VARCHAR,
    question_text          TEXT,
    description            TEXT,
    category               VARCHAR,
    tags                   VARCHAR[],
    outcomes               VARCHAR[],
    neg_risk               BOOLEAN,
    resolution_source      TEXT,
    resolution_date        TIMESTAMP,
    created_at             TIMESTAMP,
    closed_at              TIMESTAMP,
    volume_cumulative_usd  DECIMAL(18,2),
    liquidity_usd          DECIMAL(18,2),
    status                 VARCHAR,
    last_synced_at         TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trades (
    tx_hash                VARCHAR,
    log_index              INTEGER,
    block_number           BIGINT,
    block_timestamp        TIMESTAMP,
    condition_id           VARCHAR,
    token_id               VARCHAR,
    outcome_index          INTEGER,
    maker                  VARCHAR,
    taker                  VARCHAR,
    side                   VARCHAR,
    price                  DECIMAL(6,4),
    size_tokens            DECIMAL(18,6),
    size_usd               DECIMAL(18,2),
    fee                    DECIMAL(18,6),
    exchange               VARCHAR,
    PRIMARY KEY (tx_hash, log_index)
);

CREATE TABLE IF NOT EXISTS wallets (
    address                VARCHAR PRIMARY KEY,
    first_seen_at          TIMESTAMP,
    last_active_at         TIMESTAMP,
    total_trades           INTEGER,
    total_volume_usd       DECIMAL(18,2),
    is_proxy               BOOLEAN,
    resolved_eoa           VARCHAR,
    cluster_id             VARCHAR
);

CREATE TABLE IF NOT EXISTS tracked_wallets (
    address                VARCHAR PRIMARY KEY,
    tier                   VARCHAR,
    active                 BOOLEAN,
    source                 VARCHAR,
    added_at               TIMESTAMP,
    last_reviewed_at       TIMESTAMP,
    honeypot_flag          BOOLEAN,
    honeypot_score         DECIMAL(3,2),
    tier_a_confidence      DECIMAL(3,2),
    notes                  TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id               VARCHAR PRIMARY KEY,
    component              VARCHAR,
    emitted_at             TIMESTAMP,
    condition_id           VARCHAR,
    token_id               VARCHAR,
    side                   VARCHAR,
    price_at_alert         DECIMAL(6,4),
    size_recommended_usd   DECIMAL(18,2),
    bankroll_snapshot      DECIMAL(18,2),
    signal_source          VARCHAR,
    features               JSON,
    resolution_risk_score  DECIMAL(3,2),
    resolution_risk_label  VARCHAR,
    telegram_message_id    VARCHAR
);

CREATE TABLE IF NOT EXISTS kill_switches (
    component              VARCHAR PRIMARY KEY,
    state                  VARCHAR,
    set_at                 TIMESTAMP,
    reason                 TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id                 BIGINT PRIMARY KEY,
    timestamp              TIMESTAMP,
    level                  VARCHAR,
    component              VARCHAR,
    event                  VARCHAR,
    details                JSON
);

CREATE SEQUENCE IF NOT EXISTS audit_log_seq START 1;

CREATE TABLE IF NOT EXISTS rate_limit_counters (
    component              VARCHAR,
    hour_bucket            TIMESTAMP,
    count                  INTEGER,
    PRIMARY KEY (component, hour_bucket)
);

CREATE TABLE IF NOT EXISTS bankroll_state (
    updated_at             TIMESTAMP PRIMARY KEY,
    amount_eur             DECIMAL(18,2),
    note                   TEXT
);

CREATE TABLE IF NOT EXISTS resolution_risk_cache (
    condition_id           VARCHAR PRIMARY KEY,
    llm_score              DECIMAL(3,2),
    llm_reasons            TEXT[],
    llm_red_flags          TEXT[],
    llm_model_version      VARCHAR,
    computed_at            TIMESTAMP
);

-- Snapshot universe: which markets to snapshot hourly
CREATE TABLE IF NOT EXISTS snapshot_universe (
    condition_id           VARCHAR,
    token_id_yes           VARCHAR,
    token_id_no            VARCHAR,
    question_text          TEXT,
    volume_24h_usd         DECIMAL(18,2),
    refreshed_at           TIMESTAMP,
    PRIMARY KEY (condition_id)
);
```

- [ ] **Step 5: Write `scripts/init_db.py`**

```python
#!/usr/bin/env python3
"""Initialize DuckDB with all pending migrations."""

import sys
from pathlib import Path

# Add src to path for direct script execution
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from polybot.db.migrations import apply_migrations


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Apply DuckDB migrations")
    parser.add_argument(
        "--db", default="data/pm.duckdb", help="Path to DuckDB file"
    )
    parser.add_argument(
        "--migrations", default="migrations", help="Path to migrations directory"
    )
    args = parser.parse_args()

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    applied = apply_migrations(args.db, args.migrations)

    if applied:
        print(f"Applied {len(applied)} migration(s): {', '.join(applied)}")
    else:
        print("No new migrations to apply.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_migrations.py -v
```
Expected: 3 tests PASS

- [ ] **Step 7: Run init_db.py manually to verify**

```bash
uv run python scripts/init_db.py --db data/pm.duckdb
uv run python -c "import duckdb; con = duckdb.connect('data/pm.duckdb'); print([r[0] for r in con.execute('SHOW TABLES').fetchall()]); con.close()"
```
Expected: list of 11 tables (10 M1 + snapshot_universe) + `_migrations`

- [ ] **Step 8: Commit**

```bash
git add migrations/ src/polybot/db/ scripts/init_db.py tests/unit/test_migrations.py
git commit -m "feat(db): DuckDB schema 001 — 10 M1 tables + snapshot_universe + migration runner"
```

---

### Task 3: Config Module (pydantic-settings)

**Files:**
- Create: `src/polybot/config.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_config.py`:
```python
from pathlib import Path

from polybot.config import Settings


def test_settings_defaults():
    """Settings should work with minimal env vars (all have defaults or are optional)."""
    settings = Settings(
        R2_ACCOUNT_ID="test-account",
        R2_ACCESS_KEY_ID="test-key",
        R2_SECRET_ACCESS_KEY="test-secret",
    )
    assert settings.DUCKDB_PATH == Path("data/pm.duckdb")
    assert settings.R2_BUCKET_NAME == "polybot-snapshots"
    assert settings.GAMMA_API_URL == "https://gamma-api.polymarket.com"
    assert settings.CLOB_API_URL == "https://clob.polymarket.com"
    assert settings.LOG_LEVEL == "INFO"


def test_settings_r2_endpoint_url():
    settings = Settings(
        R2_ACCOUNT_ID="abc123",
        R2_ACCESS_KEY_ID="key",
        R2_SECRET_ACCESS_KEY="secret",
    )
    assert settings.r2_endpoint_url == "https://abc123.r2.cloudflarestorage.com"


def test_settings_migrations_dir():
    settings = Settings(
        R2_ACCOUNT_ID="test",
        R2_ACCESS_KEY_ID="key",
        R2_SECRET_ACCESS_KEY="secret",
    )
    assert settings.MIGRATIONS_DIR == Path("migrations")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write config module**

`src/polybot/config.py`:
```python
"""Configuration via pydantic-settings — loads from .env file."""

from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DuckDB
    DUCKDB_PATH: Path = Path("data/pm.duckdb")
    MIGRATIONS_DIR: Path = Path("migrations")

    # Cloudflare R2
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str = "polybot-snapshots"

    # Polymarket APIs
    GAMMA_API_URL: str = "https://gamma-api.polymarket.com"
    CLOB_API_URL: str = "https://clob.polymarket.com"

    # Snapshot config
    SNAPSHOT_TOP_N: int = 150
    SNAPSHOT_MIN_VOLUME_24H: float = 50_000.0
    SNAPSHOT_UNIVERSE_REFRESH_HOURS: int = 6

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = Path("logs")

    @computed_field
    @property
    def r2_endpoint_url(self) -> str:
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_config.py -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/polybot/config.py tests/unit/test_config.py
git commit -m "feat(config): pydantic-settings config module with R2, DuckDB, API defaults"
```

---

### Task 4: Cloudflare R2 Storage Wrapper

**Files:**
- Create: `src/polybot/storage/r2.py`
- Create: `tests/integration/test_r2.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the failing test (unit-level, no real R2)**

`tests/unit/test_r2_interface.py` — just test that the class instantiates and has the right methods:

Actually, for R2 we need real integration tests. Let's write both a unit test (mocked) and an integration test.

`tests/conftest.py`:
```python
import pytest

from polybot.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Settings with test defaults. Override R2 creds via env or parametrize."""
    return Settings(
        R2_ACCOUNT_ID="test",
        R2_ACCESS_KEY_ID="test-key",
        R2_SECRET_ACCESS_KEY="test-secret",
        DUCKDB_PATH="data/test.duckdb",
    )
```

`tests/integration/test_r2.py`:
```python
import io

import pytest

from polybot.config import Settings
from polybot.storage.r2 import R2Client


@pytest.fixture
def r2_settings() -> Settings:
    """Load real R2 credentials from .env."""
    return Settings()


@pytest.fixture
def r2(r2_settings: Settings) -> R2Client:
    return R2Client(r2_settings)


@pytest.mark.integration
def test_upload_and_read_back(r2: R2Client):
    key = "_test/integration_test.txt"
    data = b"hello from polybot integration test"

    r2.upload_bytes(key, data)
    result = r2.get_bytes(key)
    assert result == data

    # Cleanup
    r2.delete_object(key)


@pytest.mark.integration
def test_list_objects(r2: R2Client):
    key = "_test/list_test.txt"
    r2.upload_bytes(key, b"test")

    keys = r2.list_keys(prefix="_test/")
    assert key in keys

    r2.delete_object(key)
```

- [ ] **Step 2: Write R2 client**

`src/polybot/storage/r2.py`:
```python
"""Minimal R2 (S3-compatible) client for Parquet snapshot storage."""

import io

import boto3

from polybot.config import Settings


class R2Client:
    def __init__(self, settings: Settings):
        self._bucket = settings.R2_BUCKET_NAME
        self._s3 = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )

    def upload_bytes(self, key: str, data: bytes) -> None:
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=data)

    def upload_parquet(self, key: str, data: bytes) -> None:
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType="application/octet-stream",
        )

    def get_bytes(self, key: str) -> bytes:
        response = self._s3.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def list_keys(self, prefix: str = "") -> list[str]:
        response = self._s3.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
        if "Contents" not in response:
            return []
        return [obj["Key"] for obj in response["Contents"]]

    def delete_object(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)
```

- [ ] **Step 3: Run integration test (requires VPN + real R2 creds in .env)**

```bash
uv run pytest tests/integration/test_r2.py -v -m integration
```
Expected: 2 tests PASS (skip if no R2 creds configured)

- [ ] **Step 4: Commit**

```bash
git add src/polybot/storage/r2.py tests/conftest.py tests/integration/test_r2.py
git commit -m "feat(storage): R2 client wrapper — upload, read, list, delete"
```

---

### Task 5: Structured Logging Setup

**Files:**
- Create: `src/polybot/logging.py`

- [ ] **Step 1: Write logging setup**

`src/polybot/logging.py`:
```python
"""Structured logging via structlog."""

import logging
from pathlib import Path

import structlog


def setup_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    """Configure structlog with JSON file output + human-readable console."""
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if not log_dir else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 2: Commit**

```bash
git add src/polybot/logging.py
git commit -m "feat(logging): structlog setup with JSON and console renderers"
```

---

### Task 6: CLOB Snapshot Indexer

**Files:**
- Create: `src/polybot/indexers/clob_snapshot.py`
- Create: `tests/unit/test_clob_snapshot.py`
- Create: `tests/integration/test_clob_snapshot_e2e.py`

This is the biggest task. We split into sub-steps: (a) fetch top-N markets from Gamma, (b) fetch order book from CLOB, (c) build Polars DataFrame, (d) write Parquet to R2, (e) refresh_snapshot_universe job.

- [ ] **Step 1: Write unit tests for market selection logic**

`tests/unit/test_clob_snapshot.py`:
```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import polars as pl
import pytest

from polybot.indexers.clob_snapshot import (
    build_snapshot_row,
    filter_top_markets,
    parse_order_book,
)


def test_filter_top_markets():
    """Filter markets by volume threshold and return top N."""
    markets = [
        {"condition_id": "a", "volume_num_24hr": 100_000, "clobTokenIds": '["tok_a_yes","tok_a_no"]', "question": "Q1"},
        {"condition_id": "b", "volume_num_24hr": 30_000, "clobTokenIds": '["tok_b_yes","tok_b_no"]', "question": "Q2"},
        {"condition_id": "c", "volume_num_24hr": 60_000, "clobTokenIds": '["tok_c_yes","tok_c_no"]', "question": "Q3"},
    ]
    result = filter_top_markets(markets, top_n=2, min_volume=50_000)
    assert len(result) == 2
    assert result[0]["condition_id"] == "a"
    assert result[1]["condition_id"] == "c"


def test_parse_order_book_basic():
    """Parse CLOB /book response into best bid/ask/depth."""
    book = {
        "bids": [
            {"price": "0.55", "size": "1000"},
            {"price": "0.54", "size": "2000"},
            {"price": "0.53", "size": "500"},
        ],
        "asks": [
            {"price": "0.57", "size": "800"},
            {"price": "0.58", "size": "1500"},
            {"price": "0.60", "size": "300"},
        ],
    }
    result = parse_order_book(book)
    assert result["best_bid"] == 0.55
    assert result["best_ask"] == 0.57
    assert abs(result["midpoint"] - 0.56) < 0.001
    assert abs(result["spread"] - 0.02) < 0.001


def test_parse_order_book_empty():
    """Empty book returns None values."""
    result = parse_order_book({"bids": [], "asks": []})
    assert result["best_bid"] is None
    assert result["best_ask"] is None


def test_build_snapshot_row():
    """Build a complete row for the Parquet output."""
    book_data = {
        "best_bid": 0.55,
        "best_ask": 0.57,
        "midpoint": 0.56,
        "spread": 0.02,
        "bid_depth_1pct": 3000.0,
        "ask_depth_1pct": 2300.0,
    }
    ts = datetime(2026, 4, 21, 14, 0, 0, tzinfo=timezone.utc)
    row = build_snapshot_row("cond_1", "tok_yes", ts, book_data, volume_1h=15000.0)
    assert row["condition_id"] == "cond_1"
    assert row["token_id"] == "tok_yes"
    assert row["snapshot_ts"] == ts
    assert row["best_bid"] == 0.55
    assert row["volume_1h"] == 15000.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_clob_snapshot.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement clob_snapshot.py**

`src/polybot/indexers/clob_snapshot.py`:
```python
"""CLOB snapshot indexer — fetches order books for top markets, writes Parquet to R2."""

import json
from datetime import datetime, timezone

import httpx
import polars as pl
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from polybot.config import Settings
from polybot.storage.r2 import R2Client

logger = structlog.get_logger()


def filter_top_markets(
    markets: list[dict], top_n: int, min_volume: float
) -> list[dict]:
    """Filter markets by volume_24h > min_volume, return top N sorted by volume desc."""
    filtered = [
        m for m in markets
        if (m.get("volume_num_24hr") or 0) >= min_volume
    ]
    filtered.sort(key=lambda m: m.get("volume_num_24hr", 0), reverse=True)
    return filtered[:top_n]


def parse_order_book(book: dict) -> dict:
    """Extract best bid/ask, midpoint, spread, and depth from CLOB /book response."""
    bids = book.get("bids") or []
    asks = book.get("asks") or []

    best_bid = float(bids[0]["price"]) if bids else None
    best_ask = float(asks[0]["price"]) if asks else None

    midpoint = None
    spread = None
    if best_bid is not None and best_ask is not None:
        midpoint = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

    # Depth within 1% of midpoint
    bid_depth_1pct = 0.0
    ask_depth_1pct = 0.0
    if midpoint:
        bid_threshold = midpoint * 0.99
        ask_threshold = midpoint * 1.01
        bid_depth_1pct = sum(
            float(b["size"]) for b in bids if float(b["price"]) >= bid_threshold
        )
        ask_depth_1pct = sum(
            float(a["size"]) for a in asks if float(a["price"]) <= ask_threshold
        )

    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "midpoint": midpoint,
        "spread": spread,
        "bid_depth_1pct": bid_depth_1pct,
        "ask_depth_1pct": ask_depth_1pct,
    }


def build_snapshot_row(
    condition_id: str,
    token_id: str,
    snapshot_ts: datetime,
    book_data: dict,
    volume_1h: float | None = None,
) -> dict:
    """Build a single row for the Parquet snapshot."""
    return {
        "condition_id": condition_id,
        "token_id": token_id,
        "snapshot_ts": snapshot_ts,
        "best_bid": book_data["best_bid"],
        "best_ask": book_data["best_ask"],
        "midpoint": book_data["midpoint"],
        "spread": book_data["spread"],
        "bid_depth_1pct": book_data["bid_depth_1pct"],
        "ask_depth_1pct": book_data["ask_depth_1pct"],
        "volume_1h": volume_1h,
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=30))
async def fetch_top_markets(
    client: httpx.AsyncClient, gamma_url: str, limit: int = 500
) -> list[dict]:
    """Fetch markets from Gamma API sorted by 24h volume. Paginate to get enough."""
    all_markets: list[dict] = []
    offset = 0
    page_size = 100

    while len(all_markets) < limit:
        resp = await client.get(
            f"{gamma_url}/markets",
            params={
                "active": "true",
                "closed": "false",
                "limit": page_size,
                "offset": offset,
                "order": "volume24hr",
                "ascending": "false",
            },
        )
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        all_markets.extend(page)
        offset += page_size

    return all_markets


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=30))
async def fetch_order_book(
    client: httpx.AsyncClient, clob_url: str, token_id: str
) -> dict:
    """Fetch order book for a single token from CLOB API."""
    resp = await client.get(f"{clob_url}/book", params={"token_id": token_id})
    resp.raise_for_status()
    return resp.json()


async def run_snapshot(settings: Settings, r2: R2Client) -> int:
    """Run one snapshot cycle: fetch books for universe, write Parquet to R2.

    Returns number of rows written.
    """
    import duckdb

    now = datetime.now(timezone.utc)

    # Load universe from DuckDB
    con = duckdb.connect(str(settings.DUCKDB_PATH), read_only=True)
    universe = con.execute(
        "SELECT condition_id, token_id_yes, token_id_no FROM snapshot_universe"
    ).fetchall()
    con.close()

    if not universe:
        logger.warning("snapshot_universe is empty — run refresh_snapshot_universe first")
        return 0

    rows: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for condition_id, token_yes, token_no in universe:
            for token_id in [token_yes, token_no]:
                try:
                    book = await fetch_order_book(client, settings.CLOB_API_URL, token_id)
                    book_data = parse_order_book(book)
                    row = build_snapshot_row(condition_id, token_id, now, book_data)
                    rows.append(row)
                except Exception:
                    logger.exception(
                        "failed to fetch book",
                        condition_id=condition_id,
                        token_id=token_id,
                    )

    if not rows:
        logger.error("no rows collected — skipping Parquet write")
        return 0

    df = pl.DataFrame(rows)
    parquet_bytes = df.write_parquet(compression="zstd")

    key = f"snapshots/{now.strftime('%Y-%m-%d')}/{now.strftime('%H')}.parquet"
    r2.upload_parquet(key, parquet_bytes)
    logger.info("snapshot written", key=key, rows=len(rows))

    return len(rows)


async def refresh_snapshot_universe(settings: Settings) -> int:
    """Refresh the snapshot_universe table from Gamma API top markets.

    Returns number of markets in universe.
    """
    import duckdb

    async with httpx.AsyncClient(timeout=30.0) as client:
        all_markets = await fetch_top_markets(client, settings.GAMMA_API_URL)

    selected = filter_top_markets(
        all_markets, settings.SNAPSHOT_TOP_N, settings.SNAPSHOT_MIN_VOLUME_24H
    )

    if not selected:
        logger.warning("no markets passed volume filter")
        return 0

    now = datetime.now(timezone.utc)
    con = duckdb.connect(str(settings.DUCKDB_PATH))

    con.execute("DELETE FROM snapshot_universe")
    for m in selected:
        clob_token_ids = json.loads(m.get("clobTokenIds", "[]"))
        if len(clob_token_ids) < 2:
            continue
        con.execute(
            """INSERT INTO snapshot_universe
               (condition_id, token_id_yes, token_id_no, question_text, volume_24h_usd, refreshed_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                m["condition_id"],
                clob_token_ids[0],
                clob_token_ids[1],
                m.get("question", ""),
                m.get("volume_num_24hr", 0),
                now,
            ],
        )

    count = con.execute("SELECT COUNT(*) FROM snapshot_universe").fetchone()[0]
    con.close()

    logger.info("snapshot_universe refreshed", count=count)
    return count


async def main():
    """CLI entrypoint: run snapshot or refresh universe."""
    import argparse

    from polybot.logging import setup_logging

    parser = argparse.ArgumentParser(description="CLOB snapshot indexer")
    parser.add_argument(
        "action",
        choices=["snapshot", "refresh-universe"],
        help="Action to perform",
    )
    args = parser.parse_args()

    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)

    if args.action == "refresh-universe":
        count = await refresh_snapshot_universe(settings)
        print(f"Universe refreshed: {count} markets")
    elif args.action == "snapshot":
        r2 = R2Client(settings)
        rows = await run_snapshot(settings, r2)
        print(f"Snapshot complete: {rows} rows")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

- [ ] **Step 4: Run unit tests**

```bash
uv run pytest tests/unit/test_clob_snapshot.py -v
```
Expected: 4 tests PASS

- [ ] **Step 5: Commit unit-tested core**

```bash
git add src/polybot/indexers/clob_snapshot.py tests/unit/test_clob_snapshot.py
git commit -m "feat(indexer): CLOB snapshot indexer — market selection, book parsing, R2 write"
```

- [ ] **Step 6: Write integration test**

`tests/integration/test_clob_snapshot_e2e.py`:
```python
"""End-to-end test: refresh universe then run snapshot, verify Parquet on R2."""

import asyncio
from pathlib import Path

import polars as pl
import pytest

from polybot.config import Settings
from polybot.indexers.clob_snapshot import refresh_snapshot_universe, run_snapshot
from polybot.storage.r2 import R2Client


@pytest.fixture
def live_settings(tmp_path: Path) -> Settings:
    """Settings with real APIs + temp DuckDB."""
    from polybot.db.migrations import apply_migrations

    db_path = tmp_path / "test.duckdb"
    apply_migrations(str(db_path), "migrations")
    return Settings(DUCKDB_PATH=db_path)


@pytest.fixture
def r2(live_settings: Settings) -> R2Client:
    return R2Client(live_settings)


@pytest.mark.integration
def test_refresh_universe_populates_markets(live_settings: Settings):
    """Refresh universe from real Gamma API — should get > 0 markets."""
    count = asyncio.run(refresh_snapshot_universe(live_settings))
    assert count > 0
    assert count <= live_settings.SNAPSHOT_TOP_N


@pytest.mark.integration
def test_full_snapshot_cycle(live_settings: Settings, r2: R2Client):
    """Full cycle: refresh universe → snapshot → verify Parquet on R2."""
    # Step 1: refresh universe
    count = asyncio.run(refresh_snapshot_universe(live_settings))
    assert count > 0

    # Step 2: run snapshot
    rows = asyncio.run(run_snapshot(live_settings, r2))
    assert rows > 0

    # Step 3: verify Parquet exists on R2
    keys = r2.list_keys(prefix="snapshots/")
    assert len(keys) > 0

    # Step 4: read back and check schema
    parquet_data = r2.get_bytes(keys[-1])
    df = pl.read_parquet(parquet_data)
    expected_cols = {
        "condition_id", "token_id", "snapshot_ts", "best_bid", "best_ask",
        "midpoint", "spread", "bid_depth_1pct", "ask_depth_1pct", "volume_1h",
    }
    assert set(df.columns) == expected_cols
    assert len(df) > 100  # expect ~2 * universe_count rows

    # Cleanup test snapshots
    for key in keys:
        if "snapshots/" in key:
            r2.delete_object(key)
```

- [ ] **Step 7: Run integration test (requires VPN + .env configured)**

```bash
uv run pytest tests/integration/test_clob_snapshot_e2e.py -v -m integration
```
Expected: 2 tests PASS

- [ ] **Step 8: Commit integration tests**

```bash
git add tests/integration/test_clob_snapshot_e2e.py
git commit -m "test(indexer): integration tests for CLOB snapshot end-to-end cycle"
```

---

### Task 7: Healthcheck

**Files:**
- Create: `src/polybot/healthcheck.py`

- [ ] **Step 1: Write healthcheck**

`src/polybot/healthcheck.py`:
```python
"""Healthcheck — verify DuckDB connectivity, R2 access, and last snapshot freshness."""

from datetime import datetime, timezone

import duckdb
import structlog

from polybot.config import Settings
from polybot.storage.r2 import R2Client

logger = structlog.get_logger()


def check_duckdb(settings: Settings) -> tuple[bool, str]:
    """Check DuckDB is accessible and has expected tables."""
    try:
        con = duckdb.connect(str(settings.DUCKDB_PATH), read_only=True)
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        con.close()
        if "markets" not in tables:
            return False, f"Missing expected tables. Found: {tables}"
        return True, f"{len(tables)} tables OK"
    except Exception as e:
        return False, f"DuckDB error: {e}"


def check_r2(r2: R2Client) -> tuple[bool, str]:
    """Check R2 bucket is accessible."""
    try:
        keys = r2.list_keys(prefix="snapshots/")
        return True, f"R2 OK — {len(keys)} snapshot files"
    except Exception as e:
        return False, f"R2 error: {e}"


def check_last_snapshot(r2: R2Client) -> tuple[bool, str]:
    """Check that the most recent snapshot is < 2 hours old."""
    try:
        keys = r2.list_keys(prefix="snapshots/")
        if not keys:
            return False, "No snapshots found on R2"
        latest = sorted(keys)[-1]
        # Parse date from key: snapshots/YYYY-MM-DD/HH.parquet
        parts = latest.replace("snapshots/", "").replace(".parquet", "").split("/")
        if len(parts) == 2:
            ts = datetime.strptime(f"{parts[0]} {parts[1]}", "%Y-%m-%d %H")
            ts = ts.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_hours > 2:
                return False, f"Latest snapshot is {age_hours:.1f}h old: {latest}"
            return True, f"Latest snapshot: {latest} ({age_hours:.1f}h ago)"
        return True, f"Latest key: {latest}"
    except Exception as e:
        return False, f"Snapshot check error: {e}"


def run_healthcheck(settings: Settings) -> bool:
    """Run all health checks, log results. Returns True if all pass."""
    r2 = R2Client(settings)
    checks = [
        ("DuckDB", check_duckdb(settings)),
        ("R2", check_r2(r2)),
        ("Last Snapshot", check_last_snapshot(r2)),
    ]

    all_ok = True
    for name, (ok, msg) in checks:
        if ok:
            logger.info("healthcheck_pass", check=name, detail=msg)
        else:
            logger.error("healthcheck_fail", check=name, detail=msg)
            all_ok = False

    return all_ok


def main():
    from polybot.logging import setup_logging

    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    ok = run_healthcheck(settings)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add src/polybot/healthcheck.py
git commit -m "feat(ops): healthcheck — DuckDB, R2, last snapshot freshness"
```

---

### Task 8: Validation Script

**Files:**
- Create: `scripts/validate_snapshot.py`

- [ ] **Step 1: Write validation script**

`scripts/validate_snapshot.py`:
```python
#!/usr/bin/env python3
"""Validate a CLOB snapshot on R2 — check structure, row count, non-null fields."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import polars as pl

from polybot.config import Settings
from polybot.storage.r2 import R2Client


def validate_snapshot(r2: R2Client, key: str) -> tuple[bool, list[str]]:
    """Validate a single Parquet snapshot. Returns (ok, list of issues)."""
    issues: list[str] = []

    try:
        data = r2.get_bytes(key)
    except Exception as e:
        return False, [f"Cannot read {key}: {e}"]

    try:
        df = pl.read_parquet(data)
    except Exception as e:
        return False, [f"Cannot parse Parquet: {e}"]

    # Check columns
    expected = {
        "condition_id", "token_id", "snapshot_ts", "best_bid", "best_ask",
        "midpoint", "spread", "bid_depth_1pct", "ask_depth_1pct", "volume_1h",
    }
    missing = expected - set(df.columns)
    if missing:
        issues.append(f"Missing columns: {missing}")

    # Check row count (~300 expected = 150 markets * 2 tokens)
    n_rows = len(df)
    if n_rows < 50:
        issues.append(f"Only {n_rows} rows (expected ~300)")
    elif n_rows < 200:
        issues.append(f"Low row count: {n_rows} (expected ~300)")

    # Check non-null best_bid / best_ask
    if "best_bid" in df.columns and "best_ask" in df.columns:
        null_bid = df.filter(pl.col("best_bid").is_null()).height
        null_ask = df.filter(pl.col("best_ask").is_null()).height
        null_pct = (null_bid + null_ask) / (2 * n_rows) * 100 if n_rows > 0 else 100
        if null_pct > 10:
            issues.append(f"{null_pct:.1f}% null bid/ask (threshold: 10%)")

    # Check unique condition_ids
    if "condition_id" in df.columns:
        n_markets = df["condition_id"].n_unique()
        if n_markets < 25:
            issues.append(f"Only {n_markets} unique markets (expected ~150)")

    ok = len(issues) == 0
    return ok, issues


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate CLOB snapshot on R2")
    parser.add_argument(
        "--key",
        help="Specific R2 key (e.g. snapshots/2026-04-21/14.parquet). If omitted, validates the most recent.",
    )
    args = parser.parse_args()

    settings = Settings()
    r2 = R2Client(settings)

    if args.key:
        key = args.key
    else:
        keys = sorted(r2.list_keys(prefix="snapshots/"))
        if not keys:
            print("FAIL: No snapshots found on R2")
            sys.exit(1)
        key = keys[-1]

    print(f"Validating: {key}")
    ok, issues = validate_snapshot(r2, key)

    if ok:
        data = r2.get_bytes(key)
        df = pl.read_parquet(data)
        print(f"OK: {len(df)} rows, {df['condition_id'].n_unique()} markets")
    else:
        print("ISSUES:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/validate_snapshot.py
git commit -m "feat(scripts): validate_snapshot.py — check R2 Parquet structure and row count"
```

---

### Task 9: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write CI workflow**

`.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Lint with ruff
        run: uv run ruff check src/ tests/

      - name: Run unit tests
        run: uv run pytest tests/unit/ -v --tb=short
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: GitHub Actions — ruff lint + unit tests"
```

---

### Task 10: README Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

```markdown
# Polymarket Bot (polybot)

Signals-only bot for Polymarket — CLOB snapshots, informed trading alerts, sharp money tracking. Human-in-the-loop, no auto-execution.

## Status

**Phase B — M1: Foundations + CLOB Snapshot**

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Cloudflare R2 account (free tier)
- US VPN (Polymarket APIs are geo-blocked from EU)

### Install

```bash
git clone <repo-url>
cd polymarket-bot
cp .env.example .env
# Edit .env with your R2 credentials

uv sync --extra dev
```

### Initialize database

```bash
uv run python scripts/init_db.py
```

### Run CLOB snapshot (one-shot)

```bash
# First: refresh the market universe
uv run python -m polybot.indexers.clob_snapshot refresh-universe

# Then: take a snapshot
uv run python -m polybot.indexers.clob_snapshot snapshot
```

### Validate a snapshot

```bash
uv run python scripts/validate_snapshot.py
```

### Run tests

```bash
# Unit tests only
uv run pytest tests/unit/ -v

# Integration tests (requires .env + VPN)
uv run pytest tests/ -v -m integration
```

## Project structure

```
src/polybot/          — Main package
  config.py           — Settings via pydantic-settings (.env)
  db/                 — DuckDB migrations
  storage/            — R2 (S3-compatible) client
  indexers/           — Data ingestion (CLOB snapshots, etc.)
  healthcheck.py      — Connectivity checks
migrations/           — SQL migration files
scripts/              — CLI utilities
tests/                — Unit + integration tests
notebooks/phase_c/    — Phase C research notebooks (reference)
docs/                 — Architecture, plans, research docs
```

## Phase C reference

Phase C research (Iran cluster pilot, ground truth data) is preserved in `notebooks/phase_c/` and `data/ground_truth/`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for Phase B — setup, usage, project structure"
```

---

### Task 11: VPS Provisioning + systemd (LAST)

This task is executed only after all local code is tested and working.

**Files:**
- Create: `deploy/polybot-snapshot.service`
- Create: `deploy/polybot-snapshot.timer`
- Create: `deploy/polybot-universe-refresh.service`
- Create: `deploy/polybot-universe-refresh.timer`
- Create: `deploy/polybot-healthcheck.service`
- Create: `deploy/polybot-healthcheck.timer`
- Create: `deploy/setup-vps.sh`

- [ ] **Step 1: Create systemd unit files**

`deploy/polybot-snapshot.service`:
```ini
[Unit]
Description=Polybot CLOB snapshot
After=network.target

[Service]
Type=oneshot
User=polybot
WorkingDirectory=/opt/polybot
ExecStart=/opt/polybot/.venv/bin/python -m polybot.indexers.clob_snapshot snapshot
Environment=PYTHONPATH=/opt/polybot/src
EnvironmentFile=/opt/polybot/.env
StandardOutput=append:/var/log/polybot/snapshot.log
StandardError=append:/var/log/polybot/snapshot.log
```

`deploy/polybot-snapshot.timer`:
```ini
[Unit]
Description=Run CLOB snapshot hourly

[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
```

`deploy/polybot-universe-refresh.service`:
```ini
[Unit]
Description=Polybot refresh snapshot universe
After=network.target

[Service]
Type=oneshot
User=polybot
WorkingDirectory=/opt/polybot
ExecStart=/opt/polybot/.venv/bin/python -m polybot.indexers.clob_snapshot refresh-universe
Environment=PYTHONPATH=/opt/polybot/src
EnvironmentFile=/opt/polybot/.env
StandardOutput=append:/var/log/polybot/universe-refresh.log
StandardError=append:/var/log/polybot/universe-refresh.log
```

`deploy/polybot-universe-refresh.timer`:
```ini
[Unit]
Description=Refresh snapshot universe every 6h

[Timer]
OnCalendar=*-*-* 00/6:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

`deploy/polybot-healthcheck.service`:
```ini
[Unit]
Description=Polybot healthcheck
After=network.target

[Service]
Type=oneshot
User=polybot
WorkingDirectory=/opt/polybot
ExecStart=/opt/polybot/.venv/bin/python -m polybot.healthcheck
Environment=PYTHONPATH=/opt/polybot/src
EnvironmentFile=/opt/polybot/.env
StandardOutput=append:/var/log/polybot/healthcheck.log
StandardError=append:/var/log/polybot/healthcheck.log
```

`deploy/polybot-healthcheck.timer`:
```ini
[Unit]
Description=Run healthcheck every 6h

[Timer]
OnCalendar=*-*-* 03/6:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 2: Create VPS setup script**

`deploy/setup-vps.sh`:
```bash
#!/bin/bash
# VPS provisioning script — run as root on fresh Ubuntu 24.04
set -euo pipefail

echo "=== Polybot VPS Setup ==="

# System updates
apt update && apt upgrade -y
apt install -y ufw fail2ban git curl

# SSH hardening
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# Firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw --force enable

# fail2ban
systemctl enable fail2ban
systemctl start fail2ban

# Create polybot user
useradd -m -s /bin/bash polybot || true
mkdir -p /opt/polybot /var/log/polybot /data
chown polybot:polybot /opt/polybot /var/log/polybot /data

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Clone and setup (run as polybot user)
su - polybot << 'POLYBOT_SETUP'
cd /opt/polybot
# git clone <repo-url> .  # uncomment when remote is set
# cp .env.example .env    # edit with real credentials
# uv sync --extra dev
# uv run python scripts/init_db.py --db /data/pm.duckdb
POLYBOT_SETUP

# Install systemd timers
cp /opt/polybot/deploy/polybot-*.service /etc/systemd/system/
cp /opt/polybot/deploy/polybot-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable polybot-snapshot.timer polybot-universe-refresh.timer polybot-healthcheck.timer
systemctl start polybot-snapshot.timer polybot-universe-refresh.timer polybot-healthcheck.timer

echo "=== Setup complete. Edit /opt/polybot/.env and run 'uv sync' ==="
echo "=== Check timers: systemctl list-timers polybot-* ==="
```

- [ ] **Step 3: Commit deploy files**

```bash
git add deploy/
git commit -m "ops: systemd timers + VPS setup script for Hetzner CX22"
```

- [ ] **Step 4: VPS provisioning (manual steps)**

1. Create Hetzner CX22 (Nuremberg or Helsinki, Ubuntu 24.04)
2. Add SSH key, connect
3. Run `setup-vps.sh`
4. Configure `.env` with real R2 credentials
5. Run `uv sync && uv run python scripts/init_db.py --db /data/pm.duckdb`
6. Manually trigger first run:
   ```bash
   sudo -u polybot /opt/polybot/.venv/bin/python -m polybot.indexers.clob_snapshot refresh-universe
   sudo -u polybot /opt/polybot/.venv/bin/python -m polybot.indexers.clob_snapshot snapshot
   ```
7. Verify: `systemctl list-timers polybot-*`
8. Wait 4h, then: `uv run python scripts/validate_snapshot.py`

- [ ] **Step 5: Final commit**

```bash
git commit --allow-empty -m "milestone: M1 complete — foundations + CLOB snapshot in prod"
```
