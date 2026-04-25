"""Indexer on-chain trades via Alchemy RPC OrderFilled events — hourly polling."""

import time
from datetime import UTC, datetime

import duckdb
import httpx
import structlog

from polybot.config import Settings
from polybot.indexers.proxy_factory import (
    LogResponseTooLarge,
    get_current_block,
    rpc_call,
)
from polybot.logging import setup_logging

logger = structlog.get_logger()

# --- Constants ---

CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"

EXCHANGES = {
    CTF_EXCHANGE: "ctf",
    NEG_RISK_EXCHANGE: "neg_risk",
}

# keccak256("OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)")
ORDER_FILLED_TOPIC = (
    "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"
)

# Filter out events where taker is the exchange contract itself (internal routing)
EXCHANGE_ADDRS_LOWER = {addr.lower() for addr in EXCHANGES}

BATCH_SIZE_BLOCKS = 100  # OrderFilled is very dense (~150 events/block)
SLEEP_BETWEEN_BATCHES = 0.2
INITIAL_LOOKBACK = 5_000  # ~2.5h for initial scan, incremental extends
REQUEST_TIMEOUT = 30.0
LOG_EVERY_N_BATCHES = 25

INSERT_SQL = """
INSERT INTO trades_all (
    tx_hash_log_idx, transaction_hash, log_index,
    proxy_wallet, condition_id, side, size_usd, price,
    timestamp_ts, source
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'alchemy')
ON CONFLICT (tx_hash_log_idx) DO NOTHING
"""


# --- Event parsing ---


def parse_order_filled(event: dict) -> dict | None:
    """Parse an OrderFilled event log into a structured dict.

    Event: OrderFilled(bytes32 orderHash, address maker, address taker,
                       uint256 makerAssetId, uint256 takerAssetId,
                       uint256 makerAmountFilled, uint256 takerAmountFilled,
                       uint256 fee)

    topics[0] = signature, topics[1] = orderHash,
    topics[2] = maker (padded), topics[3] = taker (padded)
    data = makerAssetId | takerAssetId | makerAmountFilled | takerAmountFilled | fee
    """
    topics = event.get("topics", [])
    if len(topics) < 4:
        return None

    data = event.get("data", "0x")[2:]
    if len(data) < 320:  # 5 x 64 hex chars
        return None

    taker = ("0x" + topics[3][26:]).lower()

    # Skip internal exchange routing events
    if taker in EXCHANGE_ADDRS_LOWER:
        return None

    maker_asset_id = int(data[0:64], 16)
    taker_asset_id = int(data[64:128], 16)
    maker_amount = int(data[128:192], 16)
    taker_amount = int(data[192:256], 16)

    # Determine USDC side and derive trade direction
    if maker_asset_id == 0:
        # Maker pays USDC → taker sells condition tokens
        size_usd = maker_amount / 1e6
        token_id = str(taker_asset_id)
        token_amount = taker_amount
        side = "SELL"
    elif taker_asset_id == 0:
        # Taker pays USDC → taker buys condition tokens
        size_usd = taker_amount / 1e6
        token_id = str(maker_asset_id)
        token_amount = maker_amount
        side = "BUY"
    else:
        # Neither side is USDC — skip (token-for-token swap, rare)
        return None

    price = size_usd / (token_amount / 1e6) if token_amount > 0 else 0.0

    block_number = int(event["blockNumber"], 16)
    log_index = int(event["logIndex"], 16)
    tx_hash = event["transactionHash"]

    return {
        "tx_hash_log_idx": f"{tx_hash}_{log_index}",
        "transaction_hash": tx_hash,
        "log_index": log_index,
        "block_number": block_number,
        "proxy_wallet": taker,
        "condition_id": token_id,
        "side": side,
        "size_usd": round(size_usd, 2),
        "price": round(price, 4),
    }


# --- DB operations ---


def get_last_scanned_block(db_path: str) -> int | None:
    """Read last_cursor from indexer_state for onchain_alchemy."""
    con = duckdb.connect(db_path, read_only=True)
    row = con.execute(
        "SELECT last_cursor FROM indexer_state "
        "WHERE indexer_name = 'onchain_alchemy'"
    ).fetchone()
    con.close()
    if row and row[0]:
        return int(row[0])
    return None


def insert_trades(db_path: str, trades: list[dict]) -> int:
    """Insert trades into trades_all. Returns count of new rows."""
    if not trades:
        return 0
    con = duckdb.connect(db_path)
    before = con.execute("SELECT COUNT(*) FROM trades_all").fetchone()[0]
    for t in trades:
        con.execute(
            INSERT_SQL,
            [
                t["tx_hash_log_idx"],
                t["transaction_hash"],
                t["log_index"],
                t["proxy_wallet"],
                t["condition_id"],
                t["side"],
                t["size_usd"],
                t["price"],
                t.get("timestamp_ts"),
            ],
        )
    after = con.execute("SELECT COUNT(*) FROM trades_all").fetchone()[0]
    con.close()
    return after - before


def update_indexer_state(
    db_path: str,
    last_block: int,
    status: str,
    count: int,
    duration_ms: int,
    error: str | None = None,
) -> None:
    """Update indexer_state for 'onchain_alchemy'."""
    con = duckdb.connect(db_path)
    con.execute(
        """
        INSERT OR REPLACE INTO indexer_state (
            indexer_name, last_synced_at, last_block_number, last_cursor,
            last_run_status, last_run_duration_ms, ingested_count,
            last_error, updated_at
        ) VALUES ('onchain_alchemy', NOW(), ?, ?, ?, ?, ?, ?, NOW())
        """,
        [last_block, str(last_block), status, duration_ms, count, error],
    )
    con.close()


