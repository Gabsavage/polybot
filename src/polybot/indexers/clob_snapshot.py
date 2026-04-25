"""CLOB snapshot indexer — fetches order books for top markets, writes Parquet to R2."""

import json
from datetime import UTC, datetime

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
    filtered = [m for m in markets if float(m.get("volume24hr") or 0) >= min_volume]
    filtered.sort(key=lambda m: float(m.get("volume24hr") or 0), reverse=True)
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

    now = datetime.now(UTC)

    # Load universe from DuckDB
    from polybot.db.connection import db_read_with_retry

    universe = db_read_with_retry(
        str(settings.DUCKDB_PATH),
        lambda con: con.execute(
            "SELECT condition_id, token_id_yes, token_id_no FROM snapshot_universe"
        ).fetchall(),
    )

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

    import io

    df = pl.DataFrame(rows)
    buf = io.BytesIO()
    df.write_parquet(buf, compression="zstd")
    parquet_bytes = buf.getvalue()

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

    from polybot.db.connection import db_write_with_retry

    now = datetime.now(UTC)

    def _do(con):
        con.execute("DELETE FROM snapshot_universe")
        for m in selected:
            clob_token_ids = json.loads(m.get("clobTokenIds", "[]"))
            if len(clob_token_ids) < 2:
                continue
            cols = "condition_id, token_id_yes, token_id_no"
            cols += ", question_text, volume_24h_usd, refreshed_at"
            con.execute(
                f"INSERT INTO snapshot_universe ({cols}) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    m["conditionId"],
                    clob_token_ids[0],
                    clob_token_ids[1],
                    m.get("question", ""),
                    m.get("volume24hr", 0),
                    now,
                ],
            )
        return con.execute("SELECT COUNT(*) FROM snapshot_universe").fetchone()[0]

    count = db_write_with_retry(str(settings.DUCKDB_PATH), _do)

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
