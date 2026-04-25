"""DuckDB connection helper with retry on lock conflicts."""

import time
from collections.abc import Callable
from typing import TypeVar

import duckdb
import structlog

logger = structlog.get_logger()

MAX_RETRIES = 5
BASE_DELAY = 1.0

T = TypeVar("T")


def connect(db_path: str, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Connect to DuckDB with retry on IOException (lock conflicts).

    DuckDB is single-writer. When multiple processes access the same DB,
    write locks can conflict. This helper retries with exponential backoff.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return duckdb.connect(db_path, read_only=read_only)
        except duckdb.IOException:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = BASE_DELAY * 2**attempt
            logger.warning(
                "duckdb_lock_retry",
                attempt=attempt + 1,
                delay=delay,
                read_only=read_only,
            )
            time.sleep(delay)
    raise duckdb.IOException("Failed to connect after retries")


def db_write_with_retry(
    db_path: str,
    callback: Callable[[duckdb.DuckDBPyConnection], T],
    max_retries: int = 5,
    base_delay: float = 1.0,
) -> T:
    """Open a write connection, run callback, close. Retry on lock conflicts.

    The connection is opened and closed within each attempt — no long-lived
    write locks. On IOException (DuckDB lock conflict), retries with
    exponential backoff: base_delay * 2^attempt.
    """
    for attempt in range(max_retries):
        con = None
        try:
            con = duckdb.connect(db_path)
            result = callback(con)
            return result
        except duckdb.IOException:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * 2**attempt
            logger.warning(
                "duckdb_write_retry",
                attempt=attempt + 1,
                delay=delay,
            )
            time.sleep(delay)
        finally:
            if con:
                try:
                    con.close()
                except Exception:
                    pass
    raise duckdb.IOException("Failed to write after retries")
