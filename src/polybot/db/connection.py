"""DuckDB connection helper with retry on lock conflicts."""

import time

import duckdb
import structlog

logger = structlog.get_logger()

MAX_RETRIES = 5
RETRY_DELAY = 1.0


def connect(db_path: str, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Connect to DuckDB with retry on IOException (lock conflicts).

    DuckDB is single-writer. When multiple processes access the same DB,
    write locks can conflict. This helper retries with backoff.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return duckdb.connect(db_path, read_only=read_only)
        except duckdb.IOException:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = RETRY_DELAY * (attempt + 1)
            logger.warning(
                "duckdb_lock_retry",
                attempt=attempt + 1,
                delay=delay,
                read_only=read_only,
            )
            time.sleep(delay)
    raise duckdb.IOException("Failed to connect after retries")
