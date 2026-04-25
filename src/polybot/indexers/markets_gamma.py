"""Indexer markets via Gamma API — full sync every 15 min."""

import json
import time
from datetime import UTC, datetime

import duckdb
import httpx
import structlog

from polybot.config import Settings
from polybot.logging import setup_logging

logger = structlog.get_logger()

GAMMA_URL = "https://gamma-api.polymarket.com/markets"
PAGE_SIZE = 500
SLEEP_BETWEEN_PAGES = 0.5
REQUEST_TIMEOUT = 15.0
MAX_RETRIES = 4


def fetch_all_markets() -> list[dict]:
    """Paginate through Gamma API, return all markets."""
    all_markets: list[dict] = []
    offset = 0

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        while True:
            response = _fetch_page(client, offset)
            page = response.json()
            if not page:
                break
            all_markets.extend(page)
            logger.info(
                "fetched_page",
                count=len(page),
                offset=offset,
                total_so_far=len(all_markets),
            )
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
            time.sleep(SLEEP_BETWEEN_PAGES)

    return all_markets


def _fetch_page(client: httpx.Client, offset: int) -> httpx.Response:
    """Fetch a single page with retry on 429 and 5xx."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(
                GAMMA_URL, params={"limit": PAGE_SIZE, "offset": offset}
            )
            if resp.status_code == 429:
                delay = 2**attempt
                logger.warning("rate_limited", status=429, retry_in=delay)
                time.sleep(delay)
                continue
            if resp.status_code >= 500:
                delay = 2
                logger.warning(
                    "server_error", status=resp.status_code, retry_in=delay
                )
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp
        except httpx.TimeoutException as e:
            last_exc = e
            delay = 2**attempt
            logger.warning("timeout", retry_in=delay, attempt=attempt + 1)
            time.sleep(delay)

    msg = f"Failed after {MAX_RETRIES} retries"
    raise RuntimeError(msg) from last_exc


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _parse_decimal(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_outcomes(value) -> list[str] | None:
    """Parse outcomes from JSON string or list."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _derive_status(market: dict) -> str:
    if market.get("closed"):
        return "closed"
    if market.get("active"):
        return "active"
    return "inactive"


def map_market(m: dict) -> tuple:
    """Map a Gamma API market dict to a DB row tuple."""
    event_slug = None
    events = m.get("events")
    if events and isinstance(events, list) and len(events) > 0:
        event_slug = events[0].get("slug")

    return (
        m.get("conditionId"),
        m.get("questionID"),
        m.get("question"),
        m.get("description"),
        m.get("category"),
        None,  # tags — not available from Gamma
        _parse_outcomes(m.get("outcomes")),
        m.get("negRisk"),
        m.get("resolutionSource") or None,
        _parse_timestamp(m.get("endDate")),  # resolution_date
        _parse_timestamp(m.get("createdAt")),
        _parse_timestamp(m.get("closedTime")),
        _parse_decimal(m.get("volume")),
        _parse_decimal(m.get("liquidity")),
        _derive_status(m),
        datetime.now(UTC),  # last_synced_at
        m.get("question"),  # title (same as question in Gamma)
        m.get("slug"),
        event_slug,
        _parse_decimal(m.get("volume24hr")),
        None,  # volume_1h — not available, ADR-006
        _parse_timestamp(m.get("endDate")),
        _parse_timestamp(m.get("startDate")),
        bool(m.get("active")),
        bool(m.get("closed")),
    )


COLUMNS = [
    "condition_id", "question_id", "question_text", "description", "category",
    "tags", "outcomes", "neg_risk", "resolution_source", "resolution_date",
    "created_at", "closed_at", "volume_cumulative_usd", "liquidity_usd",
    "status", "last_synced_at",
    "title", "slug", "event_slug", "volume_24h", "volume_1h",
    "end_date", "start_date", "active", "resolved",
]


def upsert_markets(db_path: str, markets: list[dict]) -> int:
    """Upsert markets into DuckDB via bulk temp table + INSERT OR REPLACE."""
    if not markets:
        return 0

    rows = []
    skipped = 0
    for m in markets:
        if not m.get("conditionId"):
            skipped += 1
            continue
        rows.append(map_market(m))

    if skipped:
        logger.info("skipped_markets_no_condition_id", count=skipped)

    if not rows:
        return 0

    import pyarrow as pa

    # Build Arrow table for bulk insert
    cols_data: dict[str, list] = {col: [] for col in COLUMNS}
    for row in rows:
        for i, col in enumerate(COLUMNS):
            cols_data[col].append(row[i])

    staging_data = pa.table(cols_data)  # noqa: F841 (referenced by DuckDB SQL)

    from polybot.db.connection import db_write_with_retry

    upsert_start = time.monotonic()

    def _do(con):
        con.register("staging_data", staging_data)
        con.execute(
            "CREATE OR REPLACE TEMP TABLE _staging AS SELECT * FROM staging_data"
        )
        cols_str = ", ".join(COLUMNS)
        con.execute(
            f"INSERT OR REPLACE INTO markets ({cols_str}) "
            f"SELECT {cols_str} FROM _staging"
        )
        con.execute("DROP TABLE IF EXISTS _staging")

    db_write_with_retry(db_path, _do)
    upsert_ms = int((time.monotonic() - upsert_start) * 1000)
    logger.info("upsert_complete", count=len(rows), upsert_ms=upsert_ms)

    return len(rows)


def update_indexer_state(
    db_path: str,
    status: str,
    count: int,
    duration_ms: int,
    error: str | None = None,
) -> None:
    """Update indexer_state table for 'markets_gamma'."""
    from polybot.db.connection import db_write_with_retry

    def _do(con):
        con.execute(
            """
            INSERT OR REPLACE INTO indexer_state (
                indexer_name, last_synced_at, last_run_status,
                last_run_duration_ms, ingested_count, last_error, updated_at
            ) VALUES ('markets_gamma', NOW(), ?, ?, ?, ?, NOW())
            """,
            [status, duration_ms, count, error],
        )

    db_write_with_retry(db_path, _do)


def run(db_path: str) -> int:
    """Main entry point. Fetch all markets, upsert, update state."""
    logger.info("starting_markets_gamma_sync")
    start = time.monotonic()

    try:
        markets = fetch_all_markets()
        count = upsert_markets(db_path, markets)
        duration_ms = int((time.monotonic() - start) * 1000)
        update_indexer_state(db_path, "success", count, duration_ms)
        logger.info(
            "markets_sync_complete",
            total=count,
            duration_ms=duration_ms,
        )
        return count
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        update_indexer_state(db_path, "failed", 0, duration_ms, str(e))
        logger.error("markets_sync_failed", error=str(e))
        raise


def main():
    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    count = run(str(settings.DUCKDB_PATH))
    print(f"Markets sync complete: {count} markets upserted")


if __name__ == "__main__":
    main()
