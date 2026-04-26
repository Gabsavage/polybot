"""Weekly report generation for Polybot — full 8-section performance summary."""

from datetime import UTC, datetime

from polybot.db.connection import connect as db_connect

FRENCH_MONTHS = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def generate_weekly_report(db_path: str, weeks: int = 1) -> str:
    """Generate a weekly performance report. Returns formatted HTML string."""
    con = db_connect(db_path, read_only=True)
    try:
        return _build_report(con, weeks)
    finally:
        con.close()


def _build_report(con, weeks: int) -> str:
    interval = f"{7 * weeks} DAY"

    now = datetime.now(UTC)
    year, week_num, _ = now.isocalendar()
    month_name = FRENCH_MONTHS[now.month]

    # Check if any alerts exist in window
    total_alerts = con.execute(
        f"SELECT COUNT(*) FROM alerts WHERE emitted_at >= CURRENT_DATE - INTERVAL {interval}"
    ).fetchone()[0]

    if total_alerts == 0:
        return f"📊 <b>Weekly Report — Sem {week_num}</b>\n\nAucune alerte cette semaine."

    parts = [f"📊 <b>Weekly Report — Sem {week_num} ({month_name} {year})</b>"]
    parts.append(_section_alerts(con, interval))
    parts.append(_section_shadow(con, interval, weeks))
    parts.append(_section_cumulative(con))
    parts.append(_section_wallets(con, interval, weeks))
    alignment = _section_alignment(con, interval)
    if alignment:
        parts.append(alignment)
    parts.append(_section_orchestrator(con, interval))
    parts.append(_section_costs(con, interval))

    return "\n".join(parts)


def _section_alerts(con, interval: str) -> str:
    rows = con.execute(
        f"""
        SELECT component, COUNT(*), AVG(score)
        FROM alerts
        WHERE emitted_at >= CURRENT_DATE - INTERVAL {interval}
        GROUP BY component
        """
    ).fetchall()

    comp = {r[0]: (r[1], r[2]) for r in rows}
    c1_cnt = comp.get("C1", (0, None))[0]
    c2_cnt, c2_avg = comp.get("C2", (0, None))
    total = c1_cnt + c2_cnt

    lines = ["\n🎯 <b>Alertes émises</b>"]

    if c1_cnt:
        sides = con.execute(
            f"""
            SELECT side, COUNT(*) FROM alerts
            WHERE component = 'C1'
              AND emitted_at >= CURRENT_DATE - INTERVAL {interval}
            GROUP BY side
            """
        ).fetchall()
        side_str = ", ".join(f"{cnt} {s}" for s, cnt in sides) if sides else ""
        lines.append(f"  C1 : {c1_cnt} alertes ({side_str})")

    if c2_cnt:
        avg_str = f" (score moyen {c2_avg:.1f}/7)" if c2_avg else ""
        lines.append(f"  C2 : {c2_cnt} alertes{avg_str}")

    lines.append(f"  Total : {total}")
    return "\n".join(lines)


def _section_shadow(con, interval: str, weeks: int) -> str:
    row = con.execute(
        f"""
        SELECT
            COUNT(*) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL
                  AND ao.resolution_outcome != 'PENDING'
            ) as resolved,
            COUNT(*) FILTER (
                WHERE ao.was_direction_correct = TRUE
            ) as correct,
            SUM(ao.shadow_pnl_simulated) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL
                  AND ao.resolution_outcome != 'PENDING'
            ) as pnl
        FROM alerts a
        JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
        WHERE a.emitted_at >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()
    resolved, correct, pnl = row
    pnl = float(pnl) if pnl else 0.0

    lines = [f"\n⚖️ <b>Performance shadow ({weeks * 7} jours)</b>"]
    if resolved == 0:
        lines.append("  Aucune alerte résolue")
    else:
        pct = correct / resolved * 100
        sign = "+" if pnl >= 0 else ""
        lines.append(f"  Résolues : {resolved}")
        lines.append(f"  Direction correcte : {correct}/{resolved} ({pct:.0f}%)")
        lines.append(f"  Shadow P&amp;L : {sign}${abs(pnl):,.2f}")

    return "\n".join(lines)


def _section_cumulative(con) -> str:
    total = con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    row = con.execute(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL
                  AND ao.resolution_outcome != 'PENDING'
            ) as resolved,
            COUNT(*) FILTER (
                WHERE ao.was_direction_correct = TRUE
            ) as correct,
            SUM(ao.shadow_pnl_simulated) FILTER (
                WHERE ao.resolution_outcome IS NOT NULL
                  AND ao.resolution_outcome != 'PENDING'
            ) as pnl
        FROM alerts a
        LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
        """
    ).fetchone()
    resolved, correct, pnl = row
    pnl = float(pnl) if pnl else 0.0

    lines = ["\n📈 <b>Performance cumulée</b>"]
    lines.append(f"  Total alertes : {total}")
    if resolved == 0:
        lines.append("  Aucune résolue")
    else:
        pct = correct / resolved * 100
        sign = "+" if pnl >= 0 else ""
        lines.append(f"  Résolues : {resolved}")
        lines.append(f"  Direction correcte : {correct}/{resolved} ({pct:.0f}%)")
        lines.append(f"  Shadow P&amp;L cumulé : {sign}${abs(pnl):,.2f}")

    if resolved < 30:
        lines.append("  <i>⚠️ Échantillon &lt; 30 — trop tôt pour conclure</i>")

    return "\n".join(lines)


