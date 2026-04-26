"""Live integration test for CEX funding tracer.

Requires ALCHEMY_POLYGON_URL environment variable.
"""

import os

import httpx
import pytest

from polybot.indexers.cex_funding import (
    REQUEST_TIMEOUT,
    fetch_first_usdc_transfers,
    trace_funding_hops,
)

ALCHEMY_URL = os.environ.get("ALCHEMY_POLYGON_URL", "")

pytestmark = pytest.mark.skipif(not ALCHEMY_URL, reason="ALCHEMY_POLYGON_URL not set")


# Known active Tier A wallet (Domer)
TIER_A_WALLET = "0x9d84ce0306f8551e02efef1680475fc0f1dc1344"


class TestLiveFunding:
    def test_fetch_transfers(self):
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            transfers = fetch_first_usdc_transfers(client, ALCHEMY_URL, TIER_A_WALLET, max_count=3)
        assert len(transfers) > 0
        assert "from" in transfers[0]
        assert "value" in transfers[0]

    def test_trace_hops(self):
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            result = trace_funding_hops(client, ALCHEMY_URL, TIER_A_WALLET)
        assert result["funded_by"] is not None
        assert result["funded_by"].startswith("0x")
