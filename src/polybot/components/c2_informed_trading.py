"""C2 Informed Trading — detect insider/sharp patterns on hot markets."""

import asyncio
import time
from datetime import UTC, datetime

import structlog

from polybot.config import Settings
from polybot.db.connection import connect as db_connect

logger = structlog.get_logger()


def _next_alert_id(con) -> str:
    """Generate next alert_id: AL_YYYYMMDD_XXXX (shared sequence with C1)."""
    today = datetime.now(UTC).strftime("%Y%m%d")
    prefix = f"AL_{today}_"
    row = con.execute(
        "SELECT alert_id FROM alerts "
        "WHERE alert_id LIKE ? ORDER BY alert_id DESC LIMIT 1",
        [f"{prefix}%"],
    ).fetchone()
    seq = int(row[0].split("_")[-1]) + 1 if row else 1
    return f"{prefix}{seq:04d}"


class InformedTradingDetector:
    """Scans hot markets every 5 min for informed trading patterns."""

    def __init__(self, settings: Settings, bot=None):
        self.settings = settings
        self.db_path = str(settings.DUCKDB_PATH)
        self.bot = bot

    # --- Hot market selection ---

    def get_hot_markets(self) -> list[dict]:
        """Identify markets meeting at least 1 of 3 hot criteria."""
        con = db_connect(self.db_path, read_only=True)

        # Condition 1: Volume spike — vol_1h from trades_all vs volume_24h/24
        # Condition 2: Price move > 10% in 1h + volume > $500
        # Condition 3: Near resolution (< 72h) + volume_24h > $10K
        rows = con.execute(
            """
            WITH vol_1h AS (
                SELECT condition_id, SUM(size_usd) AS vol
                FROM trades_all
                WHERE timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
                GROUP BY condition_id
            ),
            price_move AS (
                SELECT
                    condition_id,
                    (SELECT AVG(price) FROM trades_all t2
                     WHERE t2.condition_id = t1.condition_id
                       AND t2.timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 10 MINUTE
                    ) AS price_now,
                    (SELECT AVG(price) FROM trades_all t3
                     WHERE t3.condition_id = t1.condition_id
                       AND t3.timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 70 MINUTE
                       AND t3.timestamp_ts < CURRENT_TIMESTAMP - INTERVAL 50 MINUTE
                    ) AS price_1h_ago
                FROM (SELECT DISTINCT condition_id FROM trades_all
                      WHERE timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 70 MINUTE
                ) t1
            )
            SELECT
                m.condition_id,
                m.title,
                m.slug,
                m.event_slug,
                m.end_date,
                m.volume_24h,
                m.liquidity_usd,
                m.volume_cumulative_usd,
                m.category,
                COALESCE(v.vol, 0) AS vol_1h,
                pm.price_now,
                pm.price_1h_ago
            FROM markets m
            LEFT JOIN vol_1h v ON v.condition_id = m.condition_id
            LEFT JOIN price_move pm ON pm.condition_id = m.condition_id
            WHERE COALESCE(m.resolved, FALSE) = FALSE
              AND COALESCE(m.active, TRUE) = TRUE
              AND (
                  -- Condition 1: volume spike > 3x hourly avg
                  (COALESCE(v.vol, 0) > 0
                   AND m.volume_24h > 0
                   AND v.vol / (m.volume_24h / 24) > 3)
                  -- Condition 2: price move > 10% with volume
                  OR (pm.price_now IS NOT NULL
                      AND pm.price_1h_ago IS NOT NULL
                      AND pm.price_1h_ago > 0
                      AND ABS(pm.price_now - pm.price_1h_ago) / pm.price_1h_ago > 0.10
                      AND COALESCE(v.vol, 0) > 500)
                  -- Condition 3: near resolution + volume
                  OR (m.end_date IS NOT NULL
                      AND m.end_date > CURRENT_TIMESTAMP
                      AND EXTRACT(EPOCH FROM (m.end_date - CURRENT_TIMESTAMP)) / 3600 < 72
                      AND COALESCE(m.volume_24h, 0) > 10000)
              )
            """
        ).fetchall()
        con.close()

        columns = [
            "condition_id", "title", "slug", "event_slug", "end_date",
            "volume_24h", "liquidity_usd", "volume_cumulative_usd",
            "category", "vol_1h", "price_now", "price_1h_ago",
        ]
        return [dict(zip(columns, row, strict=False)) for row in rows]

    # --- 7 Features ---

    def compute_fresh_wallets_ratio(self, condition_id: str) -> float:
        """% of 1h volume from wallets first seen < 7 days ago."""
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            """
            WITH recent_trades AS (
                SELECT proxy_wallet, size_usd, timestamp_ts
                FROM trades_all
                WHERE condition_id = ?
                  AND timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
            ),
            wallet_ages AS (
                SELECT proxy_wallet, MIN(timestamp_ts) AS first_seen
                FROM trades_all
                GROUP BY proxy_wallet
            )
            SELECT
                SUM(CASE
                    WHEN rt.timestamp_ts - COALESCE(wa.first_seen, rt.timestamp_ts)
                         < INTERVAL 7 DAY
                    THEN rt.size_usd ELSE 0
                END) / NULLIF(SUM(rt.size_usd), 0)
            FROM recent_trades rt
            LEFT JOIN wallet_ages wa ON wa.proxy_wallet = rt.proxy_wallet
            """,
            [condition_id],
        ).fetchone()
        con.close()
        return float(row[0]) if row and row[0] is not None else 0.0

    def compute_top5_concentration(self, condition_id: str) -> float:
        """Share of 1h volume held by top 5 traders."""
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            """
            WITH vols AS (
                SELECT proxy_wallet, SUM(size_usd) AS vol
                FROM trades_all
                WHERE condition_id = ?
                  AND timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
                GROUP BY proxy_wallet
            ),
            top5 AS (
                SELECT vol FROM vols ORDER BY vol DESC LIMIT 5
            )
            SELECT
                (SELECT COALESCE(SUM(vol), 0) FROM top5)
                / NULLIF((SELECT SUM(vol) FROM vols), 0)
            """,
            [condition_id],
        ).fetchone()
        con.close()
        return float(row[0]) if row and row[0] is not None else 0.0

    def compute_time_to_event(self, condition_id: str) -> float | None:
        """Hours until resolution. None if no end_date."""
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            "SELECT end_date FROM markets WHERE condition_id = ?",
            [condition_id],
        ).fetchone()
        con.close()
        if not row or row[0] is None:
            return None
        end_date = row[0]
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=UTC)
        delta = (end_date - datetime.now(UTC)).total_seconds()
        return delta / 3600 if delta > 0 else 0.0

    def compute_niche_market_flag(self, condition_id: str) -> bool:
        """True if cumulative volume < $50K."""
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            "SELECT volume_cumulative_usd FROM markets WHERE condition_id = ?",
            [condition_id],
        ).fetchone()
        con.close()
        if not row or row[0] is None:
            return True  # unknown market = niche
        return float(row[0]) < 50_000

    def compute_momentum_1h(self, condition_id: str) -> float:
        """Price change over 1h from trades_all VWAP."""
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            """
            SELECT
                (SELECT SUM(price * size_usd) / NULLIF(SUM(size_usd), 0)
                 FROM trades_all
                 WHERE condition_id = ?
                   AND timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 10 MINUTE
                ) AS price_now,
                (SELECT SUM(price * size_usd) / NULLIF(SUM(size_usd), 0)
                 FROM trades_all
                 WHERE condition_id = ?
                   AND timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 70 MINUTE
                   AND timestamp_ts < CURRENT_TIMESTAMP - INTERVAL 50 MINUTE
                ) AS price_1h_ago
            """,
            [condition_id, condition_id],
        ).fetchone()
        con.close()
        if not row or row[0] is None or row[1] is None or row[1] == 0:
            return 0.0
        return (float(row[0]) - float(row[1])) / float(row[1])

    def compute_volume_zscore(self, condition_id: str) -> float:
        """Vol 1h vs hourly baseline from volume_24h. Returns ratio as proxy."""
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            """
            SELECT
                (SELECT COALESCE(SUM(size_usd), 0)
                 FROM trades_all
                 WHERE condition_id = ?
                   AND timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
                ) AS vol_1h,
                m.volume_24h
            FROM markets m
            WHERE m.condition_id = ?
            """,
            [condition_id, condition_id],
        ).fetchone()
        con.close()
        if not row or row[1] is None or float(row[1]) == 0:
            return 0.0
        vol_1h = float(row[0])
        hourly_avg = float(row[1]) / 24
        if hourly_avg <= 0:
            return 0.0
        return vol_1h / hourly_avg

    def compute_single_dominance(self, condition_id: str) -> float:
        """Max single wallet share of 1h volume."""
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            """
            WITH vols AS (
                SELECT proxy_wallet, SUM(size_usd) AS vol
                FROM trades_all
                WHERE condition_id = ?
                  AND timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
                GROUP BY proxy_wallet
            )
            SELECT MAX(vol) / NULLIF(SUM(vol), 0) FROM vols
            """,
            [condition_id],
        ).fetchone()
        con.close()
        return float(row[0]) if row and row[0] is not None else 0.0

    # --- Scoring ---

    def compute_score(self, condition_id: str) -> dict:
        """Compute all 7 features + score for a market."""
        fresh = self.compute_fresh_wallets_ratio(condition_id)
        top5 = self.compute_top5_concentration(condition_id)
        tte = self.compute_time_to_event(condition_id)
        niche = self.compute_niche_market_flag(condition_id)
        momentum = self.compute_momentum_1h(condition_id)
        zscore = self.compute_volume_zscore(condition_id)
        dominance = self.compute_single_dominance(condition_id)

        features = {
            "fresh_wallets": fresh > 0.50,
            "top5_concentration": top5 > 0.70,
            "time_to_event": tte is not None and tte < 48,
            "niche_market": niche,
            "momentum_1h": abs(momentum) > 0.05,
            "volume_zscore": zscore > 3.0,
            "single_dominance": dominance > 0.60,
        }
        raw_values = {
            "fresh_wallets": round(fresh, 4),
            "top5_concentration": round(top5, 4),
            "time_to_event": round(tte, 1) if tte is not None else None,
            "niche_market": niche,
            "momentum_1h": round(momentum, 4),
            "volume_zscore": round(zscore, 2),
            "single_dominance": round(dominance, 4),
        }
        score = sum(features.values())
        features_passed = [k for k, v in features.items() if v]

        return {
            "score": score,
            "features": features,
            "features_passed": features_passed,
            "raw_values": raw_values,
        }

    # --- Dedup and rate limiting ---

    def check_dedup(self, condition_id: str) -> bool:
        """True if OK to emit (no C2 alert on this market in last 6h)."""
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            "SELECT 1 FROM alerts "
            "WHERE component = 'C2' AND condition_id = ? "
            "AND emitted_at > CURRENT_TIMESTAMP - INTERVAL 6 HOUR "
            "LIMIT 1",
            [condition_id],
        ).fetchone()
        con.close()
        return row is None

    def check_rate_limit(self) -> bool:
        """True if under hourly (2) and daily (5) caps."""
        con = db_connect(self.db_path, read_only=True)
        hourly = con.execute(
            "SELECT COUNT(*) FROM alerts "
            "WHERE component = 'C2' "
            "AND emitted_at > CURRENT_TIMESTAMP - INTERVAL 1 HOUR"
        ).fetchone()[0]
        daily = con.execute(
            "SELECT COUNT(*) FROM alerts "
            "WHERE component = 'C2' "
            "AND emitted_at >= CURRENT_DATE"
        ).fetchone()[0]
        con.close()
        return hourly < 2 and daily < 5

    # --- Alert insertion ---

    def _insert_alert(self, condition_id: str, market: dict, result: dict) -> str:
        """Insert C2 alert into alerts table. Returns alert_id."""
        con = db_connect(self.db_path)
        alert_id = _next_alert_id(con)
        con.execute(
            """
            INSERT INTO alerts (
                alert_id, component, emitted_at,
                condition_id, price, size_usd,
                score, features_passed,
                shadow_mode
            ) VALUES (?, 'C2', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, TRUE)
            """,
            [
                alert_id,
                condition_id,
                float(market.get("price_now") or 0),
                float(market.get("vol_1h") or 0),
                result["score"],
                ",".join(result["features_passed"]),
            ],
        )
        con.close()
        return alert_id

    # --- Main scan loop ---

    def scan_once(self) -> list[dict]:
        """One scan cycle. Returns list of alerts emitted."""
        hot_markets = self.get_hot_markets()
        logger.info("c2_scan", hot_markets=len(hot_markets))

        alerts_emitted = []

        for market in hot_markets:
            cid = market["condition_id"]

            result = self.compute_score(cid)

            if result["score"] < 4:
                continue

            if not self.check_dedup(cid):
                logger.debug("c2_dedup_blocked", condition_id=cid[:16])
                continue

            if not self.check_rate_limit():
                logger.info("c2_rate_limit_reached")
                break

            alert_id = self._insert_alert(cid, market, result)

            alert = {
                "alert_id": alert_id,
                "condition_id": cid,
                "market": market,
                "score": result["score"],
                "features_passed": result["features_passed"],
                "raw_values": result["raw_values"],
            }
            alerts_emitted.append(alert)

            logger.info(
                "c2_alert_emitted",
                alert_id=alert_id,
                market=market.get("title", cid[:20]),
                score=result["score"],
                features=result["features_passed"],
            )

        return alerts_emitted

    async def run_forever(self) -> None:
        """Main loop: scan every 5 min."""
        logger.info("c2_starting", scan_interval=self.settings.C2_SCAN_INTERVAL)
        while True:
            start = time.monotonic()
            try:
                alerts = self.scan_once()
                if alerts:
                    logger.info("c2_scan_complete", alerts=len(alerts))
            except Exception:
                logger.exception("c2_scan_error")
            elapsed = time.monotonic() - start
            sleep_time = max(0, self.settings.C2_SCAN_INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)
