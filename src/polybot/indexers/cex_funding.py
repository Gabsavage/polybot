"""Trace CEX funding source for wallets via USDC transfers on Polygon."""

import time

import httpx
import structlog

logger = structlog.get_logger()

# --- Constants ---

REQUEST_TIMEOUT = 15.0
MAX_RPC_RETRIES = 5
RATE_LIMIT_SLEEP = 0.1

USDC_POLYGON = "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"
USDC_E_POLYGON = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"


# --- RPC helpers ---


class RPCError(Exception):
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
            if resp.status_code >= 500:
                logger.warning("rpc_5xx", status=resp.status_code)
                time.sleep(2)
                continue
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RPCError(data["error"].get("message", "unknown"))
            return data
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exc = e
            delay = 2**attempt
            logger.warning("rpc_network_error", error=str(e)[:100], retry_in=delay)
            time.sleep(delay)

    msg = f"RPC {method} failed after {MAX_RPC_RETRIES} retries"
    raise RPCError(msg) from last_exc


# --- Transfer lookups ---


def fetch_first_usdc_transfers(
    client: httpx.Client,
    alchemy_url: str,
    wallet: str,
    max_count: int = 5,
) -> list[dict]:
    """Fetch earliest USDC transfers into a wallet via Alchemy."""
    data = rpc_call(
        client,
        alchemy_url,
        "alchemy_getAssetTransfers",
        [
            {
                "toAddress": wallet,
                "category": ["erc20"],
                "contractAddresses": [USDC_POLYGON, USDC_E_POLYGON],
                "order": "asc",
                "maxCount": hex(max_count),
                "withMetadata": True,
            }
        ],
    )
    return data.get("result", {}).get("transfers", [])


def trace_funding_hops(
    client: httpx.Client,
    alchemy_url: str,
    wallet: str,
) -> dict:
    """Trace 2 hops of USDC funding for a wallet."""
    transfers = fetch_first_usdc_transfers(client, alchemy_url, wallet)
    if not transfers:
        return {"funded_by": None, "funded_by_hop2": None}

    funded_by = transfers[0]["from"].lower()

    time.sleep(RATE_LIMIT_SLEEP)

    hop2_transfers = fetch_first_usdc_transfers(client, alchemy_url, funded_by)
    funded_by_hop2 = hop2_transfers[0]["from"].lower() if hop2_transfers else None

    return {"funded_by": funded_by, "funded_by_hop2": funded_by_hop2}


# --- DB operations ---


def get_untraced_wallets(db_path: str, max_wallets: int) -> list[str]:
    """Find wallets in trades_all not yet traced in cex_funding_map."""
    from polybot.db.connection import db_read_with_retry

    def _do(con):
        rows = con.execute(
            """
            SELECT ta.proxy_wallet, SUM(ta.size_usd) as total_vol
            FROM trades_all ta
            LEFT JOIN cex_funding_map cfm
                ON ta.proxy_wallet = cfm.wallet_address
            WHERE cfm.wallet_address IS NULL
              AND ta.proxy_wallet IS NOT NULL
            GROUP BY ta.proxy_wallet
            ORDER BY total_vol DESC
            LIMIT ?
            """,
            [max_wallets],
        ).fetchall()
        return [r[0] for r in rows]

    return db_read_with_retry(db_path, _do)


def identify_cex(
    db_path: str,
    funded_by: str | None,
    funded_by_hop2: str | None,
) -> dict | None:
    """Match funding hops against cex_hot_wallets."""
    if funded_by is None:
        return None

    from polybot.db.connection import db_read_with_retry

    def _do(con):
        # Hop 1: direct hot wallet
        row = con.execute(
            "SELECT exchange_name FROM cex_hot_wallets WHERE address = ?",
            [funded_by.lower()],
        ).fetchone()
        if row:
            return {
                "cex_source": row[0],
                "method": "direct_hot_wallet",
                "deposit_address": None,
                "confidence": 1.0,
            }

        # Hop 2: via deposit address
        if funded_by_hop2 is not None:
            row = con.execute(
                "SELECT exchange_name FROM cex_hot_wallets WHERE address = ?",
                [funded_by_hop2.lower()],
            ).fetchone()
            if row:
                return {
                    "cex_source": row[0],
                    "method": "hop2_hot_wallet",
                    "deposit_address": funded_by.lower(),
                    "confidence": 0.9,
                }

        return None

    return db_read_with_retry(db_path, _do)