# --- Fetch logic ---


def fetch_order_filled_events(
    client: httpx.Client,
    url: str,
    from_block: int,
    to_block: int,
    exchange: str,
    _min_batch: int = 10,
) -> list[dict]:
    """Fetch OrderFilled events with recursive splitting on range errors."""
    try:
        result = rpc_call(
            client,
            url,
            "eth_getLogs",
            [
                {
                    "fromBlock": hex(from_block),
                    "toBlock": hex(to_block),
                    "address": exchange,
                    "topics": [ORDER_FILLED_TOPIC],
                }
            ],
        )
        return result.get("result", [])
    except LogResponseTooLarge:
        if to_block - from_block < _min_batch:
            logger.warning(
                "block_range_too_small",
                from_block=from_block,
                to_block=to_block,
            )
            return []
        mid = from_block + (to_block - from_block) // 2
        left = fetch_order_filled_events(
            client, url, from_block, mid, exchange, _min_batch
        )
        right = fetch_order_filled_events(
            client, url, mid + 1, to_block, exchange, _min_batch
        )
        return left + right


def get_block_timestamps(
    client: httpx.Client,
    url: str,
    block_numbers: set[int],
    cache: dict[int, datetime],
) -> dict[int, datetime]:
    """Fetch block timestamps for blocks not yet cached."""
    to_fetch = block_numbers - set(cache.keys())
    for bn in to_fetch:
        result = rpc_call(
            client, url, "eth_getBlockByNumber", [hex(bn), False]
        )
        block = result.get("result")
        if block and "timestamp" in block:
            ts = int(block["timestamp"], 16)
            cache[bn] = datetime.fromtimestamp(ts, tz=UTC)
    return cache


# --- Main run ---


def run(db_path: str, alchemy_url: str) -> int:
    """Main entry. Scans OrderFilled events from both CTF exchanges."""
    last_block = get_last_scanned_block(db_path)
    is_backfill = last_block is None

    start_time = time.monotonic()
    total_inserted = 0

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        head = get_current_block(client, alchemy_url)

        start_block = max(1, head - INITIAL_LOOKBACK) if is_backfill else last_block + 1

        current_block_end = start_block
        total_batches = max(
            1, (head - start_block + BATCH_SIZE_BLOCKS) // BATCH_SIZE_BLOCKS
        )

        mode = "backfill" if is_backfill else "incremental"
        logger.info(
            "onchain_alchemy_starting",
            mode=mode,
            from_block=start_block,
            to_block=head,
            total_batches=total_batches,
        )

        if start_block > head:
            logger.info("onchain_alchemy_already_synced", head=head)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            update_indexer_state(db_path, head, "success", 0, duration_ms)
            return 0

        block_ts_cache: dict[int, datetime] = {}
        batch_num = 0
        batch_start = start_block

        try:
            while batch_start <= head:
                batch_end = min(batch_start + BATCH_SIZE_BLOCKS - 1, head)
                batch_num += 1

                batch_trades: list[dict] = []
                batch_blocks: set[int] = set()

                for exchange in EXCHANGES:
                    events = fetch_order_filled_events(
                        client, alchemy_url, batch_start, batch_end, exchange
                    )

                    for event in events:
                        parsed = parse_order_filled(event)
                        if parsed:
                            batch_trades.append(parsed)
                            batch_blocks.add(parsed["block_number"])

                # Fetch timestamps for all blocks in this batch
                if batch_blocks:
                    get_block_timestamps(
                        client, alchemy_url, batch_blocks, block_ts_cache
                    )
                    for t in batch_trades:
                        t["timestamp_ts"] = block_ts_cache.get(
                            t["block_number"]
                        )

                if batch_trades:
                    inserted = insert_trades(db_path, batch_trades)
                    total_inserted += inserted

                if batch_num % LOG_EVERY_N_BATCHES == 0 or batch_num == 1:
                    pct = batch_num / total_batches * 100
                    logger.info(
                        "onchain_scan_progress",
                        batch=batch_num,
                        total_batches=total_batches,
                        pct=f"{pct:.1f}",
                        block=batch_end,
                        trades_so_far=total_inserted,
                    )

                current_block_end = batch_end
                batch_start = batch_end + 1
                time.sleep(SLEEP_BETWEEN_BATCHES)

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            update_indexer_state(
                db_path,
                current_block_end,
                "failed",
                total_inserted,
                duration_ms,
                str(e)[:500],
            )
            logger.error(
                "onchain_alchemy_failed",
                error=str(e)[:200],
                last_block=current_block_end,
                trades=total_inserted,
            )
            raise

    duration_ms = int((time.monotonic() - start_time) * 1000)
    update_indexer_state(
        db_path, head, "success", total_inserted, duration_ms
    )
    logger.info(
        "onchain_alchemy_complete",
        mode=mode,
        trades=total_inserted,
        duration_s=round(duration_ms / 1000, 1),
        head=head,
    )
    return total_inserted


def main():
    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    logger.info("onchain_alchemy_indexer_starting")
    count = run(
        db_path=str(settings.DUCKDB_PATH),
        alchemy_url=settings.ALCHEMY_POLYGON_URL,
    )
    print(f"Onchain Alchemy indexer complete: {count} new trades")


if __name__ == "__main__":
    main()
