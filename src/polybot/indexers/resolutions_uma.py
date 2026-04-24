"""Indexer market resolutions via ConditionResolution events on Polygon.

Polymarket market resolutions are emitted by the ConditionalTokens
framework contract (not the UMA Oracle directly). The ConditionResolution
event carries conditionId, questionId, and payout numerators which tell
us the outcome (YES/NO/INVALID).

Proposed/disputed info (from UMA Oracle) is not captured in v1 — those
fields remain NULL and can be enriched in M7.
"""

import time
from datetime import UTC, datetime

import duckdb
import httpx
import structlog

from polybot.config import Settings
from polybot.indexers.proxy_factory import (
    LogResponseTooLarge,
    rpc_call,
)
from polybot.logging import setup_logging

logger = structlog.get_logger()

# --- Constants ---

CONDITIONAL_TOKENS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# keccak256("ConditionResolution(bytes32,address,bytes32,uint256,uint256[])")
CONDITION_RESOLUTION_TOPIC = (
    "0xb44d84d3289691f71497564b85d4233648d9dbae8cbdbb4329f301c3a0185894"
)

BATCH_SIZE_BLOCKS = 10  # Alchemy free tier limit
SLEEP_BETWEEN_BATCHES = 0.05
BACKFILL_START_BLOCK = 0  # 0 = dynamic (head - DEFAULT_LOOKBACK)
DEFAULT_LOOKBACK = 5_000_000  # ~4 months, resolutions are sparser
LOG_EVERY_N_BATCHES = 50_000

UPSERT_SQL = """
INSERT INTO resolutions (
    condition_id, question_id, settled_at, final_price, settled_outcome
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT (condition_id) DO UPDATE SET
    settled_at = EXCLUDED.settled_at,
    final_price = EXCLUDED.final_price,
    settled_outcome = EXCLUDED.settled_outcome
"""


# --- Event parsing ---


def parse_condition_resolution(event: dict) -> dict | None:
    """Parse a ConditionResolution event into a resolution dict.

    Event structure:
        topics[0] = event signature
        topics[1] = conditionId (bytes32, indexed)
        topics[2] = oracle address (address, indexed, padded to 32 bytes)
        topics[3] = questionId (bytes32, indexed)
        data = outcomeSlotCount (uint256) + offset (uint256)
             + array length (uint256) + payoutNumerators (uint256[])
    """
    topics = event.get("topics", [])
    if len(topics) < 4:
        return None

    condition_id = topics[1]
    question_id = topics[3]
    block_number = int(event["blockNumber"], 16)

    # Parse payouts from data
    data = event.get("data", "0x")[2:]
    if len(data) < 192:
        return None

    arr_len = int(data[128:192], 16)
    payouts = []
    for i in range(arr_len):
        start = 192 + i * 64
        if start + 64 > len(data):
            break
        payouts.append(int(data[start : start + 64], 16))

    outcome, price = _interpret_payouts(payouts)

    return {
        "condition_id": condition_id,
        "question_id": question_id,
        "block_number": block_number,
        "final_price": price,
        "settled_outcome": outcome,
    }


def _interpret_payouts(payouts: list[int]) -> tuple[str, float]:
    """Interpret payout numerators into outcome label and price.

    Standard Polymarket binary markets:
        (1, 0) → YES, price 1.0
        (0, 1) → NO, price 0.0
        (1, 1) → INVALID, price 0.5
    """
    if payouts == [1, 0]:
        return "YES", 1.0
    if payouts == [0, 1]:
        return "NO", 0.0
    if payouts == [1, 1]:
        return "INVALID", 0.5
    # Multi-outcome or unexpected
    return "UNKNOWN", -1.0


# --- DB operations ---


def get_last_scanned_block(db_path: str) -> int | None:
    """Read last_cursor from indexer_state for resolutions_uma."""
    con = duckdb.connect(db_path, read_only=True)
    row = con.execute(
        "SELECT last_cursor FROM indexer_state "
        "WHERE indexer_name = 'resolutions_uma'"
    ).fetchone()
    con.close()
    if row and row[0]:
        return int(row[0])
    return None


def upsert_resolutions(db_path: str, resolutions: list[dict]) -> int:
    """Upsert resolutions into DB. Returns count of new/updated rows."""
    if not resolutions:
        return 0
    con = duckdb.connect(db_path)
    before = con.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0]
    for r in resolutions:
        con.execute(
            UPSERT_SQL,
            [
                r["condition_id"],
                r["question_id"],
                r.get("settled_at"),
                r["final_price"],
                r["settled_outcome"],
            ],
        )
    after = con.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0]
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
    """Update indexer_state for 'resolutions_uma'."""
    con = duckdb.connect(db_path)
    con.execute(
        """
        INSERT OR REPLACE INTO indexer_state (
            indexer_name, last_synced_at, last_block_number, last_cursor,
            last_run_status, last_run_duration_ms, ingested_count,
            last_error, updated_at
        ) VALUES ('resolutions_uma', NOW(), ?, ?, ?, ?, ?, ?, NOW())
        """,
        [last_block, str(last_block), status, duration_ms, count, error],
    )
    con.close()