def insert_mapping(
    db_path: str,
    wallet: str,
    hops: dict,
    cex_result: dict | None,
) -> None:
    """Insert wallet funding mapping. ON CONFLICT DO NOTHING."""
    from polybot.db.connection import db_write_with_retry

    if cex_result:
        params = [
            wallet.lower(),
            hops["funded_by"],
            hops["funded_by_hop2"],
            cex_result["cex_source"],
            cex_result["deposit_address"],
            cex_result["confidence"],
            cex_result["method"],
        ]
    else:
        params = [
            wallet.lower(),
            hops["funded_by"],
            hops["funded_by_hop2"],
            None,
            None,
            0.0,
            None,
        ]

    def _do(con):
        con.execute(
            """
            INSERT INTO cex_funding_map (
                wallet_address, funded_by, funded_by_hop2,
                cex_source, deposit_address, confidence, method
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (wallet_address) DO NOTHING
            """,
            params,
        )

    db_write_with_retry(db_path, _do)


def update_indexer_state(
    db_path: str,
    status: str,
    count: int,
    duration_ms: int,
    error: str | None = None,
) -> None:
    """Update indexer_state for 'cex_funding'."""
    from polybot.db.connection import db_write_with_retry

    def _do(con):
        con.execute(
            """
            INSERT OR REPLACE INTO indexer_state (
                indexer_name, last_synced_at, last_run_status,
                last_run_duration_ms, ingested_count, last_error, updated_at
            ) VALUES ('cex_funding', NOW(), ?, ?, ?, ?, NOW())
            """,
            [status, duration_ms, count, error],
        )

    db_write_with_retry(db_path, _do)


# --- Main run ---


def run(db_path: str, alchemy_url: str, max_wallets: int = 100) -> int:
    """Trace funding for untraced wallets, identify CEX sources."""
    start_time = time.monotonic()

    wallets = get_untraced_wallets(db_path, max_wallets)
    if not wallets:
        logger.info("cex_funding_no_untraced")
        duration_ms = int((time.monotonic() - start_time) * 1000)
        update_indexer_state(db_path, "success", 0, duration_ms)
        return 0

    logger.info("cex_funding_starting", untraced=len(wallets))
    cex_matched = 0
    traced = 0

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for wallet in wallets:
            try:
                hops = trace_funding_hops(client, alchemy_url, wallet)
                cex_result = identify_cex(db_path, hops["funded_by"], hops["funded_by_hop2"])
                insert_mapping(db_path, wallet, hops, cex_result)
                traced += 1
                if cex_result:
                    cex_matched += 1
                logger.info(
                    "cex_funding_traced",
                    wallet=wallet[:12],
                    cex=cex_result["cex_source"] if cex_result else None,
                    method=cex_result["method"] if cex_result else None,
                )
            except Exception as e:
                logger.warning(
                    "cex_funding_wallet_error",
                    wallet=wallet[:12],
                    error=str(e)[:200],
                )

    duration_ms = int((time.monotonic() - start_time) * 1000)
    update_indexer_state(db_path, "success", cex_matched, duration_ms)
    logger.info(
        "cex_funding_complete",
        traced=traced,
        cex_matched=cex_matched,
        duration_ms=duration_ms,
    )
    return cex_matched


def main():
    from polybot.config import Settings
    from polybot.logging import setup_logging

    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    logger.info("cex_funding_indexer_starting")
    count = run(
        db_path=str(settings.DUCKDB_PATH),
        alchemy_url=settings.ALCHEMY_POLYGON_URL,
    )
    print(f"CEX funding indexer complete: {count} wallets matched to CEX")


if __name__ == "__main__":
    main()