def _section_wallets(con, interval: str, weeks: int) -> str:
    total_a = con.execute(
        "SELECT COUNT(*) FROM tracked_wallets WHERE tier = 'A' AND active = TRUE"
    ).fetchone()[0]

    active_wallets = con.execute(
        f"""
        SELECT COUNT(DISTINCT t.proxy_wallet)
        FROM trades t
        JOIN tracked_wallets tw ON t.proxy_wallet = tw.address
        WHERE tw.tier = 'A' AND tw.active = TRUE
          AND t.timestamp_ts >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()[0]

    silent_rows = con.execute(
        f"""
        SELECT tw.address, tw.notes
        FROM tracked_wallets tw
        WHERE tw.tier = 'A' AND tw.active = TRUE
        AND NOT EXISTS (
            SELECT 1 FROM trades t
            WHERE t.proxy_wallet = tw.address
            AND t.timestamp_ts >= CURRENT_DATE - INTERVAL {interval}
        )
        """
    ).fetchall()

    trades_total = con.execute(
        f"SELECT COUNT(*) FROM trades WHERE timestamp_ts >= CURRENT_DATE - INTERVAL {interval}"
    ).fetchone()[0]

    silent_names = [r[1] or r[0][:10] for r in silent_rows]
    silent_str = ", ".join(silent_names[:5]) if silent_names else "aucun"

    lines = ["\n👛 <b>Wallets Tier A</b>"]
    lines.append(f"  Actifs : {active_wallets}/{total_a}")
    lines.append(f"  Silencieux &gt; {weeks}sem : {len(silent_rows)} ({silent_str})")
    lines.append(f"  Trades : {trades_total}")

    return "\n".join(lines)


def _section_alignment(con, interval: str) -> str | None:
    rows = con.execute(
        f"""
        SELECT alignment_score, COUNT(*)
        FROM alerts
        WHERE component = 'C2'
          AND alignment_score IS NOT NULL
          AND emitted_at >= CURRENT_DATE - INTERVAL {interval}
        GROUP BY alignment_score
        ORDER BY alignment_score DESC
        """
    ).fetchall()

    if not rows:
        return None

    dist = {int(r[0]): int(r[1]) for r in rows}
    lines = ["\n🧭 <b>Alignment C2</b>"]
    lines.append(f"  📈 Suit mouvement : {dist.get(1, 0)}")
    lines.append(f"  📉 Contrariant : {dist.get(-1, 0)}")
    lines.append(f"  ➡️ Neutre : {dist.get(0, 0)}")

    return "\n".join(lines)


def _section_orchestrator(con, interval: str) -> str:
    ks = con.execute(
        f"""
        SELECT COUNT(*) FROM audit_log
        WHERE event_type = 'kill_switch' AND action = 'on'
          AND created_at >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()[0]

    rl = con.execute(
        f"""
        SELECT COUNT(*) FROM audit_log
        WHERE event_type = 'rate_limit' AND action = 'exceeded'
          AND created_at >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()[0]

    cb = con.execute(
        f"""
        SELECT COUNT(*) FROM audit_log
        WHERE event_type = 'circuit_breaker'
          AND created_at >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()[0]

    idx_errors = con.execute(
        "SELECT COUNT(*) FROM indexer_state WHERE last_run_status = 'failed'"
    ).fetchone()[0]

    lines = ["\n⚙️ <b>Orchestrateur</b>"]
    lines.append(f"  Kill switches activés : {ks}")
    lines.append(f"  Rate limits atteints : {rl}")
    lines.append(f"  Circuit breakers : {cb}")
    lines.append(f"  Erreurs indexers : {idx_errors}")

    return "\n".join(lines)


def _section_costs(con, interval: str) -> str:
    llm_calls = con.execute(
        f"""
        SELECT COUNT(*) FROM resolution_risk_cache
        WHERE computed_at >= CURRENT_DATE - INTERVAL {interval}
        """
    ).fetchone()[0]

    llm_cost = llm_calls * 0.001

    lines = ["\n💰 <b>Coûts</b>"]
    lines.append(f"  LLM Haiku : ~${llm_cost:.2f} ({llm_calls} calls)")
    lines.append("  VPS : $4/mois")

    return "\n".join(lines)
