"""Enrich past alerts with resolution outcomes for calibration."""

import structlog

from polybot.db.connection import connect as db_connect, db_write_with_retry

logger = structlog.get_logger()


def log_alert_outcomes(db_path: str) -> int:
    """Enrich past alerts with resolution outcomes.

    Joins alerts with resolutions to compute was_direction_correct
    and shadow P&L. Returns count of newly resolved alerts.
    """
    # Read unresolved alerts (read-only, no lock contention)
    con = db_connect(db_path, read_only=True)
    unresolved = con.execute(
        """
        SELECT a.alert_id, a.condition_id, a.side, a.price,
               a.size_suggested_usd, a.component
        FROM alerts a
        LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
        WHERE ao.alert_id IS NULL
           OR ao.resolution_outcome = 'PENDING'
        """
    ).fetchall()
    con.close()

    if not unresolved:
        return 0

    # Read all resolutions we might need (read-only)
    condition_ids = list({row[1] for row in unresolved})
    con = db_connect(db_path, read_only=True)
    placeholders = ", ".join(["?"] * len(condition_ids))
    resolutions_rows = con.execute(
        f"""
        SELECT condition_id, settled_outcome, settled_at, final_price
        FROM resolutions
        WHERE condition_id IN ({placeholders})
          AND settled_outcome IS NOT NULL
        """,
        condition_ids,
    ).fetchall()
    con.close()

    resolutions_map = {r[0]: r[1:] for r in resolutions_rows}

    resolved_count = 0

    def _process_all(con):
        nonlocal resolved_count
        for row in unresolved:
            alert_id, condition_id, side, price, size_suggested, component = row

            resolution = resolutions_map.get(condition_id)

            if not resolution:
                con.execute(
                    """
                    INSERT INTO alert_outcomes (alert_id, condition_id, resolution_outcome)
                    VALUES (?, ?, 'PENDING')
                    ON CONFLICT (alert_id) DO NOTHING
                    """,
                    [alert_id, condition_id],
                )
                continue

            settled_outcome, settled_at, final_price = resolution

            if settled_outcome == "INVALID":
                con.execute(
                    """
                    INSERT INTO alert_outcomes
                    (alert_id, condition_id, resolved_at, resolution_outcome,
                     price_at_alert, shadow_pnl_simulated)
                    VALUES (?, ?, ?, 'INVALID', ?, 0)
                    ON CONFLICT (alert_id) DO UPDATE SET
                        resolved_at = EXCLUDED.resolved_at,
                        resolution_outcome = EXCLUDED.resolution_outcome,
                        shadow_pnl_simulated = 0
                    """,
                    [alert_id, condition_id, settled_at, float(price) if price else None],
                )
                resolved_count += 1
                continue

            if side == "BUY" or side is None:
                was_correct = settled_outcome == "YES"
            else:
                was_correct = settled_outcome == "NO"

            shadow_pnl = 0.0
            p = float(price) if price else None
            s = float(size_suggested) if size_suggested else None
            if was_correct and p and s and p > 0:
                shadow_pnl = s * (1.0 / p - 1.0)
            elif not was_correct and s:
                shadow_pnl = -s

            con.execute(
                """
                INSERT INTO alert_outcomes
                (alert_id, condition_id, resolved_at, resolution_outcome,
                 direction_traded, was_direction_correct, price_at_alert,
                 price_at_resolution, shadow_pnl_simulated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (alert_id) DO UPDATE SET
                    resolved_at = EXCLUDED.resolved_at,
                    resolution_outcome = EXCLUDED.resolution_outcome,
                    was_direction_correct = EXCLUDED.was_direction_correct,
                    price_at_resolution = EXCLUDED.price_at_resolution,
                    shadow_pnl_simulated = EXCLUDED.shadow_pnl_simulated
                """,
                [
                    alert_id, condition_id, settled_at, settled_outcome,
                    side, was_correct,
                    float(price) if price else None,
                    float(final_price) if final_price else None,
                    shadow_pnl,
                ],
            )

            con.execute(
                "UPDATE alerts SET outcome_known = TRUE, was_direction_correct = ? "
                "WHERE alert_id = ?",
                [was_correct, alert_id],
            )

            resolved_count += 1

    db_write_with_retry(db_path, _process_all)

    if resolved_count:
        logger.info("alert_outcomes_resolved", count=resolved_count)

    return resolved_count
