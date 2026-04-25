"""Indexer trades via Polymarket Data API — daemon polling every 60s."""

import asyncio
import time
from datetime import UTC, datetime

import duckdb
import httpx
import structlog

from polybot.config import Settings
from polybot.logging import setup_logging

logger = structlog.get_logger()

DATA_API_URL = "https://data-api.polymarket.com/trades"
POLL_INTERVAL = 60
REQUEST_TIMEOUT = 10.0
MAX_RETRIES = 4

INSERT_SQL = """
INSERT INTO trades (
    transaction_hash, proxy_wallet, condition_id, asset_id, side,
    size_usd, price, outcome, outcome_index,
    timestamp_unix, timestamp_ts,
    market_title, market_slug, event_slug, wallet_name
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (transaction_hash) DO NOTHING
"""


def get_tracked_wallets(db_path: str) -> list[dict]:
    """Read active Tier A wallets from tracked_wallets table."""
    from polybot.db.connection import db_read_with_retry

    def _do(con):
        rows = con.execute(
            "SELECT address, last_seen_timestamp FROM tracked_wallets "
            "WHERE tier = 'A' AND active = true"
        ).fetchall()
        return [{"address": r[0], "last_seen_timestamp": r[1] or 0} for r in rows]

    return db_read_with_retry(db_path, _do)


def filter_new_trades(trades: list[dict], last_seen_ts: int) -> list[dict]:
    """Filter trades newer than last_seen_timestamp."""
    return [t for t in trades if int(t.get("timestamp", 0)) > last_seen_ts]


def map_trade(t: dict) -> tuple:
    """Map a Data API trade dict to a DB row tuple."""
    ts = int(t["timestamp"])
    return (
        t["transactionHash"],
        t["proxyWallet"],
        t["conditionId"],
        t.get("asset", ""),
        t["side"],
        float(t["size"]),
        float(t["price"]),
        t.get("outcome"),
        t.get("outcomeIndex"),
        ts,
        datetime.fromtimestamp(ts, tz=UTC),
        t.get("title"),
        t.get("slug"),
        t.get("eventSlug"),
        t.get("name"),
    )


def insert_trades(db_path: str, trades: list[dict]) -> int:
    """Insert new trades with dedup via ON CONFLICT DO NOTHING.
    Returns count of actually inserted trades."""
    if not trades:
        return 0
    from polybot.db.connection import db_write_with_retry

    def _do(con):
        before = con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        for t in trades:
            try:
                con.execute(INSERT_SQL, list(map_trade(t)))
            except Exception:
                logger.warning("insert_failed", tx_hash=t.get("transactionHash"))
        after = con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        return after - before

    return db_write_with_retry(db_path, _do)


def update_wallet_cursor(db_path: str, address: str, new_timestamp: int) -> None:
    """Update last_seen_timestamp for a wallet."""
    from polybot.db.connection import db_write_with_retry

    def _do(con):
        con.execute(
            "UPDATE tracked_wallets SET last_seen_timestamp = ? WHERE address = ?",
            [new_timestamp, address],
        )

    db_write_with_retry(db_path, _do)


def update_indexer_state(
    db_path: str,
    status: str,
    count: int,
    duration_ms: int,
    error: str | None = None,
) -> None:
    """Update indexer_state for 'trades_dataapi'."""
    from polybot.db.connection import db_write_with_retry

    def _do(con):
        con.execute(
            """
            INSERT OR REPLACE INTO indexer_state (
                indexer_name, last_synced_at, last_run_status,
                last_run_duration_ms, ingested_count, last_error, updated_at
            ) VALUES ('trades_dataapi', NOW(), ?, ?, ?, ?, NOW())
            """,
            [status, duration_ms, count, error],
        )

    db_write_with_retry(db_path, _do)


async def fetch_wallet_trades(
    client: httpx.AsyncClient, address: str
) -> list[dict]:
    """Fetch latest 50 trades for a wallet with retry on 429."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(
                DATA_API_URL,
                params={"user": address, "limit": 50},
            )
            if resp.status_code == 429:
                delay = 2**attempt
                logger.warning("rate_limited", address=address[:10], retry_in=delay)
                await asyncio.sleep(delay)
                continue
            if resp.status_code == 403:
                logger.error("geoblock_detected", address=address[:10], status=403)
                return []
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException as e:
            last_exc = e
            logger.warning("timeout", address=address[:10], attempt=attempt + 1)
            await asyncio.sleep(1)
        except httpx.HTTPStatusError as e:
            last_exc = e
            logger.warning(
                "http_error", address=address[:10], status=e.response.status_code
            )
            break
        except Exception as e:
            last_exc = e
            logger.warning("fetch_error", address=address[:10], error=str(e)[:200])
            break

    logger.warning(
        "wallet_fetch_failed",
        address=address[:10],
        error=str(last_exc)[:200] if last_exc else "max retries",
    )
    return []


async def poll_once(db_path: str, client: httpx.AsyncClient) -> int:
    """One polling cycle: fetch all wallets, insert new trades."""
    wallets = get_tracked_wallets(db_path)
    if not wallets:
        logger.warning("no_tracked_wallets")
        return 0

    total_inserted = 0
    wallets_polled = 0
    wallets_with_errors = 0

    for w in wallets:
        address = w["address"]
        last_seen = w["last_seen_timestamp"]
        try:
            trades = await fetch_wallet_trades(client, address)
            if not trades:
                wallets_polled += 1
                continue

            new_trades = filter_new_trades(trades, last_seen)
            if not new_trades:
                wallets_polled += 1
                continue

            inserted = insert_trades(db_path, new_trades)
            total_inserted += inserted

            if inserted > 0:
                max_ts = max(int(t["timestamp"]) for t in new_trades)
                update_wallet_cursor(db_path, address, max_ts)
                logger.info(
                    "wallet_trades_ingested",
                    address=address[:10],
                    new=inserted,
                    max_ts=max_ts,
                )

            wallets_polled += 1
        except Exception:
            wallets_with_errors += 1
            logger.exception("wallet_poll_error", address=address[:10])

    logger.debug(
        "poll_cycle_done",
        wallets_polled=wallets_polled,
        errors=wallets_with_errors,
        new_trades=total_inserted,
    )
    return total_inserted


async def run_forever(db_path: str) -> None:
    """Main loop: poll every POLL_INTERVAL seconds."""
    logger.info("trades_indexer_starting", poll_interval=POLL_INTERVAL)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        while True:
            start = time.monotonic()
            try:
                count = await poll_once(db_path, client)
                duration_ms = int((time.monotonic() - start) * 1000)
                update_indexer_state(db_path, "success", count, duration_ms)
                if count > 0:
                    logger.info("poll_complete", new_trades=count, duration_ms=duration_ms)
                else:
                    logger.debug("poll_complete_no_new", duration_ms=duration_ms)
            except Exception as e:
                duration_ms = int((time.monotonic() - start) * 1000)
                update_indexer_state(db_path, "failed", 0, duration_ms, str(e))
                logger.error("poll_failed", error=str(e))

            elapsed = time.monotonic() - start
            sleep_time = max(0, POLL_INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)


def main():
    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    logger.info("trades_dataapi_daemon_starting")
    try:
        asyncio.run(run_forever(str(settings.DUCKDB_PATH)))
    except KeyboardInterrupt:
        logger.info("trades_indexer_stopped_by_user")


if __name__ == "__main__":
    main()
