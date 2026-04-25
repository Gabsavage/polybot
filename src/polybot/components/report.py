"""Daily report generation for Polybot — C1 + C2 + alert_outcomes."""

import os
from datetime import UTC, datetime

from polybot.db.connection import connect as db_connect


def generate_report(
    db_path: str, days: int = 1, bot_start: datetime | None = None
) -> str:
    """Generate a daily performance report. Returns formatted HTML string."""
    con = db_connect(db_path, read_only=True)
    try:
        return _build_report(con, db_path, days, bot_start)
    finally:
        con.close()


def _build_report(con, db_path: str, days: int, bot_start: datetime | None) -> str:
    interval = f"{days} DAY"
    date_label = (
        datetime.now(UTC).strftime("%Y-%m-%d")
        if days == 1
        else f"{days}j"
    )

    parts = [f"<b>📊 Daily Report — {date_label}</b>"]

    # --- C1 Sharp Money ---
    parts.append(_section_c1(con, interval))

    # --- C2 Informed Trading ---
    parts.append(_section_c2(con, interval))

    # --- Wallets ---
    parts.append(_section_wallets(con, interval))

    # --- Performance shadow (30 days window) ---
    parts.append(_section_shadow(con))

    # --- Alignment C2 ---
    alignment = _section_alignment(con)
    if alignment:
        parts.append(alignment)

    # --- System ---
    parts.append(_section_system(con, db_path, bot_start))

    return "\n".join(parts)


def _section_c1(con, interval: str) -> str:
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
    total, avg_size, avg_suggested = row

    if total == 0:
        return "\n🎯 <b>C1 Sharp Money</b>\n  Aucune alerte C1"

    return (
        f"\n🎯 <b>C1 Sharp Money</b>"
        f"\n  Alertes : <b>{total}</b>"
        f"\n  Size moyen sharp : ${avg_size:,.0f}"
        f"\n  Size suggéré moyen : ${avg_suggested:,.0f}"
    )


def _section_c2(con, interval: str) -> str:
    row = con.execute(
        f"""
        SELECT COUNT(*), AVG(score)
        FROM alerts
        WHERE component = 'C2'
          AND emitted_at >= NOW() - INTERVAL {interval}
        """
    ).fetchone()
    total, avg_score = row

    if total == 0:
        return "\n🔴 <b>C2 Informed Trading</b>\n  Aucune alerte C2"

    avg_s = f"{avg_score:.0f}" if avg_score is not None else "?"
    return (
        f"\n🔴 <b>C2 Informed Trading</b>"
        f"\n  Alertes : <b>{total}</b>"
        f"\n  Score moyen : {avg_s}/7"
    )


def _section_wallets(con, interval: str) -> str:
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

    return (
        f"\n👛 <b>Wallets</b>"
        f"\n  Trades Tier A détectés : {trades_total}"
        f"\n  Wallets silencieux : {silent}/{total_tier_a}"
    )


def _section_shadow(con) -> str:
    row = con.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN a.component='C1' THEN 1 ELSE 0 END) as c1_cnt,
            SUM(CASE WHEN a.component='C2' THEN 1 ELSE 0 END) as c2_cnt
        FROM alerts a
        WHERE a.emitted_at >= NOW() - INTERVAL 30 DAY
        """
    ).fetchone()
    total, c1_cnt, c2_cnt = row

    if total == 0:
        return (
            "\n⚖️ <b>Performance shadow</b>"
            "\n  Aucune alerte (30j)"
        )

    # Get resolution stats from alert_outcomes
    perf = con.execute(
        """
        SELECT
            COUNT(ao.alert_id) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL
                  AND ao.resolution_outcome != 'PENDING'
            ) as resolved,
            COUNT(ao.alert_id) FILTER (
                WHERE ao.was_direction_correct = TRUE
            ) as correct,
            SUM(ao.shadow_pnl_simulated) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL
                  AND ao.resolution_outcome != 'PENDING'
            ) as total_pnl
        FROM alerts a
        LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
        WHERE a.emitted_at >= NOW() - INTERVAL 30 DAY
        """
    ).fetchone()
    resolved, correct, total_pnl = perf
    total_pnl = float(total_pnl) if total_pnl else 0.0

    lines = [
        "\n⚖️ <b>Performance shadow</b>",
        f"  Alertes (30j) : {total} (C1: {c1_cnt}, C2: {c2_cnt})",
    ]

    if resolved == 0:
        lines.append("  Aucune alerte résolue")
    else:
        win_rate = correct / resolved * 100
        pnl_sign = "+" if total_pnl >= 0 else ""
        lines.append(f"  Résolues : {resolved}")
        lines.append(f"  Direction : {correct}/{resolved} ({win_rate:.0f}%)")
        lines.append(f"  Shadow P&amp;L : {pnl_sign}${abs(total_pnl):,.2f}")

    if resolved < 30:
        lines.append("  <i>Échantillon &lt; 30 — trop tôt pour conclure</i>")

    return "\n".join(lines)


def _section_alignment(con) -> str | None:
    rows = con.execute(
        """
        SELECT alignment_score, COUNT(*) as cnt
        FROM alerts
        WHERE component = 'C2'
          AND alignment_score IS NOT NULL
          AND emitted_at >= NOW() - INTERVAL 30 DAY
        GROUP BY alignment_score
        ORDER BY alignment_score DESC
        """
    ).fetchall()

    if not rows:
        return None

    dist = {int(r[0]): int(r[1]) for r in rows}
    lines = ["\n🧭 <b>Alignment C2</b> (30j)"]
    if 1 in dist:
        lines.append(f"  +1 (suit mouvement) : {dist[1]}")
    if -1 in dist:
        lines.append(f"  -1 (contrariant) : {dist[-1]}")
    if 0 in dist:
        lines.append(f"  0 (neutre) : {dist[0]}")

    return "\n".join(lines)


def _section_system(con, db_path: str, bot_start: datetime | None) -> str:
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
        secs = delta.total_seconds()
        if secs < 60:
            return f"{int(secs)}s"
        if secs < 3600:
            return f"{int(secs / 60)}min"
        return f"{secs / 3600:.1f}h"

    uptime_str = "N/A"
    if bot_start:
        up = now - bot_start
        uptime_str = f"{up.days}j {up.seconds // 3600}h{(up.seconds % 3600) // 60:02d}m"

    # DB file size
    db_size_str = "N/A"
    try:
        size_bytes = os.path.getsize(db_path)
        db_size_str = f"{size_bytes / (1024 * 1024):.0f} MB"
    except OSError:
        pass

    return (
        f"\n🔧 <b>Système</b>"
        f"\n  Uptime : {uptime_str}"
        f"\n  Dernier trade : {_ago(last_trade_ts)}"
        f"\n  Market sync : {_ago(last_sync_ts)}"
        f"\n  Indexer errors : {errors_24h}"
        f"\n  DB : {db_size_str}"
    )
