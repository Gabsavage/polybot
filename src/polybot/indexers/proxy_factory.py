"""Indexer proxy→EOA mapping via targeted wallet resolution.

Instead of scanning all ProxyCreation events on-chain (millions of
generic Gnosis Safe proxies), this indexer resolves EOAs for specific
tracked wallets using three methods:
1. getOwners() — for Gnosis Safe proxies (confidence 1.0)
2. First incoming transfer — for EIP-1167 proxies (confidence 0.8)
3. Self-mapping — for bare EOAs with no contract code (confidence 1.0)
"""

import time

import duckdb
import httpx
import structlog

from polybot.config import Settings
from polybot.logging import setup_logging

logger = structlog.get_logger()

# --- Constants ---

REQUEST_TIMEOUT = 15.0
MAX_RPC_RETRIES = 5


# --- RPC helpers ---


class RPCError(Exception):
    pass


class LogResponseTooLarge(RPCError):
    pass


def rpc_call(
    client: httpx.Client,
    url: str,
    method: str,
    params: list | None = None,
) -> dict:
    """JSON-RPC call with retry on 429/5xx."""
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


def get_current_block(client: httpx.Client, url: str) -> int:
    """eth_blockNumber → latest block as int."""
    result = rpc_call(client, url, "eth_blockNumber")
    return int(result["result"], 16)


# --- EOA resolution ---


def resolve_eoa(
    client: httpx.Client, url: str, wallet: str
) -> tuple[str, str, float]:
    """Resolve a proxy wallet address to its EOA owner.

    Returns (eoa_address, method, confidence).
    Methods: 'direct_factory' (Safe getOwners), 'first_tx', 'manual' (self-EOA).
    """
    # Step 1: Check if it's a contract
    code_result = rpc_call(client, url, "eth_getCode", [wallet, "latest"])
    code = code_result.get("result", "0x")

    if len(code) <= 2:
        # No contract code → wallet IS the EOA (trades via CLOB API off-chain)
        return wallet.lower(), "manual", 1.0

    # Step 2: Try getOwners() for Gnosis Safe
    try:
        owners_result = rpc_call(
            client, url, "eth_call",
            [{"to": wallet, "data": "0xa0e67e2b"}, "latest"],
        )
        result_data = owners_result.get("result", "0x")
        if len(result_data) > 130:
            data = result_data[2:]
            arr_len = int(data[64:128], 16)
            if arr_len > 0:
                eoa = "0x" + data[128 + 24 : 128 + 64]
                return eoa.lower(), "direct_factory", 1.0
    except RPCError:
        pass

    # Step 3: Fallback — first incoming external transfer
    try:
        transfers_result = rpc_call(
            client, url, "alchemy_getAssetTransfers",
            [{
                "toAddress": wallet,
                "category": ["external"],
                "maxCount": "0x1",
                "order": "asc",
            }],
        )
        txs = transfers_result.get("result", {}).get("transfers", [])
        if txs:
            return txs[0]["from"].lower(), "first_tx", 0.8
    except RPCError:
        pass

    # Step 4: Last resort — self-map with low confidence
    return wallet.lower(), "manual", 0.5


# --- DB operations ---


def get_unresolved_wallets(db_path: str) -> list[str]:
    """Find tracked wallets that don't have a proxy_eoa_map entry."""
    con = duckdb.connect(db_path, read_only=True)
    rows = con.execute(
        """
        SELECT tw.address
        FROM tracked_wallets tw
        LEFT JOIN proxy_eoa_map pem
            ON LOWER(tw.address) = LOWER(pem.proxy_address)
        WHERE pem.proxy_address IS NULL
          AND tw.active = TRUE
        """
    ).fetchall()
    con.close()
    return [r[0] for r in rows]


def upsert_mapping(
    db_path: str,
    proxy: str,
    eoa: str,
    confidence: float,
    method: str,
) -> None:
    """Insert or update a proxy→EOA mapping."""
    from polybot.db.connection import db_write_with_retry

    def _do(con):
        con.execute(
            """
            INSERT INTO proxy_eoa_map
                (proxy_address, eoa_address, confidence, method)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (proxy_address) DO UPDATE SET
                eoa_address = EXCLUDED.eoa_address,
                confidence = EXCLUDED.confidence,
                method = EXCLUDED.method
            """,
            [proxy.lower(), eoa, confidence, method],
        )

    db_write_with_retry(db_path, _do)


def update_indexer_state(
    db_path: str,
    status: str,
    count: int,
    duration_ms: int,
    error: str | None = None,
) -> None:
    """Update indexer_state for 'proxy_factory'."""
    from polybot.db.connection import db_write_with_retry

    def _do(con):
        con.execute(
            """
            INSERT OR REPLACE INTO indexer_state (
                indexer_name, last_synced_at, last_run_status,
                last_run_duration_ms, ingested_count, last_error, updated_at
            ) VALUES ('proxy_factory', NOW(), ?, ?, ?, ?, NOW())
            """,
            [status, duration_ms, count, error],
        )

    db_write_with_retry(db_path, _do)


# --- Main run ---


def run(db_path: str, alchemy_url: str) -> int:
    """Resolve EOAs for any tracked wallets missing from proxy_eoa_map."""
    start_time = time.monotonic()

    unresolved = get_unresolved_wallets(db_path)
    if not unresolved:
        logger.info("proxy_factory_no_unresolved")
        duration_ms = int((time.monotonic() - start_time) * 1000)
        update_indexer_state(db_path, "success", 0, duration_ms)
        return 0

    logger.info("proxy_factory_starting", unresolved=len(unresolved))
    resolved = 0

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        try:
            for wallet in unresolved:
                eoa, method, confidence = resolve_eoa(client, alchemy_url, wallet)
                upsert_mapping(db_path, wallet, eoa, confidence, method)
                resolved += 1
                logger.info(
                    "eoa_resolved",
                    wallet=wallet[:12],
                    eoa=eoa[:12],
                    method=method,
                    confidence=confidence,
                )
        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            update_indexer_state(
                db_path, "failed", resolved, duration_ms, str(e)[:500]
            )
            logger.error("proxy_factory_failed", error=str(e)[:200])
            raise

    duration_ms = int((time.monotonic() - start_time) * 1000)
    update_indexer_state(db_path, "success", resolved, duration_ms)
    logger.info(
        "proxy_factory_complete",
        resolved=resolved,
        duration_ms=duration_ms,
    )
    return resolved


def main():
    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    logger.info("proxy_factory_indexer_starting")
    count = run(
        db_path=str(settings.DUCKDB_PATH),
        alchemy_url=settings.ALCHEMY_POLYGON_URL,
    )
    print(f"Proxy factory indexer complete: {count} wallets resolved")


if __name__ == "__main__":
    main()
