"""Indexer proxy→EOA mapping via ProxyCreation events on Polygon."""

import time

import duckdb
import httpx
import structlog

from polybot.config import Settings
from polybot.logging import setup_logging

logger = structlog.get_logger()

# --- Constants ---

GNOSIS_SAFE_FACTORY = "0xa6b71e26c5e0845f74c812102ca7114b6a896ab2"
POLYMARKET_FACTORY = "0xaB45c5A4B0c941a2F231C04C3f49182e1A254052"

# keccak256("ProxyCreation(address,address)")
PROXY_CREATION_TOPIC = (
    "0x4f51faf6c4561ff95f067657e43439f0f856d97c04d9ec9070a6199ad418e235"
)

# Factories to scan — Gnosis is active, Polymarket is kept for future discovery
FACTORIES = {
    GNOSIS_SAFE_FACTORY: {"name": "gnosis_safe", "confidence": 0.8},
    POLYMARKET_FACTORY: {"name": "polymarket", "confidence": 1.0},
}

BATCH_SIZE_BLOCKS = 2000  # PAYG tier supports wide ranges
SLEEP_BETWEEN_BATCHES = 0.1
BACKFILL_START_BLOCK = 11_000_000
REQUEST_TIMEOUT = 15.0
MAX_RPC_RETRIES = 5
LOG_EVERY_N_BATCHES = 100

INSERT_SQL = """
INSERT INTO proxy_eoa_map
    (proxy_address, eoa_address, confidence, method,
     first_seen_block, first_seen_ts, factory_contract)
VALUES (?, ?, ?, 'direct_factory', ?, ?, ?)
ON CONFLICT (proxy_address) DO NOTHING
"""


# --- RPC helpers ---


