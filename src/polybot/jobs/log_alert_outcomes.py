"""Enrich past alerts with resolution outcomes for calibration."""

import structlog

from polybot.db.connection import connect as db_connect

logger = structlog.get_logger()


def log_alert_outcomes(db_path: str) -> int:
    """Enrich past alerts with resolution outcomes.

    Joins alerts with resolutions to compute was_direction_correct
    and shadow P&L. Returns count of newly resolved alerts.
    """
    con = db_connect(db_path)

    # Find alerts not yet resolved in alert_outcomes
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

    resolved_count = 0

    for row in unresolved:
        alert_id, condition_id, side, price, size_suggested, component = row

        # Check if market resolved
        resolution = con.execute(
            """
            SELECT settled_outcome, settled_at, final_price
            FROM resolutions
            WHERE condition_id = ?
              AND settled_outcome IS NOT NULL
            """,
            [condition_id],
        ).fetchone()

        if not resolution:
            # Upsert PENDING
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

        # BUY side → wins if settled YES; SELL → wins if NO
        if side == "BUY" or side is None:
            was_correct = settled_outcome == "YES"
        else:
            was_correct = settled_outcome == "NO"

        # Shadow P&L
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

        # Update alerts table
        con.execute(
            "UPDATE alerts SET outcome_known = TRUE, was_direction_correct = ? "
            "WHERE alert_id = ?",
            [was_correct, alert_id],
        )

        resolved_count += 1

    con.close()

    if resolved_count:
        logger.info("alert_outcomes_resolved", count=resolved_count)

    return resolved_count
