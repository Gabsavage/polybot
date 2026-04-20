#!/usr/bin/env python3
"""Discover Tier A wallet candidates from Polymarket trading data.

Strategy:
1. Collect wallet candidates from top market holders (Data API /holders)
2. For each candidate, pull their full trade history (Data API /trades)
3. Aggregate metrics per wallet
4. Apply quantitative filters (rapport 4 §4.3)
5. Score and rank top 30 candidates

Requires: US VPN active, .env configured.
Run: PYTHONPATH=src uv run python research/discover_tier_a/discover_candidates.py
"""

import csv
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

# Rate limiting: ~1 req/s to be safe with Data API
REQUEST_DELAY = 1.0


def load_known_sharps(path: str = "data/ground_truth/sharps_positive.csv") -> set[str]:
    """Load known sharp wallet addresses to exclude from candidates."""
    addresses = set()
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = row.get("address", "").strip().lower()
            if addr:
                addresses.add(addr)
    return addresses


def load_known_insiders(path: str = "data/ground_truth/wallets.csv") -> set[str]:
    """Load known insider wallet addresses to exclude."""
    addresses = set()
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = row.get("address", "").strip().lower()
            if addr:
                addresses.add(addr)
    return addresses


def fetch_top_market_ids(n: int = 150) -> list[str]:
    """Fetch top N active market condition IDs from Gamma, sorted by volume."""
    all_ids = []
    offset = 0
    page_size = 100

    while len(all_ids) < n:
        resp = httpx.get(
            f"{GAMMA_API}/markets",
            params={
                "active": "true",
                "closed": "false",
                "limit": page_size,
                "offset": offset,
                "order": "volume24hr",
                "ascending": "false",
            },
            timeout=30,
        )
        resp.raise_for_status()
        markets = resp.json()
        if not markets:
            break
        for m in markets:
            cid = m.get("conditionId")
            if cid:
                all_ids.append(cid)
        offset += page_size
        time.sleep(0.5)

    return all_ids[:n]