def rpc_call(
    client: httpx.Client,
    url: str,
    method: str,
    params: list | None = None,
) -> dict:
    """JSON-RPC call with retry on 429/5xx and log-size errors."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RPC_RETRIES):
        try:
            resp = client.post(
                url,
                json={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params or [],
                    "id": 1,
                },
            )
            if resp.status_code == 429:
                delay = 2**attempt
                logger.warning("rpc_429", method=method, retry_in=delay)
                time.sleep(delay)
                continue
            if resp.status_code == 400:
                # Alchemy free tier returns 400 for block range too wide
                try:
                    data = resp.json()
                    if "error" in data:
                        err_msg = data["error"].get("message", "")
                        if "block range" in err_msg.lower():
                            raise LogResponseTooLarge(err_msg)
                        raise RPCError(f"RPC 400: {err_msg}")
                except (ValueError, KeyError):
                    pass
                raise RPCError(f"RPC 400 Bad Request for {method}")
            if resp.status_code >= 500:
                logger.warning("rpc_5xx", status=resp.status_code)
                time.sleep(2)
                continue
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                err_msg = data["error"].get("message", "")
                if "Log response size exceeded" in err_msg:
                    raise LogResponseTooLarge(err_msg)
                raise RPCError(err_msg)
            return data
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exc = e
            delay = 2**attempt
            logger.warning(
                "rpc_network_error", error=str(e)[:100], retry_in=delay
            )
            time.sleep(delay)

    msg = f"RPC {method} failed after {MAX_RPC_RETRIES} retries"
    raise RPCError(msg) from last_exc


class RPCError(Exception):
    pass


class LogResponseTooLarge(RPCError):
    pass


# --- Core functions ---


def get_current_block(client: httpx.Client, url: str) -> int:
    """eth_blockNumber → latest block as int."""
    result = rpc_call(client, url, "eth_blockNumber")
    return int(result["result"], 16)


def get_last_scanned_block(db_path: str) -> int | None:
    """Read last_cursor from indexer_state. None = backfill needed."""
    con = duckdb.connect(db_path, read_only=True)
    row = con.execute(
        "SELECT last_cursor FROM indexer_state "
        "WHERE indexer_name = 'proxy_factory'"
    ).fetchone()
    con.close()
    if row and row[0]:
        return int(row[0])
    return None


def fetch_proxy_creation_events(
    client: httpx.Client,
    url: str,
    from_block: int,
    to_block: int,
    factory: str,
    _min_batch: int = 10,
) -> list[dict]:
    """eth_getLogs for ProxyCreation events, with recursive splitting on range errors."""
    try:
        result = rpc_call(
            client,
            url,
            "eth_getLogs",
            [
                {
                    "fromBlock": hex(from_block),
                    "toBlock": hex(to_block),
                    "address": factory,
                    "topics": [PROXY_CREATION_TOPIC],
                }
            ],
        )
        return result.get("result", [])
    except LogResponseTooLarge:
        if to_block - from_block < _min_batch:
            logger.warning(
                "block_range_too_small_to_split",
                from_block=from_block,
                to_block=to_block,
            )
            return []
        mid = from_block + (to_block - from_block) // 2
        left = fetch_proxy_creation_events(
            client, url, from_block, mid, factory, _min_batch
        )
        right = fetch_proxy_creation_events(
            client, url, mid + 1, to_block, factory, _min_batch
        )
        return left + right


def parse_proxy_from_event(event: dict) -> str:
    """Extract proxy address from event data.

    ProxyCreation(address proxy, address singleton) — both params are
    non-indexed, packed in data as two 32-byte ABI-encoded words.
    Proxy address is the first word (bytes 0-32), zero-padded left.
    """
    data = event.get("data", "0x")
    if len(data) < 66:
        raise ValueError(f"Event data too short: {data[:20]}")
    # First 32-byte word = proxy address (last 20 bytes)
    return "0x" + data[26:66]


def get_tx_sender(client: httpx.Client, url: str, tx_hash: str) -> str:
    """eth_getTransactionByHash → return 'from' field."""
    result = rpc_call(client, url, "eth_getTransactionByHash", [tx_hash])
    tx = result.get("result")
    if not tx or "from" not in tx:
        raise RPCError(f"No tx found for {tx_hash}")
    return tx["from"]


def process_events(
    client: httpx.Client,
    url: str,
    events: list[dict],
    factory: str,
) -> list[dict]:
    """Parse events → list of mapping dicts ready for DB insert."""
    confidence = FACTORIES[factory]["confidence"]
    mappings = []
    tx_cache: dict[str, str] = {}

    for event in events:
        try:
            proxy = parse_proxy_from_event(event)
            tx_hash = event["transactionHash"]
            block_num = int(event["blockNumber"], 16)

            # Cache tx lookups — multiple events can come from the same tx
            if tx_hash not in tx_cache:
                tx_cache[tx_hash] = get_tx_sender(client, url, tx_hash)
            eoa = tx_cache[tx_hash]

            mappings.append(
                {
                    "proxy_address": proxy.lower(),
                    "eoa_address": eoa.lower(),
                    "confidence": confidence,
                    "first_seen_block": block_num,
                    "first_seen_ts": None,  # could resolve via block timestamp, skip for v1
                    "factory_contract": factory,
                }
            )
        except Exception:
            logger.warning(
                "event_parse_failed",
                tx=event.get("transactionHash", "?")[:16],
                factory=FACTORIES[factory]["name"],
            )

    return mappings


def insert_mappings(db_path: str, mappings: list[dict]) -> int:
    """Insert mappings into proxy_eoa_map. Returns count of new rows."""
    if not mappings:
        return 0
    con = duckdb.connect(db_path)
    before = con.execute("SELECT COUNT(*) FROM proxy_eoa_map").fetchone()[0]
    for m in mappings:
        con.execute(
            INSERT_SQL,
            [
                m["proxy_address"],
                m["eoa_address"],
                m["confidence"],
                m["first_seen_block"],
                m["first_seen_ts"],
                m["factory_contract"],
            ],
        )
    after = con.execute("SELECT COUNT(*) FROM proxy_eoa_map").fetchone()[0]
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
    """Update indexer_state for 'proxy_factory'."""
    con = duckdb.connect(db_path)
    con.execute(
        """
        INSERT OR REPLACE INTO indexer_state (
            indexer_name, last_synced_at, last_block_number, last_cursor,
            last_run_status, last_run_duration_ms, ingested_count,
            last_error, updated_at
        ) VALUES ('proxy_factory', NOW(), ?, ?, ?, ?, ?, ?, NOW())
        """,
        [last_block, str(last_block), status, duration_ms, count, error],
    )
    con.close()


# --- Main run logic ---


def run(db_path: str, alchemy_url: str) -> int:
    """Main entry. Detects backfill vs incremental, scans factories."""
    last_block = get_last_scanned_block(db_path)
    is_backfill = last_block is None

    start_time = time.monotonic()
    total_inserted = 0

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        head = get_current_block(client, alchemy_url)

        start_block = BACKFILL_START_BLOCK if is_backfill else last_block + 1

        current_block_end = start_block
        total_batches = max(
            1, (head - start_block + BATCH_SIZE_BLOCKS) // BATCH_SIZE_BLOCKS
        )

        mode = "backfill" if is_backfill else "incremental"
        logger.info(
            "proxy_factory_starting",
            mode=mode,
            from_block=start_block,
            to_block=head,
            total_batches=total_batches,
        )

        if start_block > head:
            logger.info("proxy_factory_already_synced", head=head)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            update_indexer_state(
                db_path, head, "success", 0, duration_ms
            )
            return 0

        batch_num = 0
        batch_start = start_block

        try:
            while batch_start <= head:
                batch_end = min(batch_start + BATCH_SIZE_BLOCKS - 1, head)
                batch_num += 1

                for factory in FACTORIES:
                    events = fetch_proxy_creation_events(
                        client, alchemy_url, batch_start, batch_end, factory
                    )

                    if events:
                        mappings = process_events(
                            client, alchemy_url, events, factory
                        )
                        inserted = insert_mappings(db_path, mappings)
                        total_inserted += inserted

                if batch_num % LOG_EVERY_N_BATCHES == 0 or batch_num == 1:
                    pct = batch_num / total_batches * 100
                    logger.info(
                        "scan_progress",
                        batch=batch_num,
                        total_batches=total_batches,
                        pct=f"{pct:.1f}",
                        block=batch_end,
                        proxies_so_far=total_inserted,
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
                "proxy_factory_failed",
                error=str(e)[:200],
                last_block=current_block_end,
                proxies=total_inserted,
            )
            raise

    duration_ms = int((time.monotonic() - start_time) * 1000)
    update_indexer_state(
        db_path, head, "success", total_inserted, duration_ms
    )
    logger.info(
        "proxy_factory_complete",
        mode=mode,
        proxies=total_inserted,
        duration_s=round(duration_ms / 1000, 1),
        head=head,
    )
    return total_inserted


def main():
    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    logger.info("proxy_factory_indexer_starting")
    count = run(
        db_path=str(settings.DUCKDB_PATH),
        alchemy_url=settings.ALCHEMY_POLYGON_URL,
    )
    print(f"Proxy factory indexer complete: {count} new mappings")


if __name__ == "__main__":
    main()
