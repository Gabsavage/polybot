"""Lookup top candidates via Data API (paginated) + resolutions DB."""

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import httpx

DATA_API_URL = "https://data-api.polymarket.com/trades"
REQUEST_TIMEOUT = 15.0
MAX_TRADES = 3000  # Fetch up to 3000 trades per wallet

CANDIDATES = [
    "0x53757615de1c42b83f893b79d4241a009dc2aeea",
    "0x2005d16a84ceefa912d4e380cd32e7ff827875ea",
    "0xfe787d2da716d60e8acff57fb87eb13cd4d10319",
    "0xd106952ebf30a3125affd8a23b6c1f30c35fc79c",
    "0x204f72f35326db932158cba6adff0b9a1da95e14",
]


def fetch_all_trades(client, address):
    """Fetch up to MAX_TRADES trades with pagination."""
    all_trades = []
    for offset in range(0, MAX_TRADES, 1000):
        for attempt in range(3):
            try:
                r = client.get(
                    DATA_API_URL,
                    params={"user": address, "limit": 1000, "offset": offset},
                )
                if r.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                batch = r.json()
                break
            except Exception as e:
                print(f"  Retry {attempt}: {e}")
                time.sleep(1)
                batch = []
        else:
            break

        if not isinstance(batch, list) or not batch:
            break
        all_trades.extend(batch)
        if len(batch) < 1000:
            break
        time.sleep(0.3)

    return all_trades


def score_candidate(trades, resolutions):
    """Score using Data API trades + DB resolutions."""
    buy_trades = [t for t in trades if t.get("side") == "BUY"]

    wins, losses = 0, 0
    total_pnl = 0.0
    edges = []
    resolved_markets = set()
    all_markets = set()

    for t in buy_trades:
        cid = t.get("conditionId", "")
        all_markets.add(cid)
        price = float(t.get("price", 0.5))
        size = float(t.get("size", 0))

        settled = resolutions.get(cid)
        if not settled:
            continue

        resolved_markets.add(cid)

        # Each condition_id maps to one outcome token.
        # If settled == "YES", the token paid out $1 → buyer wins.
        # If settled == "NO", the token paid out $0 → buyer loses.
        correct = settled == "YES"

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
    avg_edge = sum(edges) / len(edges) if edges else 0.0
    total_volume = sum(float(t.get("size", 0)) for t in trades)

    return {
        "n_trades": len(trades),
        "n_buys": len(buy_trades),
        "n_resolved": n_resolved,
        "n_unresolved": len(buy_trades) - n_resolved,
        "n_resolved_markets": len(resolved_markets),
        "n_total_markets": len(all_markets),
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "avg_edge": avg_edge,
        "total_volume": total_volume,
        "name": "",
    }


def verdict(stats):
    nr = stats["n_resolved"]
    if nr < 5:
        return "INSUFFICIENT DATA" if nr > 0 else "NO RESOLVED TRADES"
    wr = stats["win_rate"]
    edge = stats["avg_edge"]
    if wr >= 0.58 and edge > 0.03:
        return "STRONG ADD to Tier B"
    if wr >= 0.55 and edge > 0.02:
        return "ADD to Tier B"
    if wr < 0.45 or edge < -0.02:
        return "SKIP — negative edge"
    return "MAYBE — marginal"


def main():
    con = duckdb.connect("data/pm.duckdb", read_only=True)
    rows = con.execute(
        "SELECT condition_id, settled_outcome FROM resolutions "
        "WHERE settled_outcome IS NOT NULL AND settled_outcome != 'INVALID'"
    ).fetchall()
    resolutions = {r[0]: r[1] for r in rows}
    con.close()
    print(f"Loaded {len(resolutions)} resolutions\n")

    sep = "=" * 62
    results = []

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        for i, addr in enumerate(CANDIDATES, 1):
            short = addr[:6] + "..." + addr[-4:]
            print(f"[{i}/{len(CANDIDATES)}] Fetching {short}...")

            trades = fetch_all_trades(client, addr)
            if not trades:
                print("  No trades\n")
                continue

            # Get name
            name = trades[0].get("name") or trades[0].get("pseudonym") or short

            # Time range
            ts = [int(t["timestamp"]) for t in trades]
            oldest = datetime.fromtimestamp(min(ts), tz=UTC)
            newest = datetime.fromtimestamp(max(ts), tz=UTC)

            stats = score_candidate(trades, resolutions)
            stats["address"] = addr
            stats["name"] = name
            results.append(stats)

            print(f"\n  {name} ({short})")
            print(f"  {sep}")
            print(f"  Trades fetched: {stats['n_trades']} ({stats['n_buys']} buys)")
            print(f"  Period: {oldest.strftime('%Y-%m-%d %H:%M')} -> "
                  f"{newest.strftime('%Y-%m-%d %H:%M')}")
            print(f"  Markets: {stats['n_total_markets']} total, "
                  f"{stats['n_resolved_markets']} resolved")
            print(f"  Resolved trades: {stats['n_resolved']} "
                  f"({stats['n_unresolved']} pending)")

            if stats["n_resolved"] > 0:
                wr = stats["win_rate"]
                print(f"  Win Rate: {wr:.0%} "
                      f"({stats['wins']}W / {stats['losses']}L)")
                pnl = stats["total_pnl"]
                sign = "+" if pnl >= 0 else ""
                print(f"  P&L: {sign}${pnl:,.2f}")
                edge_c = stats["avg_edge"] * 100
                print(f"  Avg Edge: {edge_c:+.1f}c/trade")

            print(f"  Volume: ${stats['total_volume']:,.0f}")
            v = verdict(stats)
            print(f"  >>> {v}\n")

            time.sleep(0.5)

    # Save
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    today = datetime.now(UTC).strftime("%Y%m%d")
    path = reports_dir / f"candidate_lookup_{today}.json"
    for r in results:
        r.pop("name_raw", None)
    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Results saved to {path}")


if __name__ == "__main__":
    main()