def discover_wallets_from_holders(market_ids: list[str]) -> dict[str, dict]:
    """Fetch holders for each market, collect unique wallets with metadata.

    Returns dict of {address: {name, total_position_value, markets_seen}}.
    """
    wallets: dict[str, dict] = {}
    total = len(market_ids)

    for i, cid in enumerate(market_ids):
        try:
            resp = httpx.get(
                f"{DATA_API}/holders",
                params={"market": cid},
                timeout=30,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()

            for token_data in data:
                for h in token_data.get("holders", []):
                    addr = (h.get("proxyWallet") or "").lower()
                    if not addr:
                        continue
                    amount = float(h.get("amount") or 0)

                    if addr not in wallets:
                        wallets[addr] = {
                            "name": h.get("name", ""),
                            "total_position_value": 0,
                            "markets_seen": set(),
                        }
                    wallets[addr]["total_position_value"] += amount
                    wallets[addr]["markets_seen"].add(cid)
                    # Keep the most recent non-empty name
                    if h.get("name") and not wallets[addr]["name"]:
                        wallets[addr]["name"] = h["name"]

        except Exception as e:
            print(f"  [WARN] holders failed for market {i+1}/{total}: {e}")

        if (i + 1) % 25 == 0:
            print(f"  Holders: {i+1}/{total} markets scanned, {len(wallets)} unique wallets")
        time.sleep(REQUEST_DELAY * 0.5)

    print(f"  Holders done: {len(wallets)} unique wallets from {total} markets")
    return wallets


def fetch_wallet_trades(address: str, limit: int = 5000) -> list[dict]:
    """Fetch all trades for a wallet via Data API /trades (paginated)."""
    all_trades = []
    cursor = None

    while len(all_trades) < limit:
        params = {"user": address, "limit": 100}
        if cursor:
            params["cursor"] = cursor

        try:
            resp = httpx.get(f"{DATA_API}/trades", params=params, timeout=30)
            if resp.status_code != 200:
                break
            trades = resp.json()
            if not trades:
                break
            all_trades.extend(trades)

            # Data API uses cursor-based pagination via the last item's timestamp
            if len(trades) < 100:
                break
            cursor = trades[-1].get("timestamp")
            if not cursor:
                break
        except Exception as e:
            print(f"    [WARN] trades fetch error for {address[:12]}...: {e}")
            break

        time.sleep(REQUEST_DELAY)

    return all_trades


def aggregate_wallet_metrics(trades: list[dict]) -> dict:
    """Aggregate trade-level data into wallet metrics."""
    if not trades:
        return {}

    markets = set()
    categories = set()  # We'll approximate from market titles
    total_pnl = 0.0
    buy_count = 0
    sell_count = 0
    timestamps = []
    token_sides: dict[str, dict[str, int]] = defaultdict(lambda: {"BUY": 0, "SELL": 0})

    for t in trades:
        cid = t.get("conditionId", "")
        markets.add(cid)

        # Approximate category from title keywords
        title = (t.get("title") or "").lower()
        cat = categorize_market(title)
        if cat:
            categories.add(cat)

        side = t.get("side", "")
        size = float(t.get("size") or 0)
        price = float(t.get("price") or 0)

        # Approximate PnL: buy at price, value at 0.5 baseline
        # This is rough — real PnL needs resolution data
        if side == "BUY":
            total_pnl += size * (1.0 - price)  # max upside if correct
            buy_count += 1
        elif side == "SELL":
            total_pnl += size * price  # realized from selling
            sell_count += 1

        token_id = t.get("asset", "")
        if token_id and side:
            token_sides[token_id][side] += 1

        ts = t.get("timestamp")
        if ts:
            timestamps.append(int(ts))

    # HHI on categories
    if categories:
        cat_counts = defaultdict(int)
        for t in trades:
            cat = categorize_market((t.get("title") or "").lower())
            if cat:
                cat_counts[cat] += 1
        total_cat = sum(cat_counts.values())
        hhi = sum((c / total_cat) ** 2 for c in cat_counts.values()) if total_cat > 0 else 1.0
    else:
        hhi = 1.0

    # Market maker detection: ratio buy/sell per token
    mm_score = 0
    mm_tokens_checked = 0
    for _token_id, sides in token_sides.items():
        total = sides["BUY"] + sides["SELL"]
        if total >= 10:
            mm_tokens_checked += 1
            ratio = min(sides["BUY"], sides["SELL"]) / max(sides["BUY"], sides["SELL"])
            if ratio > 0.4:  # ~50/50 buy/sell = likely MM
                mm_score += 1

    is_market_maker = (mm_tokens_checked > 0 and mm_score / mm_tokens_checked > 0.5)

    # Temporal metrics
    if timestamps:
        timestamps.sort()
        first_trade = datetime.fromtimestamp(timestamps[0], tz=UTC)
        last_trade = datetime.fromtimestamp(timestamps[-1], tz=UTC)
        days_active = max((last_trade - first_trade).days, 1)

        # Temporal consistency: std dev of inter-trade intervals
        if len(timestamps) > 1:
            intervals = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
            mean_interval = sum(intervals) / len(intervals)
            variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
            temporal_consistency = 1.0 / (1.0 + (variance**0.5) / 86400)  # normalized
        else:
            temporal_consistency = 0.0
    else:
        first_trade = None
        last_trade = None
        days_active = 0
        temporal_consistency = 0.0

    n_trades = len(trades)
    win_rate = buy_count / n_trades if n_trades > 0 else 0

    return {
        "trades_count": n_trades,
        "k_markets": len(markets),
        "l_categories": len(categories),
        "hhi_cat": round(hhi, 4),
        "pnl_lifetime": round(total_pnl, 2),
        "win_rate_approx": round(win_rate, 4),
        "first_trade": first_trade,
        "last_trade": last_trade,
        "days_active": days_active,
        "temporal_consistency": round(temporal_consistency, 4),
        "is_market_maker": is_market_maker,
        "mm_tokens_checked": mm_tokens_checked,
        "mm_score": mm_score,
    }


def categorize_market(title: str) -> str | None:
    """Simple keyword-based category from market title."""
    politics = ["president", "election", "trump", "biden", "congress", "senate", "governor",
                "democrat", "republican", "gop", "vote", "political", "party", "primary"]
    sports = ["win the", "nba", "nfl", "mlb", "nhl", "fifa", "world cup", "super bowl",
              "championship", "playoffs", "tennis", "open", "grand slam", "ufc", "boxing"]
    crypto = ["bitcoin", "btc", "ethereum", "eth", "crypto", "token", "defi", "solana",
              "dogecoin", "xrp", "altcoin", "stablecoin", "nft"]
    geopolitics = ["war", "ceasefire", "peace", "invasion", "nato", "sanction", "iran",
                   "russia", "ukraine", "china", "taiwan", "israel", "hezbollah", "gaza"]
    culture = ["oscar", "grammy", "emmy", "movie", "album", "kardashian", "celebrity",
               "tiktok", "twitter", "youtube", "pope", "royal"]

    for kw in politics:
        if kw in title:
            return "politics"
    for kw in geopolitics:
        if kw in title:
            return "geopolitics"
    for kw in sports:
        if kw in title:
            return "sports"
    for kw in crypto:
        if kw in title:
            return "crypto"
    for kw in culture:
        if kw in title:
            return "culture"
    return "other"


def compute_composite_score(metrics: dict) -> float:
    """Composite score: z-score normalization on PnL + trades + diversification."""
    # Raw components (will be normalized across all candidates)
    return metrics.get("pnl_lifetime", 0)  # placeholder, normalized in batch


def normalize_and_score(candidates: list[dict]) -> list[dict]:
    """Normalize metrics across candidates and compute composite score."""
    if not candidates:
        return []

    # Extract raw values
    pnls = [c["pnl_lifetime"] for c in candidates]
    trades = [c["trades_count"] for c in candidates]
    diversities = [c["k_markets"] for c in candidates]

    def z_scores(values: list[float]) -> list[float]:
        if len(values) < 2:
            return [0.0] * len(values)
        mean = sum(values) / len(values)
        std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
        if std == 0:
            return [0.0] * len(values)
        return [(v - mean) / std for v in values]

    z_pnl = z_scores(pnls)
    z_trades = z_scores(trades)
    z_div = z_scores(diversities)

    for i, c in enumerate(candidates):
        c["composite_score"] = round(
            0.50 * z_pnl[i] + 0.25 * z_trades[i] + 0.25 * z_div[i], 4
        )

    candidates.sort(key=lambda c: c["composite_score"], reverse=True)
    return candidates


def main():
    print("=" * 60)
    print("Tier A Wallet Discovery")
    print(f"Started: {datetime.now(UTC).isoformat()}")
    print("=" * 60)

    # Load exclusion lists
    known_sharps = load_known_sharps()
    known_insiders = load_known_insiders()
    exclude = known_sharps | known_insiders
    print(
        f"\nExclusion list: {len(known_sharps)} sharps + "
        f"{len(known_insiders)} insiders = {len(exclude)} total"
    )

    # Step 1: Get top markets
    print("\n--- Step 1: Fetching top markets from Gamma ---")
    market_ids = fetch_top_market_ids(n=150)
    print(f"Fetched {len(market_ids)} market IDs")

    # Step 2: Discover wallets from holders
    print("\n--- Step 2: Discovering wallets from holders ---")
    wallet_pool = discover_wallets_from_holders(market_ids)

    # Filter out known addresses
    filtered_pool = {
        addr: info for addr, info in wallet_pool.items()
        if addr not in exclude
    }
    excluded_count = len(wallet_pool) - len(filtered_pool)
    print(f"After exclusion filter: {len(filtered_pool)} wallets (removed {excluded_count})")

    # Pre-filter: only wallets seen in >= 3 markets (to reduce API calls)
    prefiltered = {
        addr: info for addr, info in filtered_pool.items()
        if len(info["markets_seen"]) >= 3
    }
    print(f"After pre-filter (>= 3 markets): {len(prefiltered)} wallets")

    # Step 3: Fetch trades for each candidate
    print(f"\n--- Step 3: Fetching trades for {len(prefiltered)} candidates ---")
    print(f"Estimated time: ~{len(prefiltered) * 3}s ({len(prefiltered) * 3 / 60:.0f} min)")

    candidates = []
    mm_excluded = 0
    filter_log = {"total_scanned": 0, "too_few_trades": 0, "too_few_markets": 0,
                  "too_few_categories": 0, "hhi_too_high": 0, "pnl_too_low": 0,
                  "inactive": 0, "market_maker": 0, "passed": 0}

    for i, (addr, info) in enumerate(prefiltered.items()):
        filter_log["total_scanned"] += 1

        trades = fetch_wallet_trades(addr)
        if not trades:
            continue

        # Get name from first trade or holder info
        name = info.get("name", "") or (trades[0].get("name", "") if trades else "")

        metrics = aggregate_wallet_metrics(trades)
        if not metrics:
            continue

        # Apply filters (rapport 4 §4.3)
        if metrics["trades_count"] < 100:
            filter_log["too_few_trades"] += 1
            continue
        if metrics["k_markets"] < 20:
            filter_log["too_few_markets"] += 1
            continue
        if metrics["l_categories"] < 3:
            filter_log["too_few_categories"] += 1
            continue
        if metrics["hhi_cat"] >= 0.5:
            filter_log["hhi_too_high"] += 1
            continue
        if metrics["pnl_lifetime"] < 50_000:
            filter_log["pnl_too_low"] += 1
            continue
        if metrics["last_trade"] and (datetime.now(UTC) - metrics["last_trade"]).days > 30:
            filter_log["inactive"] += 1
            continue
        if metrics["is_market_maker"]:
            filter_log["market_maker"] += 1
            mm_excluded += 1
            continue

        filter_log["passed"] += 1
        candidates.append({
            "address": addr,
            "alias_if_known": name,
            "polymarket_url": f"https://polymarket.com/profile/{addr}",
            **metrics,
        })

        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(prefiltered)}, {len(candidates)} candidates so far")

    print("\n--- Filter results ---")
    for k, v in filter_log.items():
        print(f"  {k}: {v}")
    print(f"  Market makers excluded: {mm_excluded}")

    # Step 4: Normalize and score
    print(f"\n--- Step 4: Scoring {len(candidates)} candidates ---")
    candidates = normalize_and_score(candidates)

    # Take top 30
    top30 = candidates[:30]

    # Step 5: Write output
    output_date = datetime.now(UTC).strftime("%Y%m%d")
    output_path = f"data/research_outputs/tier_a_candidates_{output_date}.csv"

    fieldnames = [
        "address", "alias_if_known", "pnl_lifetime", "trades_count", "k_markets",
        "l_categories", "hhi_cat", "win_rate_approx", "first_trade", "last_trade",
        "days_active", "temporal_consistency", "composite_score", "polymarket_url",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for c in top30:
            row = {**c}
            if row.get("first_trade"):
                row["first_trade"] = row["first_trade"].strftime("%Y-%m-%d")
            if row.get("last_trade"):
                row["last_trade"] = row["last_trade"].strftime("%Y-%m-%d")
            writer.writerow(row)

    print(f"\nOutput: {output_path}")
    print("Top 30 candidates written")

    # Print summary table
    print(f"\n{'='*80}")
    print(f"{'Rank':<5} {'Alias':<20} {'PnL':>12} {'Trades':>7} {'Markets':>8} {'Score':>7}")
    print(f"{'-'*80}")
    for i, c in enumerate(top30[:15], 1):
        alias = (c["alias_if_known"] or c["address"][:12] + "...")[:20]
        pnl = c["pnl_lifetime"]
        tc = c["trades_count"]
        km = c["k_markets"]
        sc = c["composite_score"]
        print(f"{i:<5} {alias:<20} ${pnl:>10,.0f} {tc:>7} {km:>8} {sc:>7.3f}")

    print(f"\nDone. {datetime.now(UTC).isoformat()}")


if __name__ == "__main__":
    main()
