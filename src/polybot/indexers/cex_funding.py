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
