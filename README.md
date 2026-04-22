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
src/polybot/            Production code
  config.py             Settings via pydantic-settings (.env)
  db/                   DuckDB migrations
  storage/              R2 (S3-compatible) client
  indexers/             Data ingestion (CLOB snapshots, etc.)
  healthcheck.py        Connectivity checks
research/               Research scripts (separate from prod)
  phase_c/              Phase C pilot notebooks
  discover_tier_a/      Tier A wallet candidate discovery
migrations/             SQL migration files
scripts/                CLI utilities
tests/                  Unit + integration tests
notebooks/              Active notebooks (phase D+)
data/ground_truth/      Annotated source-of-truth data
data/research_outputs/  Research script outputs
docs/                   Architecture, plans, research docs
config/                 YAML config files (wallets, thresholds)
```

## Timezone conventions

- systemd logs on VPS display local time (CEST/CET) based on server timezone
- R2 snapshot files use UTC in their names: `snapshots/YYYY-MM-DD/HH.parquet`
- All timestamps in DuckDB tables are stored in UTC
- When querying or correlating, always normalize to UTC

See [ADR-012](docs/ADRs/012_utc_timestamps_r2_naming.md) for rationale.
