"""Score Tier A wallets by crossing trades with market resolutions."""

import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import duckdb


def get_db_path() -> str:
    return os.environ.get("DUCKDB_PATH", "data/pm.duckdb")


def fetch_wallet_data(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Fetch all Tier A wallets with their trades and resolutions."""
    wallets = con.execute(
        "SELECT address, tier_a_confidence FROM tracked_wallets "
        "WHERE tier = 'A' AND active = TRUE"
    ).fetchall()

    results = []
    for address, confidence in wallets:
        trades = con.execute(
            """
            SELECT t.transaction_hash, t.condition_id, t.side,
                   t.outcome, t.size_usd, t.price, t.timestamp_ts,
                   t.wallet_name, t.market_title,
                   r.settled_outcome,
                   m.category
            FROM trades t
            LEFT JOIN resolutions r ON t.condition_id = r.condition_id
            LEFT JOIN markets m ON t.condition_id = m.condition_id
            WHERE t.proxy_wallet = ?
            ORDER BY t.timestamp_ts ASC
            """,
            [address],
        ).fetchall()

        columns = [
            "tx_hash", "condition_id", "side", "outcome", "size_usd",
            "price", "timestamp_ts", "wallet_name", "market_title",
            "settled_outcome", "category",
        ]
        trade_dicts = [dict(zip(columns, row, strict=False)) for row in trades]

        results.append({
            "address": address,
            "confidence": float(confidence) if confidence else 0.0,
            "tier_label": "A1" if confidence and float(confidence) >= 0.90 else "A2",
            "trades": trade_dicts,
        })

    return results


def compute_wallet_stats(wallet: dict) -> dict:
    """Compute all metrics for a single wallet."""
    trades = wallet["trades"]
    now = datetime.now(UTC)

    # Basic counts
    n_total = len(trades)
    if n_total == 0:
        return _empty_stats(wallet)

    # Get wallet name from first trade
    wallet_name = None
    for t in trades:
        if t["wallet_name"]:
            wallet_name = t["wallet_name"]
            break
    wallet_name = wallet_name or wallet["address"][:12]

    # Timestamps
    timestamps = [t["timestamp_ts"] for t in trades if t["timestamp_ts"]]
    first_trade = min(timestamps) if timestamps else now
    last_trade = max(timestamps) if timestamps else now
    if first_trade.tzinfo is None:
        first_trade = first_trade.replace(tzinfo=UTC)
    if last_trade.tzinfo is None:
        last_trade = last_trade.replace(tzinfo=UTC)
    days_active = max((last_trade - first_trade).days, 1)
    days_since_last = (now - last_trade).days

    # Filter BUY trades with resolutions (exclude SELL, exclude INVALID)
    resolved_buys = [
        t for t in trades
        if t["side"] == "BUY"
        and t["settled_outcome"] is not None
        and t["settled_outcome"] != "INVALID"
    ]

    # Win/Loss calculation
    wins, losses = 0, 0
    total_pnl = 0.0
    edges = []

    for t in resolved_buys:
        price = float(t["price"]) if t["price"] else 0.5
        size = float(t["size_usd"]) if t["size_usd"] else 0.0
        outcome = t["outcome"] or "Yes"
        resolved = t["settled_outcome"]

        # Determine if trade was correct
        correct = (
            (outcome == "Yes" and resolved == "YES")
            or (outcome == "No" and resolved == "NO")
        )

        if correct:
            wins += 1
            pnl = size * (1.0 / price - 1.0) if price > 0 else 0.0
            edge = 1.0 - price
        else:
            losses += 1
            pnl = -size
            edge = 0.0 - price

        total_pnl += pnl
        edges.append(edge)

    n_resolved = wins + losses
    win_rate = wins / n_resolved if n_resolved > 0 else 0.0
    avg_pnl = total_pnl / n_resolved if n_resolved > 0 else 0.0
    avg_edge = sum(edges) / len(edges) if edges else 0.0

    # Diversification
    unique_markets = set()
    categories = set()
    vol_by_category = defaultdict(float)

    for t in trades:
        if t["condition_id"]:
            unique_markets.add(t["condition_id"])
        cat = t["category"] or "Unknown"
        categories.add(cat)
        vol_by_category[cat] += float(t["size_usd"]) if t["size_usd"] else 0.0

    # HHI
    total_vol = sum(vol_by_category.values())
    hhi = (
        sum((v / total_vol) ** 2 for v in vol_by_category.values())
        if total_vol > 0 else 1.0
    )

    return {
        "address": wallet["address"],
        "wallet_name": wallet_name,
        "tier_label": wallet["tier_label"],
        "confidence": wallet["confidence"],
        "n_total": n_total,
        "n_resolved": n_resolved,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "avg_pnl": avg_pnl,
        "avg_edge": avg_edge,
        "n_markets": len(unique_markets),
        "n_categories": len(categories),
        "hhi": hhi,
        "days_active": days_active,
        "days_since_last": days_since_last,
        "trades_per_day": n_total / days_active,
        "first_trade": first_trade.isoformat(),
        "last_trade": last_trade.isoformat(),
        "verdict": _verdict(
            n_resolved, win_rate, avg_edge, days_since_last
        ),
    }


def _empty_stats(wallet: dict) -> dict:
    return {
        "address": wallet["address"],
        "wallet_name": wallet["address"][:12],
        "tier_label": wallet["tier_label"],
        "confidence": wallet["confidence"],
        "n_total": 0, "n_resolved": 0, "wins": 0, "losses": 0,
        "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
        "avg_edge": 0.0, "n_markets": 0, "n_categories": 0,
        "hhi": 1.0, "days_active": 0, "days_since_last": 999,
        "trades_per_day": 0.0,
        "first_trade": None, "last_trade": None,
        "verdict": "⚠️ WATCH — no trades",
    }


def _verdict(
    n_resolved: int, win_rate: float, avg_edge: float, days_since: int
) -> str:
    if n_resolved < 10:
        return "⚠️ WATCH — insufficient data"
    if win_rate >= 0.58 and avg_edge > 0.03:
        return "✅ KEEP — strong edge"
    if win_rate >= 0.55 and avg_edge > 0.02:
        return "✅ KEEP — positive edge"
    if win_rate < 0.45 or avg_edge < -0.02:
        return "❌ DEMOTE — negative performance"
    if days_since > 30:
        return "⚠️ WATCH — inactive > 30d"
    return "⚠️ WATCH — marginal performance"


def print_scorecard(all_stats: list[dict]) -> None:
    """Print formatted scorecard to terminal."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    sep = "═" * 78
    thin = "─" * 50

    print(f"\n╔{sep}╗")
    print(f"║  TIER A WALLET SCORECARD — {today:^50} ║")
    print(f"╠{sep}╣\n")

    for s in all_stats:
        addr_short = s["address"][:6] + "..." + s["address"][-4:]
        print(f" {s['wallet_name']} ({addr_short})"
              f" — Tier {s['tier_label']} (conf {s['confidence']:.2f})")
        print(f" {thin}")

        if s["n_total"] == 0:
            print(" No trades\n")
            print(f" Verdict: {s['verdict']}\n")
            continue

        # Trades + resolution rate
        res_pct = (
            f"{s['n_resolved'] / s['n_total'] * 100:.0f}%"
            if s["n_total"] > 0 else "0%"
        )
        print(f" Trades: {s['n_total']} total, {s['n_resolved']} resolved ({res_pct})")

        # Win rate
        wr_icon = "✅" if s["win_rate"] >= 0.55 else ("❌" if s["win_rate"] < 0.45 else "⚠️")
        if s["n_resolved"] > 0:
            print(f" Win Rate: {s['win_rate']:.0%}"
                  f" ({s['wins']}W / {s['losses']}L) {wr_icon}")
        else:
            print(" Win Rate: N/A (0 resolved)")

        # P&L
        pnl_sign = "+" if s["total_pnl"] >= 0 else "-"
        avg_sign = "+" if s["avg_pnl"] >= 0 else "-"
        print(f" P&L: {pnl_sign}${abs(s['total_pnl']):,.2f}"
              f" (avg {avg_sign}${abs(s['avg_pnl']):,.2f}/trade)")

        # Edge
        edge_cents = s["avg_edge"] * 100
        edge_icon = "✅" if edge_cents > 3 else ("❌" if edge_cents < -2 else "⚠️")
        print(f" Edge: {edge_cents:+.1f} cents/trade {edge_icon}")

        # Markets
        div_icon = "✅" if s["n_markets"] >= 20 and s["n_categories"] >= 3 else "⚠️"
        print(f" Markets: {s['n_markets']} unique,"
              f" {s['n_categories']} categories {div_icon}")

        # HHI
        hhi_icon = "✅" if s["hhi"] < 0.2 else ("⚠️" if s["hhi"] < 0.5 else "❌")
        print(f" HHI: {s['hhi']:.2f} {hhi_icon}")

        # Activity
        act_warn = " ⚠️" if s["days_since_last"] > 30 else ""
        print(f" Active: {s['days_active']}d,"
              f" last trade {s['days_since_last']}d ago{act_warn}")

        # Verdict
        print(f" Verdict: {s['verdict']}\n")

    # Summary
    keep = sum(1 for s in all_stats if "KEEP" in s["verdict"])
    watch = sum(1 for s in all_stats if "WATCH" in s["verdict"])
    demote = sum(1 for s in all_stats if "DEMOTE" in s["verdict"])
    no_data = sum(1 for s in all_stats if s["n_resolved"] == 0)
    total_pnl = sum(s["total_pnl"] for s in all_stats)
    pnl_sign = "+" if total_pnl >= 0 else ""

    print(f"╠{sep}╣")
    print(f"║ SUMMARY{' ' * 70}║")
    print(f"║ Total wallets: {len(all_stats):<62}║")
    verdict_line = f"KEEP: {keep} | WATCH: {watch} | DEMOTE: {demote}"
    pnl_line = f"Total resolved P&L: {pnl_sign}${abs(total_pnl):,.2f}"
    print(f"║ {verdict_line:<76}║")
    print(f"║ Wallets with 0 resolved trades: {no_data:<45}║")
    print(f"║ {pnl_line:<76}║")
    print(f"╚{sep}╝\n")


def save_report(all_stats: list[dict]) -> str:
    """Save scorecard to JSON file."""
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    today = datetime.now(UTC).strftime("%Y%m%d")
    path = reports_dir / f"tier_a_scorecard_{today}.json"
    with open(path, "w") as f:
        json.dump(all_stats, f, indent=2, default=str)
    return str(path)


def main():
    db_path = get_db_path()
    con = duckdb.connect(db_path, read_only=True)

    print("Loading Tier A wallet data...")
    wallets = fetch_wallet_data(con)
    con.close()

    if not wallets:
        print("No Tier A wallets found.")
        sys.exit(1)

    print(f"Scoring {len(wallets)} wallets...")
    all_stats = []
    for w in wallets:
        stats = compute_wallet_stats(w)
        all_stats.append(stats)

    # Sort: KEEP first, then WATCH, then DEMOTE
    order = {"✅": 0, "⚠️": 1, "❌": 2}
    all_stats.sort(key=lambda s: (
        order.get(s["verdict"][:2], 9),
        -s["total_pnl"],
    ))

    print_scorecard(all_stats)

    path = save_report(all_stats)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    main()
