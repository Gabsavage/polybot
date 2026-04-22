#!/usr/bin/env python3
"""Discover Tier A wallet candidates from Polymarket trading data (v2).

Strategy:
1. Collect wallet candidates from top market holders (Data API /holders)
2. For each candidate, fetch portfolio value (Data API /value)
3. For promising wallets (portfolio >= $1K), pull trade history (progressive pagination up to 10K)
4. Aggregate metrics, detect red flags, auto-classify A1/A2/reject
5. Score and rank

portfolio_value_usd is the current Polymarket portfolio value, NOT lifetime PnL.
Biased towards wallets that haven't withdrawn gains.
Will be refined in M7 with tracking deposits/withdraws on-chain via Polymarket Proxy events.

Composite score:
  Z(portfolio_value_capped_p99) * 0.40
  + Z(trades_count_capped_p99) * 0.20
  + Z(k_markets) * 0.15
  + Z(l_categories) * 0.10
  + Z(days_active) * 0.15

Run: PYTHONPATH=src uv run python -u research/discover_tier_a/discover_candidates.py
"""

import csv
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

import httpx

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
REQUEST_DELAY = 0.3
MAX_TRADES = 10_000

# Known Polymarket system contracts to flag
KNOWN_SYSTEM_CONTRACTS = {
    "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e",  # CTF Exchange (NegRisk)
    "0xd91e80cf2e7be2e162c6513ced06f1dd0da35296",  # NegRisk Adapter
    "0x4d97dcd97ec945f40cf65f87097ace5ea0476045",  # ConditionalTokens
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",  # USDC.e bridge
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_exclusion_addresses() -> set[str]:
    """Load known sharps + insiders + already-seeded wallets to exclude."""
    addresses = set()
    for path in [
        "data/ground_truth/sharps_positive.csv",
        "data/ground_truth/wallets.csv",
    ]:
        try:
            with open(path) as f:
                for row in csv.DictReader(f):
                    addr = row.get("address", "").strip().lower()
                    if addr:
                        addresses.add(addr)
        except FileNotFoundError:
            pass

    # Also exclude wallets already in seed list
    try:
        import yaml

        with open("config/tracked_wallets_seed.yaml") as f:
            seed = yaml.safe_load(f)
        for w in seed.get("wallets", []):
            addr = w.get("address", "").strip().lower()
            if addr:
                addresses.add(addr)
    except Exception:
        pass

    return addresses


# ---------------------------------------------------------------------------
# API fetchers
# ---------------------------------------------------------------------------


def fetch_top_market_ids(n: int = 150) -> list[str]:
    all_ids = []
    offset = 0
    while len(all_ids) < n:
        resp = httpx.get(
            f"{GAMMA_API}/markets",
            params={
                "active": "true",
                "closed": "false",
                "limit": 100,
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
        offset += 100
        time.sleep(0.5)
    return all_ids[:n]


def discover_wallets_from_holders(market_ids: list[str]) -> dict[str, dict]:
    wallets: dict[str, dict] = {}
    total = len(market_ids)
    for i, cid in enumerate(market_ids):
        try:
            resp = httpx.get(
                f"{DATA_API}/holders", params={"market": cid}, timeout=30
            )
            if resp.status_code != 200:
                continue
            for token_data in resp.json():
                for h in token_data.get("holders", []):
                    addr = (h.get("proxyWallet") or "").lower()
                    if not addr:
                        continue
                    if addr not in wallets:
                        wallets[addr] = {"name": h.get("name", ""), "markets_seen": set()}
                    wallets[addr]["markets_seen"].add(cid)
                    if h.get("name") and not wallets[addr]["name"]:
                        wallets[addr]["name"] = h["name"]
        except Exception as e:
            print(f"  [WARN] holders failed {i+1}/{total}: {e}")
        if (i + 1) % 25 == 0:
            print(f"  Holders: {i+1}/{total}, {len(wallets)} wallets")
        time.sleep(REQUEST_DELAY * 0.5)
    print(f"  Holders done: {len(wallets)} wallets from {total} markets")
    return wallets


def fetch_portfolio_value(address: str) -> float | None:
    try:
        resp = httpx.get(f"{DATA_API}/value", params={"user": address}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list):
                return float(data[0].get("value", 0))
    except Exception:
        pass
    return None


def fetch_top_position_concentration(address: str) -> float | None:
    """Fetch positions, return fraction of portfolio in single largest market."""
    try:
        resp = httpx.get(
            f"{DATA_API}/positions",
            params={"user": address, "limit": 100},
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        positions = resp.json()
        if not positions:
            return None

        # Group by conditionId, sum currentValue
        market_values: dict[str, float] = defaultdict(float)
        for p in positions:
            cid = p.get("conditionId", "")
            cv = float(p.get("currentValue") or 0)
            market_values[cid] += cv

        total = sum(market_values.values())
        if total <= 0:
            return None
        top_market = max(market_values.values())
        return top_market / total
    except Exception:
        return None


def _fetch_page(address: str, limit: int, offset: int) -> list[dict]:
    try:
        resp = httpx.get(
            f"{DATA_API}/trades",
            params={"user": address, "limit": limit, "offset": offset},
            timeout=15,
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def fetch_wallet_trades(address: str) -> tuple[list[dict], bool]:
    """Progressive pagination: 500 first, then up to 10K if promising."""
    all_trades: list[dict] = []
    offset = 0

    # Phase 1: quick scan (5 pages)
    for _ in range(5):
        page = _fetch_page(address, 100, offset)
        if not page:
            break
        all_trades.extend(page)
        if len(page) < 100:
            break
        offset += 100
        time.sleep(REQUEST_DELAY)

    if len(all_trades) < 100:
        return all_trades, False
    if len({t.get("conditionId") for t in all_trades}) < 15:
        return all_trades, False

    # Phase 2: full fetch
    max_pages = MAX_TRADES // 100
    pages_done = 5
    while pages_done < max_pages:
        page = _fetch_page(address, 100, offset)
        if not page:
            break
        all_trades.extend(page)
        if len(page) < 100:
            break
        offset += 100
        pages_done += 1
        time.sleep(REQUEST_DELAY)

    return all_trades, len(all_trades) >= MAX_TRADES


# ---------------------------------------------------------------------------
# Metrics + categorization
# ---------------------------------------------------------------------------


def categorize_market(title: str) -> str:
    kw_map = [
        ("politics", ["president", "election", "trump", "biden", "congress",
                       "senate", "governor", "democrat", "republican", "gop",
                       "vote", "political", "party", "primary"]),
        ("geopolitics", ["war", "ceasefire", "peace", "invasion", "nato",
                         "sanction", "iran", "russia", "ukraine", "china",
                         "taiwan", "israel", "hezbollah", "gaza"]),
        ("sports", ["win the", "nba", "nfl", "mlb", "nhl", "fifa",
                     "world cup", "super bowl", "championship", "playoffs",
                     "tennis", "open", "grand slam", "ufc", "boxing"]),
        ("crypto", ["bitcoin", "btc", "ethereum", "eth", "crypto", "token",
                     "defi", "solana", "dogecoin", "xrp", "nft"]),
        ("culture", ["oscar", "grammy", "emmy", "movie", "album",
                      "kardashian", "celebrity", "tiktok", "twitter",
                      "youtube", "pope", "royal"]),
    ]
    for cat, keywords in kw_map:
        for kw in keywords:
            if kw in title:
                return cat
    return "other"


def aggregate_metrics(trades: list[dict], was_capped: bool) -> dict | None:
    if not trades:
        return None

    markets = set()
    cat_counts: dict[str, int] = defaultdict(int)
    buy_count = 0
    timestamps = []
    token_sides: dict[str, dict[str, int]] = defaultdict(lambda: {"BUY": 0, "SELL": 0})
    cost_per_market: dict[str, float] = defaultdict(float)

    for t in trades:
        cid = t.get("conditionId", "")
        markets.add(cid)
        cat = categorize_market((t.get("title") or "").lower())
        cat_counts[cat] += 1
        side = t.get("side", "")
        size = float(t.get("size") or 0)
        price = float(t.get("price") or 0)
        if side == "BUY":
            buy_count += 1
            cost_per_market[cid] += size * price
        token_id = t.get("asset", "")
        if token_id and side:
            token_sides[token_id][side] += 1
        ts = t.get("timestamp")
        if ts:
            timestamps.append(int(ts))

    n = len(trades)
    categories = set(cat_counts.keys())
    total_cat = sum(cat_counts.values())
    hhi = sum((c / total_cat) ** 2 for c in cat_counts.values()) if total_cat else 1.0

    # Market maker detection
    mm_score = 0
    mm_checked = 0
    for _tok, sides in token_sides.items():
        tot = sides["BUY"] + sides["SELL"]
        if tot >= 10:
            mm_checked += 1
            if min(sides["BUY"], sides["SELL"]) / max(sides["BUY"], sides["SELL"]) > 0.4:
                mm_score += 1
    is_mm = mm_checked > 0 and mm_score / mm_checked > 0.5

    # Temporal
    if timestamps:
        timestamps.sort()
        first_trade = datetime.fromtimestamp(timestamps[0], tz=UTC)
        last_trade = datetime.fromtimestamp(timestamps[-1], tz=UTC)
        days_active = max((last_trade - first_trade).days, 1)
        daily: dict[str, int] = defaultdict(int)
        for ts_val in timestamps:
            daily[datetime.fromtimestamp(ts_val, tz=UTC).strftime("%Y-%m-%d")] += 1
        tpd_med = median(daily.values()) if daily else 0
        unique_days = len(daily)
        if len(timestamps) > 1:
            ivs = [timestamps[j + 1] - timestamps[j] for j in range(len(timestamps) - 1)]
            m_iv = sum(ivs) / len(ivs)
            v_iv = sum((x - m_iv) ** 2 for x in ivs) / len(ivs)
            temp_consistency = 1.0 / (1.0 + (v_iv**0.5) / 86400)
        else:
            temp_consistency = 0.0
    else:
        first_trade = last_trade = None
        days_active = unique_days = 0
        tpd_med = 0
        temp_consistency = 0.0

    # Single-market dominance from trades (fallback for red flag #7)
    total_cost = sum(cost_per_market.values())
    top_market_cost_pct = (
        max(cost_per_market.values()) / total_cost if total_cost > 0 else 0
    )

    return {
        "trades_count": n,
        "trades_capped": was_capped,
        "k_markets": len(markets),
        "l_categories": len(categories),
        "hhi_cat": round(hhi, 4),
        "win_rate_approx": round(buy_count / n, 4) if n else 0,
        "first_trade": first_trade,
        "last_trade": last_trade,
        "days_active": days_active,
        "unique_active_days": unique_days,
        "trades_per_day_median": round(tpd_med, 1),
        "temporal_consistency": round(temp_consistency, 4),
        "is_market_maker": is_mm,
        "top_market_cost_pct": round(top_market_cost_pct, 4),
    }


# ---------------------------------------------------------------------------
# Red flags + auto-classification
# ---------------------------------------------------------------------------


def detect_red_flags(
    addr: str,
    metrics: dict,
    portfolio_value: float,
    top_position_conc: float | None,
) -> list[str]:
    flags = []
    tc = metrics["trades_count"]

    # 1. burst_trader
    if tc >= 200 and metrics["unique_active_days"] < 5:
        flags.append("burst_trader")

    # 2. win_rate_too_high
    if tc >= 100 and metrics["win_rate_approx"] > 0.95:
        flags.append("win_rate_too_high")

    # 3. anti_pattern (win_rate too low)
    if metrics["win_rate_approx"] < 0.30:
        flags.append("anti_pattern")

    # 4. ultra_mono_category
    if metrics["hhi_cat"] > 0.70:
        flags.append("ultra_mono_category")

    # 5. inactive
    if metrics["last_trade"]:
        days_since = (datetime.now(UTC) - metrics["last_trade"]).days
        if days_since > 30:
            flags.append("inactive")

    # 6. known_proxy
    if addr in KNOWN_SYSTEM_CONTRACTS:
        flags.append("known_proxy")

    # 7. single_market_dominant
    conc = top_position_conc if top_position_conc is not None else metrics["top_market_cost_pct"]
    if conc > 0.60:
        flags.append("single_market_dominant")

    # 8. erratic_activity
    if metrics["temporal_consistency"] < 0.30:
        flags.append("erratic_activity")

    return flags


def auto_classify(metrics: dict, portfolio_value: float, red_flags: list[str]) -> str:
    """Classify as A1_candidate, A2_candidate, or reject."""
    if red_flags:
        return "reject"

    tc = metrics["trades_count"]
    da = metrics["days_active"]
    lc = metrics["l_categories"]
    tpd = metrics["trades_per_day_median"]

    # A1 thresholds
    if (
        portfolio_value >= 100_000
        and tc >= 500
        and da >= 180
        and lc >= 3
        and tpd <= 10
    ):
        return "A1_candidate"

    # A2 thresholds
    if (
        portfolio_value >= 30_000
        and tc >= 200
        and da >= 90
        and lc >= 2
        and tpd <= 15
    ):
        return "A2_candidate"

    return "reject"


def make_validation_note(tier: str, metrics: dict, pv: float, red_flags: list[str]) -> str:
    tc = metrics["trades_count"]
    lc = metrics["l_categories"]
    da = metrics["days_active"]
    if tier == "A1_candidate":
        return f"A1 strict : {tc} trades / {lc} cat / {da}j / portfolio ${pv:,.0f}"
    if tier == "A2_candidate":
        return f"A2 : {tc} trades / {lc} cat / {da}j / portfolio ${pv:,.0f}"
    if red_flags:
        return f"Reject : {red_flags[0]} ({tc} trades / {da}j)"
    return f"Reject : below thresholds ({tc} trades / {da}j / ${pv:,.0f})"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def winsorize(values: list[float], pct: float = 0.99) -> list[float]:
    if len(values) < 3:
        return list(values)
    sv = sorted(values)
    cap = sv[min(int(len(sv) * pct), len(sv) - 1)]
    return [min(v, cap) for v in values]


def z_scores(values: list[float]) -> list[float]:
    n = len(values)
    if n < 2:
        return [0.0] * n
    mean = sum(values) / n
    std = (sum((v - mean) ** 2 for v in values) / n) ** 0.5
    if std == 0:
        return [0.0] * n
    return [(v - mean) / std for v in values]


def score_candidates(candidates: list[dict]) -> list[dict]:
    """Composite score with winsorized outliers."""
    if not candidates:
        return []
    z_pv = z_scores(winsorize([c["portfolio_value_usd"] for c in candidates]))
    z_tc = z_scores(winsorize([float(c["trades_count"]) for c in candidates]))
    z_mk = z_scores([float(c["k_markets"]) for c in candidates])
    z_lc = z_scores([float(c["l_categories"]) for c in candidates])
    z_da = z_scores([float(c["days_active"]) for c in candidates])

    for i, c in enumerate(candidates):
        c["composite_score"] = round(
            0.40 * z_pv[i] + 0.20 * z_tc[i] + 0.15 * z_mk[i]
            + 0.10 * z_lc[i] + 0.15 * z_da[i],
            4,
        )
    return candidates


# ---------------------------------------------------------------------------
# Tier B watchlist
# ---------------------------------------------------------------------------

A2_CHECKS = [
    ("portfolio_value_usd", 30_000),
    ("trades_count", 200),
    ("days_active", 90),
    ("l_categories", 2),
]


def is_tier_b_watchlist(c: dict) -> bool:
    """Reject that passes at least 2 of 5 A2 criteria."""
    if c["auto_tier"] != "reject":
        return False
    passed = sum(1 for field, thresh in A2_CHECKS if c.get(field, 0) >= thresh)
    if c.get("trades_per_day_median", 99) <= 15:
        passed += 1
    return passed >= 2


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("=" * 60)
    print("Tier A Wallet Discovery v2")
    print(f"Started: {datetime.now(UTC).isoformat()}")
    print("=" * 60)

    exclude = load_exclusion_addresses()
    print(f"\nExclusion list: {len(exclude)} addresses")

    # Step 1
    print("\n--- Step 1: Top markets from Gamma ---")
    market_ids = fetch_top_market_ids(150)
    print(f"Fetched {len(market_ids)} markets")

    # Step 2
    print("\n--- Step 2: Discover wallets from holders ---")
    pool = discover_wallets_from_holders(market_ids)
    pool = {a: v for a, v in pool.items() if a not in exclude}
    print(f"After exclusion: {len(pool)} wallets")
    pool = {a: v for a, v in pool.items() if len(v["markets_seen"]) >= 5}
    print(f"After pre-filter (>=5 markets): {len(pool)} wallets")

    # Step 3: portfolio values
    n_pool = len(pool)
    print(f"\n--- Step 3: Portfolio values for {n_pool} wallets ---")
    valued: dict[str, dict] = {}
    for i, (addr, info) in enumerate(pool.items()):
        val = fetch_portfolio_value(addr)
        if val is not None and val >= 1000:
            valued[addr] = {**info, "portfolio_value_usd": val}
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{n_pool}, {len(valued)} with >=$1K")
        time.sleep(REQUEST_DELAY)
    print(f"  Done: {len(valued)} wallets with portfolio >=$1K")

    # Step 4: trades + metrics + classify
    n_val = len(valued)
    print(f"\n--- Step 4: Trades + classify for {n_val} wallets ---")

    all_candidates = []
    flog = defaultdict(int)

    for i, (addr, info) in enumerate(valued.items()):
        flog["total"] += 1
        alias = info.get("name", "") or addr[:12]
        pv = info["portfolio_value_usd"]
        print(f"  [{i+1}/{n_val}] {alias} (${pv:,.0f})...", end=" ", flush=True)

        trades, capped = fetch_wallet_trades(addr)
        if not trades:
            flog["no_trades"] += 1
            print("no trades")
            continue

        name = info.get("name", "") or trades[0].get("name", "")
        m = aggregate_metrics(trades, capped)
        if not m:
            print("no metrics")
            continue

        tc = m["trades_count"]
        cap_s = "+" if capped else ""

        # Basic quantitative filters
        reject_reason = None
        if tc < 100:
            reject_reason = "too_few_trades"
        elif m["k_markets"] < 20:
            reject_reason = "too_few_markets"
        elif m["l_categories"] < 2:
            reject_reason = "too_few_categories"
        elif m["hhi_cat"] >= 0.5:
            reject_reason = "hhi_too_high"
        elif m["is_market_maker"]:
            reject_reason = "market_maker"
        elif m["days_active"] < 30:
            reject_reason = "too_short_history"
        elif m["trades_per_day_median"] > 20:
            reject_reason = "hf_bot"

        if reject_reason:
            flog[reject_reason] += 1
            print(f"{tc}{cap_s} trades, SKIP ({reject_reason})")
            continue

        flog["passed_quant"] += 1

        # Red flags (fetch position concentration for flag #7)
        top_conc = fetch_top_position_concentration(addr)
        time.sleep(REQUEST_DELAY)
        flags = detect_red_flags(addr, m, pv, top_conc)

        tier = auto_classify(m, pv, flags)
        note = make_validation_note(tier, m, pv, flags)
        flog[f"classified_{tier}"] += 1

        print(
            f"{tc}{cap_s} trades, ${pv:,.0f}, {m['days_active']}d "
            f"-> {tier}" + (f" [{', '.join(flags)}]" if flags else "")
        )

        all_candidates.append({
            "address": addr,
            "alias_if_known": name,
            "auto_tier": tier,
            "red_flags_detected": " | ".join(flags) if flags else "",
            "validation_notes": note[:100],
            "portfolio_value_usd": pv,
            "polymarket_url": f"https://polymarket.com/profile/{addr}",
            **m,
        })

    # Score all candidates that passed quant filters
    all_candidates = score_candidates(all_candidates)

    # Sort: A1 first, then A2, then reject, each by score desc
    tier_order = {"A1_candidate": 0, "A2_candidate": 1, "reject": 2}
    all_candidates.sort(
        key=lambda c: (tier_order.get(c["auto_tier"], 9), -c.get("composite_score", 0))
    )

    # Write CSV
    output_path = "data/research_outputs/tier_a_candidates_20260422_v2.csv"
    fieldnames = [
        "address", "alias_if_known", "auto_tier", "red_flags_detected",
        "validation_notes", "portfolio_value_usd", "trades_count",
        "trades_capped", "k_markets", "l_categories", "hhi_cat",
        "win_rate_approx", "first_trade", "last_trade", "days_active",
        "trades_per_day_median", "temporal_consistency", "composite_score",
        "polymarket_url",
    ]
    with open(output_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for c in all_candidates:
            row = {**c}
            if row.get("first_trade"):
                row["first_trade"] = row["first_trade"].strftime("%Y-%m-%d")
            if row.get("last_trade"):
                row["last_trade"] = row["last_trade"].strftime("%Y-%m-%d")
            w.writerow(row)

    # Tier B watchlist
    watchlist = [c for c in all_candidates if is_tier_b_watchlist(c)]
    wl_path = "data/research_outputs/tier_b_watchlist_20260422.md"
    with open(wl_path, "w") as f:
        f.write("# Tier B Watchlist (20260422)\n\n")
        f.write("Wallets borderline rejected from Tier A. Re-evaluate in M7.\n\n")
        f.write("| Address | Alias | Portfolio | Trades | Days | Cat | Reject reason | Notes |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for c in watchlist:
            addr_short = c["address"][:14] + "..."
            alias = c["alias_if_known"] or "-"
            reason = c["red_flags_detected"] or c["validation_notes"][:40]
            f.write(
                f"| {addr_short} | {alias} | ${c['portfolio_value_usd']:,.0f} "
                f"| {c['trades_count']} | {c['days_active']} | {c['l_categories']} "
                f"| {reason} | {c['validation_notes'][:50]} |\n"
            )

    # Filter funnel
    print(f"\n{'='*60}")
    print("FILTER FUNNEL")
    print(f"{'='*60}")
    print(f"Total wallets scanned:       {flog['total']}")
    print(f"Passed quantitative filters: {flog['passed_quant']}")
    a1 = flog.get("classified_A1_candidate", 0)
    a2 = flog.get("classified_A2_candidate", 0)
    rej = flog.get("classified_reject", 0)
    print(f"  A1 candidates:             {a1}")
    print(f"  A2 candidates:             {a2}")
    print(f"  Rejected (red flags):      {rej}")
    print(f"Tier B watchlist:            {len(watchlist)}")
    print("\nRejection reasons (quant):")
    for k in sorted(flog):
        skip = {"total", "passed_quant", "no_trades"}
        is_reason = k not in skip and not k.startswith("classified")
        if is_reason and flog[k] > 0:
                print(f"  {k}: {flog[k]}")

    # Summary table
    hdr = (
        f"{'#':<3} {'Tier':<6} {'Alias':<22} {'Portfolio':>11} "
        f"{'Trades':>7} {'Days':>5} {'Cat':>4} {'Score':>6}"
    )
    print(f"\n{hdr}")
    print("-" * len(hdr))
    for i, c in enumerate(all_candidates[:25], 1):
        alias = (c["alias_if_known"] or c["address"][:12] + "...")[:22]
        cap = "*" if c.get("trades_capped") else ""
        flags = f" [{c['red_flags_detected']}]" if c["red_flags_detected"] else ""
        print(
            f"{i:<3} {c['auto_tier']:<6} {alias:<22} "
            f"${c['portfolio_value_usd']:>9,.0f} "
            f"{c['trades_count']:>6}{cap} {c['days_active']:>5} "
            f"{c['l_categories']:>4} {c.get('composite_score', 0):>6.3f}"
            f"{flags}"
        )

    print(f"\nCSV: {output_path}")
    print(f"Watchlist: {wl_path}")
    print(f"Done. {datetime.now(UTC).isoformat()}")


if __name__ == "__main__":
    main()
