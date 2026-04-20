"""End-to-end test: refresh universe then run snapshot, verify Parquet on R2."""

import asyncio
from pathlib import Path

import polars as pl
import pytest

from polybot.config import Settings
from polybot.db.migrations import apply_migrations
from polybot.indexers.clob_snapshot import refresh_snapshot_universe, run_snapshot
from polybot.storage.r2 import R2Client


@pytest.fixture
def live_settings(tmp_path: Path) -> Settings:
    """Settings with real APIs + temp DuckDB."""
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
    """Full cycle: refresh universe -> snapshot -> verify Parquet on R2."""
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
        "condition_id",
        "token_id",
        "snapshot_ts",
        "best_bid",
        "best_ask",
        "midpoint",
        "spread",
        "bid_depth_1pct",
        "ask_depth_1pct",
        "volume_1h",
    }
    assert set(df.columns) == expected_cols
    assert len(df) > 100  # expect ~2 * universe_count rows

    # Cleanup test snapshots
    for key in keys:
        if "snapshots/" in key:
            r2.delete_object(key)