# --- Scan logic ---


def fetch_resolution_events(
    client: httpx.Client,
    url: str,
    from_block: int,
    to_block: int,
    _min_batch: int = 10,
) -> list[dict]:
    """Fetch ConditionResolution events, with recursive splitting on range errors."""
    try:
        result = rpc_call(
            client,
            url,
            "eth_getLogs",
            [
                {
                    "fromBlock": hex(from_block),
                    "toBlock": hex(to_block),
                    "address": CONDITIONAL_TOKENS,
                    "topics": [CONDITION_RESOLUTION_TOPIC],
                }
            ],
        )
        return result.get("result", [])
    except LogResponseTooLarge:
        if to_block - from_block < _min_batch:
            return []
        mid = from_block + (to_block - from_block) // 2
        left = fetch_resolution_events(client, url, from_block, mid, _min_batch)
        right = fetch_resolution_events(client, url, mid + 1, to_block, _min_batch)
        return left + right


def get_block_timestamp(
    client: httpx.Client, url: str, block_number: int
) -> datetime | None:
    """Get block timestamp via eth_getBlockByNumber."""
    result = rpc_call(
        client, url, "eth_getBlockByNumber", [hex(block_number), False]
    )
    block = result.get("result")
    if block and "timestamp" in block:
        ts = int(block["timestamp"], 16)
        return datetime.fromtimestamp(ts, tz=UTC)
    return None


def run(db_path: str, alchemy_url: str) -> int:
    """Main entry. Backfill or incremental scan for ConditionResolution events."""
    last_block = get_last_scanned_block(db_path)
    is_backfill = last_block is None

    start_time = time.monotonic()
    total_inserted = 0

    with httpx.Client(timeout=15.0) as client:
        from polybot.indexers.proxy_factory import get_current_block

        head = get_current_block(client, alchemy_url)

        if is_backfill:
            start_block = (
                BACKFILL_START_BLOCK if BACKFILL_START_BLOCK > 0
                else max(1, head - DEFAULT_LOOKBACK)
            )
        else:
            start_block = last_block + 1

        current_block_end = start_block
        total_batches = max(
            1, (head - start_block + BATCH_SIZE_BLOCKS) // BATCH_SIZE_BLOCKS
        )

        mode = "backfill" if is_backfill else "incremental"
        logger.info(
            "resolutions_starting",
            mode=mode,
            from_block=start_block,
            to_block=head,
            total_batches=total_batches,
        )

        if start_block > head:
            logger.info("resolutions_already_synced", head=head)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            update_indexer_state(db_path, head, "success", 0, duration_ms)
            return 0

        # Cache block timestamps to avoid redundant RPC calls
        block_ts_cache: dict[int, datetime | None] = {}
        batch_num = 0
        batch_start = start_block

        try:
            while batch_start <= head:
                batch_end = min(batch_start + BATCH_SIZE_BLOCKS - 1, head)
                batch_num += 1

                events = fetch_resolution_events(
                    client, alchemy_url, batch_start, batch_end
                )

                if events:
                    resolutions = []
                    for event in events:
                        parsed = parse_condition_resolution(event)
                        if not parsed:
                            continue

                        # Get block timestamp (cached)
                        bn = parsed["block_number"]
                        if bn not in block_ts_cache:
                            block_ts_cache[bn] = get_block_timestamp(
                                client, alchemy_url, bn
                            )
                        parsed["settled_at"] = block_ts_cache[bn]
                        resolutions.append(parsed)

                    inserted = upsert_resolutions(db_path, resolutions)
                    total_inserted += inserted

                if batch_num % LOG_EVERY_N_BATCHES == 0 or batch_num == 1:
                    pct = batch_num / total_batches * 100
                    logger.info(
                        "resolution_scan_progress",
                        batch=batch_num,
                        total_batches=total_batches,
                        pct=f"{pct:.1f}",
                        block=batch_end,
                        resolutions_so_far=total_inserted,
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
                "resolutions_failed",
                error=str(e)[:200],
                last_block=current_block_end,
                resolutions=total_inserted,
            )
            raise

    duration_ms = int((time.monotonic() - start_time) * 1000)
    update_indexer_state(
        db_path, head, "success", total_inserted, duration_ms
    )
    logger.info(
        "resolutions_complete",
        mode=mode,
        resolutions=total_inserted,
        duration_s=round(duration_ms / 1000, 1),
        head=head,
    )
    return total_inserted


def main():
    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    logger.info("resolutions_uma_indexer_starting")
    count = run(
        db_path=str(settings.DUCKDB_PATH),
        alchemy_url=settings.ALCHEMY_POLYGON_URL,
    )
    print(f"Resolutions indexer complete: {count} new resolutions")


if __name__ == "__main__":
    main()
