"""Healthcheck — verify DuckDB connectivity, R2 access, and last snapshot freshness."""

from datetime import UTC, datetime

import duckdb
import structlog

from polybot.config import Settings
from polybot.storage.r2 import R2Client

logger = structlog.get_logger()


def check_duckdb(settings: Settings) -> tuple[bool, str]:
    """Check DuckDB is accessible and has expected tables."""
    try:
        from polybot.db.connection import db_read_with_retry

        tables = db_read_with_retry(
            str(settings.DUCKDB_PATH),
            lambda con: [r[0] for r in con.execute("SHOW TABLES").fetchall()],
        )
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
            ts = ts.replace(tzinfo=UTC)
            age_hours = (datetime.now(UTC) - ts).total_seconds() / 3600
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
