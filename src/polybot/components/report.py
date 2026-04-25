"""Daily report generation for Polybot."""

from datetime import UTC, datetime

from polybot.db.connection import connect as db_connect


def generate_report(db_path: str, days: int = 1, bot_start: datetime | None = None) -> str:
    """Generate a daily performance report. Returns formatted HTML string."""
    con = db_connect(db_path, read_only=True)
    try:
        return _build_report(con, days, bot_start)
    finally:
        con.close()


def _build_report(con, days: int, bot_start: datetime | None) -> str:
    interval = f"{days} DAY"
    date_label = (
        datetime.now(UTC).strftime("%Y-%m-%d")
        if days == 1
        else f"{days}j"
    )

    parts = [f"<b>📊 Daily Report — {date_label}</b>"]

    # --- Alerts C1 ---
    row = con.execute(
        f"""
        SELECT COUNT(*),
               AVG(size_usd),
               AVG(size_suggested_usd)
        FROM alerts
        WHERE component = 'C1'
          AND emitted_at >= NOW() - INTERVAL {interval}
        """
    ).fetchone()
    total_alerts, avg_size, avg_suggested = row

    if total_alerts == 0:
        parts.append("\n🎯 <b>Alertes C1</b>\n  Aucune alerte émise")
    else:
        # Outcome breakdown — alerts store the predicted outcome
        # but we don't have a direct 'outcome' column, use side info
        parts.append(
            f"\n🎯 <b>Alertes C1</b>"
            f"\n  Total : <b>{total_alerts}</b>"
            f"\n  Size moyen sharp : ${avg_size:,.0f}"
            f"\n  Size suggéré moyen : ${avg_suggested:,.0f}"
        )

    # --- Wallets actifs ---
    trades_total = con.execute(
        f"SELECT COUNT(*) FROM trades WHERE timestamp_ts >= NOW() - INTERVAL {interval}"
    ).fetchone()[0]

    wallets_with_trades = con.execute(
        f"""
        SELECT COUNT(DISTINCT t.proxy_wallet)
        FROM trades t
        JOIN tracked_wallets tw ON t.proxy_wallet = tw.address
        WHERE tw.tier = 'A' AND tw.active = TRUE
          AND t.timestamp_ts >= NOW() - INTERVAL {interval}
        """
    ).fetchone()[0]

    total_tier_a = con.execute(
        "SELECT COUNT(*) FROM tracked_wallets WHERE tier = 'A' AND active = TRUE"
    ).fetchone()[0]

    silent = total_tier_a - wallets_with_trades

    parts.append(
        f"\n👛 <b>Wallets actifs</b>"
        f"\n  Trades détectés : {trades_total}"
        f"\n  Trades alertés : {total_alerts}"
        f"\n  Wallets silencieux : {silent}/{total_tier_a}"
    )

    # --- Marchés touchés ---
    if total_alerts > 0:
        markets_count = con.execute(
            f"""
            SELECT COUNT(DISTINCT condition_id) FROM alerts
            WHERE component = 'C1' AND emitted_at >= NOW() - INTERVAL {interval}
            """
        ).fetchone()[0]

        top_market = con.execute(
            f"""
            SELECT condition_id, MAX(size_usd) as max_size
            FROM alerts
            WHERE component = 'C1' AND emitted_at >= NOW() - INTERVAL {interval}
            GROUP BY condition_id
            ORDER BY max_size DESC LIMIT 1
            """
        ).fetchone()

        # Try to get market title
        top_title = "?"
        if top_market:
            title_row = con.execute(
                "SELECT title FROM markets WHERE condition_id = ?",
                [top_market[0]],
            ).fetchone()
            if title_row and title_row[0]:
                top_title = title_row[0][:50]

        parts.append(
            f"\n📈 <b>Marchés</b>"
            f"\n  Marchés uniques : {markets_count}"
            f"\n  Top : {top_title}"
        )

    # --- Performance shadow ---
    perf = con.execute(
        f"""
        SELECT
            a.alert_id, a.price, a.size_suggested_usd,
            r.settled_outcome,
            CASE
                WHEN r.settled_outcome IS NULL THEN 'pending'
                WHEN r.settled_outcome = 'INVALID' THEN 'invalid'
                WHEN r.settled_outcome = 'YES' THEN 'correct'
                ELSE 'incorrect'
            END as result
        FROM alerts a
        LEFT JOIN resolutions r ON a.condition_id = r.condition_id
        WHERE a.component = 'C1'
          AND a.emitted_at >= NOW() - INTERVAL {interval}
        """
    ).fetchall()

    resolved = [p for p in perf if p[4] != "pending"]
    correct = [p for p in resolved if p[4] == "correct"]

    if not resolved:
        parts.append(
            "\n⚖️ <b>Shadow</b>"
            "\n  Aucune alerte résolue"
        )
    else:
        pnl = 0.0
        for row in resolved:
            price, size_sugg, _, _, result = row[1], float(row[2]), row[3], row[4], row[4]
            price = float(price) if price else 0.5
            if result == "correct":
                pnl += float(size_sugg) * (1.0 / price - 1.0)
            elif result == "incorrect":
                pnl -= float(size_sugg)

        win_rate = len(correct) / len(resolved) * 100 if resolved else 0
        pnl_sign = "+" if pnl >= 0 else ""
        disclaimer = ""
        if len(resolved) < 30:
            disclaimer = "\n  <i>(échantillon &lt; 30, trop tôt)</i>"

        parts.append(
            f"\n⚖️ <b>Shadow</b>"
            f"\n  Résolues : {len(resolved)}/{len(perf)}"
            f"\n  Direction : {len(correct)}/{len(resolved)} ({win_rate:.0f}%)"
            f"\n  P&amp;L sim : {pnl_sign}${abs(pnl):,.2f}"
            f"{disclaimer}"
        )

    # --- Santé système ---
    last_trade_row = con.execute("SELECT MAX(ingested_at) FROM trades").fetchone()
    last_trade_ts = last_trade_row[0] if last_trade_row else None

    last_sync_row = con.execute(
        "SELECT last_synced_at FROM indexer_state WHERE indexer_name = 'markets_gamma'"
    ).fetchone()
    last_sync_ts = last_sync_row[0] if last_sync_row else None

    errors_24h = con.execute(
        "SELECT COUNT(*) FROM indexer_state WHERE last_run_status = 'failed'"
    ).fetchone()[0]

    now = datetime.now(UTC)

    def _ago(ts):
        if not ts:
            return "N/A"
        delta = now - ts.replace(tzinfo=UTC)
        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())}s"
        if delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() / 60)}min"
        return f"{delta.total_seconds() / 3600:.1f}h"

    uptime_str = "N/A"
    if bot_start:
        up = now - bot_start
        uptime_str = f"{up.days}j {up.seconds // 3600}h{(up.seconds % 3600) // 60:02d}m"

    parts.append(
        f"\n🔧 <b>Système</b>"
        f"\n  Uptime : {uptime_str}"
        f"\n  Dernier trade : {_ago(last_trade_ts)}"
        f"\n  Market sync : {_ago(last_sync_ts)}"
        f"\n  Indexer errors : {errors_24h}"
    )

    return "\n".join(parts)
