#!/usr/bin/env python3
"""Validate a CLOB snapshot on R2 — check structure, row count, non-null fields."""

import sys
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
        help="Specific R2 key (e.g. snapshots/2026-04-21/14.parquet). "
        "If omitted, validates the most recent.",
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
