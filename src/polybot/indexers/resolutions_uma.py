"""Indexer market resolutions via ConditionResolution events on Polygon.

Polymarket market resolutions are emitted by the ConditionalTokens
framework contract (not the UMA Oracle directly). The ConditionResolution
event carries conditionId, questionId, and payout numerators which tell
us the outcome (YES/NO/INVALID).

Proposed/disputed info (from UMA Oracle) is not captured in v1 — those
fields remain NULL and can be enriched in M7.
"""

import signal
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

BATCH_SIZE_BLOCKS = 5000  # PAYG tier supports wide ranges
SLEEP_BETWEEN_BATCHES = 0.1
BACKFILL_START_BLOCK = 11_000_000
LOG_EVERY_N_BATCHES = 50
CHECKPOINT_EVERY = 50

UPSERT_SQL = """
INSERT INTO resolutions (
    condition_id, question_id, settled_at, final_price, settled_outcome
)
SELECT condition_id, question_id, settled_at, final_price, settled_outcome
FROM _staging_res
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
    from polybot.db.connection import db_read_with_retry

    def _do(con):
        row = con.execute(
            "SELECT last_cursor FROM indexer_state "
            "WHERE indexer_name = 'resolutions_uma'"
        ).fetchone()
        return int(row[0]) if row and row[0] else None

    return db_read_with_retry(db_path, _do)


def upsert_resolutions(db_path: str, resolutions: list[dict]) -> int:
    """Upsert resolutions into DB. Returns count of new/updated rows."""
    if not resolutions:
        return 0
    from polybot.db.connection import db_write_with_retry

    params = [
        (r["condition_id"], r["question_id"], r.get("settled_at"),
         r["final_price"], r["settled_outcome"])
        for r in resolutions
    ]

    def _do(con):
        before = con.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0]
        con.execute("""CREATE OR REPLACE TEMP TABLE _staging_res (
            condition_id VARCHAR, question_id VARCHAR, settled_at TIMESTAMP,
            final_price DOUBLE, settled_outcome VARCHAR
        )""")
        con.executemany(
            "INSERT INTO _staging_res VALUES (?, ?, ?, ?, ?)", params
        )
        con.execute(UPSERT_SQL)
        con.execute("DROP TABLE IF EXISTS _staging_res")
        after = con.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0]
        return after - before

    return db_write_with_retry(db_path, _do)


def update_indexer_state(
    db_path: str,
    last_block: int,
    status: str,
    count: int,
    duration_ms: int,
    error: str | None = None,
) -> None:
    """Update indexer_state for 'resolutions_uma'."""
    from polybot.db.connection import db_write_with_retry

    def _do(con):
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

    db_write_with_retry(db_path, _do)


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


def get_block_timestamps_batch(
    client: httpx.Client,
    url: str,
    block_numbers: set[int],
    cache: dict[int, datetime | None],
) -> dict[int, datetime | None]:
    """Fetch block timestamps using JSON-RPC batch calls."""
    to_fetch = sorted(block_numbers - set(cache.keys()))
    if not to_fetch:
        return cache

    BATCH_RPC = 50
    for i in range(0, len(to_fetch), BATCH_RPC):
        chunk = to_fetch[i : i + BATCH_RPC]
        batch_req = [
            {
                "jsonrpc": "2.0",
                "method": "eth_getBlockByNumber",
                "params": [hex(bn), False],
                "id": idx,
            }
            for idx, bn in enumerate(chunk)
        ]
        resp = client.post(url, json=batch_req)
        resp.raise_for_status()
        results = resp.json()
        if isinstance(results, list):
            for item, bn in zip(results, chunk, strict=False):
                block = item.get("result")
                if block and "timestamp" in block:
                    ts = int(block["timestamp"], 16)
                    cache[bn] = datetime.fromtimestamp(ts, tz=UTC)
                else:
                    cache[bn] = None
        time.sleep(0.1)

    return cache


class _GracefulStop(Exception):
    pass


def run(db_path: str, alchemy_url: str) -> int:
    """Main entry. Backfill or incremental scan for ConditionResolution events."""
    last_block = get_last_scanned_block(db_path)
    is_backfill = last_block is None

    start_time = time.monotonic()
    total_inserted = 0
    stop_requested = False

    def _handle_sigterm(_signum, _frame):
        nonlocal stop_requested
        stop_requested = True
        logger.info("resolutions_sigterm_received")

    import threading
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, _handle_sigterm)

    with httpx.Client(timeout=15.0) as client:
        from polybot.indexers.proxy_factory import get_current_block

        head = get_current_block(client, alchemy_url)

        start_block = BACKFILL_START_BLOCK if is_backfill else last_block + 1

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

        block_ts_cache: dict[int, datetime | None] = {}
        batch_num = 0
        batch_start = start_block

        try:
            while batch_start <= head:
                if stop_requested:
                    raise _GracefulStop("SIGTERM received")

                batch_end = min(batch_start + BATCH_SIZE_BLOCKS - 1, head)
                batch_num += 1

                events = fetch_resolution_events(
                    client, alchemy_url, batch_start, batch_end
                )

                if events:
                    resolutions = []
                    batch_blocks: set[int] = set()
                    for event in events:
                        parsed = parse_condition_resolution(event)
                        if not parsed:
                            continue
                        batch_blocks.add(parsed["block_number"])
                        resolutions.append(parsed)

                    if batch_blocks:
                        get_block_timestamps_batch(
                            client, alchemy_url, batch_blocks, block_ts_cache
                        )
                    for r in resolutions:
                        r["settled_at"] = block_ts_cache.get(r["block_number"])

                    inserted = upsert_resolutions(db_path, resolutions)
                    total_inserted += inserted

                current_block_end = batch_end

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

                if batch_num % CHECKPOINT_EVERY == 0:
                    duration_ms = int((time.monotonic() - start_time) * 1000)
                    update_indexer_state(
                        db_path, current_block_end, "running",
                        total_inserted, duration_ms,
                    )

                batch_start = batch_end + 1
                time.sleep(SLEEP_BETWEEN_BATCHES)

        except _GracefulStop:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            update_indexer_state(
                db_path, current_block_end, "failed",
                total_inserted, duration_ms,
            )
            logger.info(
                "resolutions_partial",
                last_block=current_block_end,
                resolutions=total_inserted,
                remaining_batches=total_batches - batch_num,
            )
            return total_inserted

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
