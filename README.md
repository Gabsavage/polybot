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
src/polybot/          Main package
  config.py           Settings via pydantic-settings (.env)
  db/                 DuckDB migrations
  storage/            R2 (S3-compatible) client
  indexers/           Data ingestion (CLOB snapshots, etc.)
  healthcheck.py      Connectivity checks
migrations/           SQL migration files
scripts/              CLI utilities
tests/                Unit + integration tests
notebooks/phase_c/    Phase C research notebooks (reference)
docs/                 Architecture, plans, research docs
config/               YAML config files (wallets, thresholds)
```

## Phase C reference

Phase C research (Iran cluster pilot, ground truth data) is preserved in `notebooks/phase_c/` and `data/ground_truth/`.
