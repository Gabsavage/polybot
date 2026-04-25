"""Scan trades_all for new sharp wallet candidates (volume/activity scoring)."""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb

# Exchange contracts to exclude
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"

# Minimum filters
MIN_TRADES = 20
MIN_MARKETS = 5
MIN_VOLUME = 1000  # $1K


def get_db_path() -> str:
    return os.environ.get("DUCKDB_PATH", "data/pm.duckdb")


def fetch_candidates(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Extract wallets from trades_all that pass minimum filters."""
    rows = con.execute(
        """
        SELECT
            ta.proxy_wallet,
            COUNT(*) as n_trades,
            COUNT(DISTINCT ta.condition_id) as n_markets,
            SUM(ta.size_usd) as total_volume,
            AVG(ta.size_usd) as avg_trade_size,
            MIN(ta.timestamp_ts) as first_trade,
            MAX(ta.timestamp_ts) as last_trade,
            COUNT(DISTINCT DATE_TRUNC('day', ta.timestamp_ts)) as active_days
        FROM trades_all ta
        WHERE ta.proxy_wallet IS NOT NULL
          AND ta.proxy_wallet NOT IN (SELECT address FROM tracked_wallets)
          AND ta.proxy_wallet NOT IN (?, ?)
        GROUP BY ta.proxy_wallet
        HAVING COUNT(*) >= ?
           AND COUNT(DISTINCT ta.condition_id) >= ?
           AND SUM(ta.size_usd) >= ?
        ORDER BY SUM(ta.size_usd) DESC
        """,
        [CTF_EXCHANGE, NEG_RISK_EXCHANGE, MIN_TRADES, MIN_MARKETS, MIN_VOLUME],
    ).fetchall()

    columns = [
        "proxy_wallet", "n_trades", "n_markets", "total_volume",
        "avg_trade_size", "first_trade", "last_trade", "active_days",
    ]
    return [dict(zip(columns, row, strict=False)) for row in rows]


def compute_hhi(con: duckdb.DuckDBPyConnection, wallet: str) -> float:
    """Compute Herfindahl-Hirschman Index by condition_id for a wallet."""
    rows = con.execute(
        """
        SELECT condition_id, SUM(size_usd) as vol
        FROM trades_all
        WHERE proxy_wallet = ?
        GROUP BY condition_id
        """,
        [wallet],
    ).fetchall()

    total = sum(r[1] for r in rows if r[1])
    if total <= 0:
        return 1.0
    return sum((r[1] / total) ** 2 for r in rows if r[1])


def score_wallet(candidate: dict, hhi: float) -> int:
    """Score a wallet on volume/diversification/activity (max 9)."""
    score = 0
    vol = float(candidate["total_volume"] or 0)
    markets = int(candidate["n_markets"] or 0)
    active_days = int(candidate["active_days"] or 0)
    avg_size = float(candidate["avg_trade_size"] or 0)

    # Volume: ≥$50K → +3, ≥$10K → +2, ≥$3K → +1
    if vol >= 50_000:
        score += 3
    elif vol >= 10_000:
        score += 2
    elif vol >= 3_000:
        score += 1

    # Diversification: ≥20 markets → +2, ≥10 → +1
    if markets >= 20:
        score += 2
    elif markets >= 10:
        score += 1

    # Activity: ≥3 distinct days → +1
    if active_days >= 3:
        score += 1

    # Avg trade size: ≥$100 → +1
    if avg_size >= 100:
        score += 1

    # Concentration: HHI < 0.25 → +1
    if hhi < 0.25:
        score += 1

    return score


def print_distribution(candidates: list[dict]) -> None:
    """Print distribution stats for threshold tuning."""
    if not candidates:
        return

    volumes = sorted(float(c["total_volume"] or 0) for c in candidates)
    trades = sorted(int(c["n_trades"] or 0) for c in candidates)
    markets = sorted(int(c["n_markets"] or 0) for c in candidates)

    def percentiles(vals: list) -> str:
        n = len(vals)
        if n == 0:
            return "no data"
        p25 = vals[n // 4] if n >= 4 else vals[0]
        p50 = vals[n // 2]
        p75 = vals[3 * n // 4] if n >= 4 else vals[-1]
        return f"p25={p25:,.0f}  p50={p50:,.0f}  p75={p75:,.0f}  max={vals[-1]:,.0f}"

    print("\n--- Distribution (for threshold tuning) ---")
    print(f"  Volume ($):  {percentiles(volumes)}")
    print(f"  Trades:      {percentiles(trades)}")
    print(f"  Markets:     {percentiles(markets)}")
    print("---\n")


def print_results(scored: list[dict], total_wallets: int, n_passed: int) -> None:
    """Print formatted results to terminal."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    sep = "═" * 66
    thin = "─" * 50

    print(f"\n╔{sep}╗")
    print(f"║  NEW SHARP CANDIDATES — {today:^41} ║")
    print(f"╠{sep}╣\n")

    top = scored[:20]
    for i, s in enumerate(top, 1):
        addr = s["proxy_wallet"]
        addr_short = addr[:6] + "..." + addr[-4:]
        vol = float(s["total_volume"] or 0)
        avg = float(s["avg_trade_size"] or 0)
        hhi = s["hhi"]
        active_days = int(s["active_days"] or 0)

        # Recommendation
        score = s["score"]
        if score >= 7:
            rec = "STRONG CANDIDATE for Tier B"
        elif score >= 5:
            rec = "CANDIDATE for Tier B (needs Data API check)"
        elif score >= 3:
            rec = "MARGINAL — review manually"
        else:
            rec = "LOW SIGNAL"

        print(f" #{i:<3} {addr_short}")
        print(f"     Score: {score}/9 | Trades: {s['n_trades']}")
        print(f"     Volume: ${vol:,.0f} | Avg size: ${avg:,.0f}/trade")
        print(f"     Markets: {s['n_markets']} | HHI: {hhi:.2f}")
        print(f"     Active days: {active_days}")

        if s["first_trade"] and s["last_trade"]:
            ft = s["first_trade"]
            lt = s["last_trade"]
            ft_str = ft.strftime("%Y-%m-%d %H:%M") if hasattr(ft, "strftime") else str(ft)[:16]
            lt_str = lt.strftime("%Y-%m-%d %H:%M") if hasattr(lt, "strftime") else str(lt)[:16]
            print(f"     Period: {ft_str} → {lt_str}")

        print(f"     → {rec}")
        print(f"     {thin}")

    # Summary
    strong = sum(1 for s in scored if s["score"] >= 7)
    medium = sum(1 for s in scored if 5 <= s["score"] < 7)

    print(f"\n╠{sep}╣")
    print(f"║ SUMMARY{' ' * 58}║")
    print(f"║ Unique wallets in trades_all: {total_wallets:<36}║")
    print(f"║ Passed minimum filters: {n_passed:<41}║")
    print(f"║ Score >= 7 (strong): {strong:<44}║")
    print(f"║ Score >= 5 (candidate): {medium:<41}║")
    print(f"╚{sep}╝\n")

    if n_passed < 5:
        print(
            "⚠️  Dataset trades_all trop petit pour un scan significatif."
            " Relancer dans 1-2 semaines.\n"
        )


def save_report(scored: list[dict]) -> str:
    """Save all candidates to JSON."""
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    today = datetime.now(UTC).strftime("%Y%m%d")
    path = reports_dir / f"new_sharps_{today}.json"

    # Serialize datetimes
    output = []
    for s in scored:
        entry = dict(s)
        for key in ("first_trade", "last_trade"):
            if entry[key] and hasattr(entry[key], "isoformat"):
                entry[key] = entry[key].isoformat()
        output.append(entry)

    with open(path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    return str(path)


def main():
    db_path = get_db_path()
    con = duckdb.connect(db_path, read_only=True)

    # Total unique wallets in trades_all
    total_wallets = con.execute(
        "SELECT COUNT(DISTINCT proxy_wallet) FROM trades_all"
    ).fetchone()[0]
    print(f"Total unique wallets in trades_all: {total_wallets}")

    # Fetch candidates
    print("Scanning for candidates...")
    candidates = fetch_candidates(con)
    print(
        f"Passed minimum filters"
        f" (≥{MIN_TRADES} trades, ≥{MIN_MARKETS} markets,"
        f" ≥${MIN_VOLUME} vol): {len(candidates)}"
    )

    if not candidates:
        print("\nNo candidates found. trades_all may not have enough data yet.")
        con.close()
        sys.exit(0)

    # Distribution log
    print_distribution(candidates)

    # Compute HHI and score each candidate
    print("Computing HHI and scoring...")
    scored = []
    for c in candidates:
        hhi = compute_hhi(con, c["proxy_wallet"])
        c["hhi"] = round(hhi, 4)
        c["score"] = score_wallet(c, hhi)
        scored.append(c)

    con.close()

    # Sort by score desc, then volume desc
    scored.sort(key=lambda s: (-s["score"], -float(s["total_volume"] or 0)))

    # Output
    print_results(scored, total_wallets, len(scored))

    path = save_report(scored)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    main()
