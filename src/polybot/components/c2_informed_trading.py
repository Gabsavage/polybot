"""C2 Informed Trading — detect insider/sharp patterns on hot markets."""

import asyncio
import time
from datetime import UTC, datetime

import structlog

from polybot.config import Settings
from polybot.db.connection import connect as db_connect
from polybot.db.connection import db_write_with_retry

logger = structlog.get_logger()


def _next_alert_id(con) -> str:
    """Generate next alert_id: AL_YYYYMMDD_XXXX (shared sequence with C1)."""
    today = datetime.now(UTC).strftime("%Y%m%d")
    prefix = f"AL_{today}_"
    row = con.execute(
        "SELECT alert_id FROM alerts WHERE alert_id LIKE ? ORDER BY alert_id DESC LIMIT 1",
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
            "condition_id",
            "title",
            "slug",
            "event_slug",
            "end_date",
            "volume_24h",
            "liquidity_usd",
            "volume_cumulative_usd",
            "category",
            "vol_1h",
            "price_now",
            "price_1h_ago",
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

    def compute_shared_cex_deposit(self, condition_id: str) -> tuple[float, str | None]:
        """Ratio of active wallets sharing the most common CEX deposit address."""
        con = db_connect(self.db_path, read_only=True)
        total_row = con.execute(
            """
            SELECT COUNT(DISTINCT proxy_wallet)
            FROM trades_all
            WHERE condition_id = ? AND proxy_wallet IS NOT NULL
            """,
            [condition_id],
        ).fetchone()
        total = int(total_row[0]) if total_row else 0
        if total == 0:
            con.close()
            return 0.0, None

        row = con.execute(
            """
            WITH active_wallets AS (
                SELECT DISTINCT proxy_wallet
                FROM trades_all
                WHERE condition_id = ? AND proxy_wallet IS NOT NULL
            ),
            funded AS (
                SELECT aw.proxy_wallet, cfm.deposit_address, cfm.cex_source
                FROM active_wallets aw
                JOIN cex_funding_map cfm ON aw.proxy_wallet = cfm.wallet_address
                WHERE cfm.deposit_address IS NOT NULL
            )
            SELECT deposit_address, cex_source, COUNT(*) as cnt
            FROM funded
            GROUP BY deposit_address, cex_source
            ORDER BY cnt DESC
            LIMIT 1
            """,
            [condition_id],
        ).fetchone()
        con.close()

        if not row:
            return 0.0, None
        return row[2] / total, row[1]

    # --- Scoring ---

    def compute_score(self, condition_id: str) -> dict:
        """Compute all 8 features + score for a market."""
        fresh = self.compute_fresh_wallets_ratio(condition_id)
        top5 = self.compute_top5_concentration(condition_id)
        tte = self.compute_time_to_event(condition_id)
        niche = self.compute_niche_market_flag(condition_id)
        momentum = self.compute_momentum_1h(condition_id)
        zscore = self.compute_volume_zscore(condition_id)
        dominance = self.compute_single_dominance(condition_id)
        cex_deposit_ratio, cex_source = self.compute_shared_cex_deposit(condition_id)

        features = {
            "fresh_wallets": fresh > 0.50,
            "top5_concentration": top5 > 0.70,
            "time_to_event": tte is not None and tte < 48,
            "niche_market": niche,
            "momentum_1h": abs(momentum) > 0.05,
            "volume_zscore": zscore > 3.0,
            "single_dominance": dominance > 0.60,
            "shared_cex_deposit": cex_deposit_ratio > 0.30,
        }
        raw_values = {
            "fresh_wallets": round(fresh, 4),
            "top5_concentration": round(top5, 4),
            "time_to_event": round(tte, 1) if tte is not None else None,
            "niche_market": niche,
            "momentum_1h": round(momentum, 4),
            "volume_zscore": round(zscore, 2),
            "single_dominance": round(dominance, 4),
            "shared_cex_deposit": round(cex_deposit_ratio, 4),
            "shared_cex_deposit_source": cex_source,
        }
        score = sum(features.values())
        features_passed = [k for k, v in features.items() if v]

        return {
            "score": score,
            "features": features,
            "features_passed": features_passed,
            "raw_values": raw_values,
        }

    # --- Alignment v0 ---

    def compute_alignment(self, condition_id: str) -> dict:
        """Compute price momentum alignment for a C2 alert.

        Returns {alignment_score: -1|0|+1|None, momentum_4h: float|None,
                 direction: str|None}.
        """
        con = db_connect(self.db_path, read_only=True)

        # Price now: VWAP last 10 min
        row_now = con.execute(
            """
            SELECT SUM(price * size_usd) / NULLIF(SUM(size_usd), 0)
            FROM trades_all
            WHERE condition_id = ?
              AND timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 10 MINUTE
            """,
            [condition_id],
        ).fetchone()
        price_now = float(row_now[0]) if row_now and row_now[0] else None

        # Price 4h ago: VWAP in window [4h15m ago, 3h45m ago]
        row_4h = con.execute(
            """
            SELECT SUM(price * size_usd) / NULLIF(SUM(size_usd), 0)
            FROM trades_all
            WHERE condition_id = ?
              AND timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 255 MINUTE
              AND timestamp_ts < CURRENT_TIMESTAMP - INTERVAL 225 MINUTE
            """,
            [condition_id],
        ).fetchone()
        price_4h = float(row_4h[0]) if row_4h and row_4h[0] else None

        # Dominant direction: majority of 1h volume BUY or SELL
        row_dir = con.execute(
            """
            SELECT
                SUM(CASE WHEN side = 'BUY' THEN size_usd ELSE 0 END) AS buy_vol,
                SUM(CASE WHEN side = 'SELL' THEN size_usd ELSE 0 END) AS sell_vol
            FROM trades_all
            WHERE condition_id = ?
              AND timestamp_ts >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
            """,
            [condition_id],
        ).fetchone()
        con.close()

        buy_vol = float(row_dir[0] or 0) if row_dir else 0
        sell_vol = float(row_dir[1] or 0) if row_dir else 0

        if buy_vol == 0 and sell_vol == 0:
            return {"alignment_score": None, "momentum_4h": None, "direction": None}

        direction = "BUY" if buy_vol >= sell_vol else "SELL"

        if price_now is None or price_4h is None or price_4h == 0:
            return {"alignment_score": None, "momentum_4h": None, "direction": direction}

        momentum_4h = (price_now - price_4h) / price_4h

        # Alignment logic:
        # BUY dominant + price going up → +1 (follows movement)
        # BUY dominant + price going down → -1 (contrarian)
        # SELL dominant → symmetric
        threshold = 0.01  # 1%
        if direction == "BUY":
            if momentum_4h > threshold:
                alignment = 1
            elif momentum_4h < -threshold:
                alignment = -1
            else:
                alignment = 0
        else:  # SELL dominant
            if momentum_4h < -threshold:
                alignment = 1
            elif momentum_4h > threshold:
                alignment = -1
            else:
                alignment = 0

        return {
            "alignment_score": alignment,
            "momentum_4h": round(momentum_4h, 4),
            "direction": direction,
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
            "SELECT COUNT(*) FROM alerts WHERE component = 'C2' AND emitted_at >= CURRENT_DATE"
        ).fetchone()[0]
        con.close()
        return hourly < 2 and daily < 5

    # --- Alert insertion ---

    def _insert_alert(
        self,
        condition_id: str,
        market: dict,
        result: dict,
        alignment: dict,
        risk_score: float = 0.3,
    ) -> str:
        """Insert C2 alert into alerts table. Returns alert_id."""

        def _do(con):
            aid = _next_alert_id(con)
            con.execute(
                """
                INSERT INTO alerts (
                    alert_id, component, emitted_at,
                    condition_id, price, size_usd,
                    score, features_passed,
                    alignment_score, momentum_4h,
                    resolution_risk_score,
                    shadow_mode
                ) VALUES (?, 'C2', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, TRUE)
                """,
                [
                    aid,
                    condition_id,
                    float(market.get("price_now") or 0),
                    float(market.get("vol_1h") or 0),
                    result["score"],
                    ",".join(result["features_passed"]),
                    alignment.get("alignment_score"),
                    alignment.get("momentum_4h"),
                    risk_score,
                ],
            )
            return aid

        return db_write_with_retry(self.db_path, _do)

    # --- Alert formatting ---

    def _format_alert(
        self,
        market: dict,
        result: dict,
        alignment: dict,
        risk_score: float,
        risk_category: str,
        alert_id: str,
    ) -> str:
        """Format C2 alert message for Telegram."""
        title = market.get("title") or market["condition_id"][:40]
        price_now = market.get("price_now")
        price_ago = market.get("price_1h_ago")
        vol_1h = float(market.get("vol_1h") or 0)

        # Price change line
        if price_now and price_ago and float(price_ago) > 0:
            pn, pa = float(price_now), float(price_ago)
            change_pct = (pn - pa) / pa * 100
            price_line = f"📈 Prix : {pa:.2f} → {pn:.2f} ({change_pct:+.1f}%)"
        elif price_now:
            price_line = f"📈 Prix : {float(price_now):.2f}"
        else:
            price_line = "📈 Prix : N/A"

        # Z-score
        zscore = result["raw_values"].get("volume_zscore", 0)
        vol_line = f"💹 Volume 1h : ${vol_1h:,.0f} (Z-score {zscore:.1f})"

        # Features
        raw = result["raw_values"]
        feature_lines = []
        for f in result["features_passed"]:
            if f == "fresh_wallets":
                feature_lines.append(f"  ✓ Fresh wallets : {raw['fresh_wallets']:.0%}")
            elif f == "top5_concentration":
                feature_lines.append(f"  ✓ Top-5 concentration : {raw['top5_concentration']:.0%}")
            elif f == "time_to_event":
                feature_lines.append(f"  ✓ {raw['time_to_event']:.0f}h avant résolution")
            elif f == "niche_market":
                feature_lines.append("  ✓ Niche market")
            elif f == "momentum_1h":
                feature_lines.append(f"  ✓ Momentum 1h : {raw['momentum_1h']:+.1%}")
            elif f == "volume_zscore":
                feature_lines.append(f"  ✓ Volume Z-score : {zscore:.1f}")
            elif f == "single_dominance":
                feature_lines.append(f"  ✓ Single dominance : {raw['single_dominance']:.0%}")

        # Alignment
        a_score = alignment.get("alignment_score")
        m4h = alignment.get("momentum_4h")
        if a_score == 1:
            align_str = "📈 Suit le mouvement"
        elif a_score == -1:
            align_str = "📉 Contrariant"
        elif a_score == 0:
            align_str = "➡️ Neutre"
        else:
            align_str = "❓ Données insuffisantes"
        m4h_str = f" ({m4h:+.1%})" if m4h is not None else ""
        align_line = f"🧭 Alignment : {align_str}{m4h_str}"

        # Risk
        risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(
            risk_category, "🟡"
        )
        risk_line = f"⚖️ Risk : {risk_icon} {risk_category} ({risk_score:.2f})"

        # Market link
        event_slug = market.get("event_slug")
        link = (
            f"https://polymarket.com/event/{event_slug}" if event_slug else "https://polymarket.com"
        )

        parts = [
            "🔴 <b>Informed Trading Alert (C2)</b>",
            "",
            f"<b>{title}</b>",
            price_line,
            vol_line,
            "",
            f"🧬 Score : <b>{result['score']}/7</b>",
            *feature_lines,
            "",
            align_line,
            risk_line,
            "",
            f"🔗 {link}",
            f"⏱️ <code>{alert_id}</code>",
        ]
        return "\n".join(parts)

    # --- Main scan loop ---

    def _get_risk_scorer(self):
        """Lazy-init C3 risk scorer if API key available."""
        if not hasattr(self, "_risk_scorer"):
            self._risk_scorer = None
            if self.settings.ANTHROPIC_API_KEY:
                from polybot.components.c3_resolution_risk import ResolutionRiskScorer

                self._risk_scorer = ResolutionRiskScorer(
                    db_path=self.db_path,
                    anthropic_api_key=self.settings.ANTHROPIC_API_KEY,
                )
        return self._risk_scorer

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

            from polybot.orchestrator.rate_limits import check_rate_limit as check_rl

            if not check_rl(self.db_path, "c2"):
                logger.info("c2_rate_limit_reached")
                break

            # Alignment v0 (informational only)
            alignment = self.compute_alignment(cid)

            # C3 risk score
            risk_score = 0.3
            risk_category = "MEDIUM"
            scorer = self._get_risk_scorer()
            if scorer:
                try:
                    risk_result = scorer.score_market(cid)
                    risk_score = risk_result["score"]
                    risk_category = risk_result["category"]
                except Exception:
                    logger.warning("c2_c3_scoring_failed", condition_id=cid[:16])

            alert_id = self._insert_alert(
                cid,
                market,
                result,
                alignment,
                risk_score,
            )

            alert = {
                "alert_id": alert_id,
                "condition_id": cid,
                "market": market,
                "score": result["score"],
                "features_passed": result["features_passed"],
                "raw_values": result["raw_values"],
                "alignment": alignment,
                "risk_score": risk_score,
                "risk_category": risk_category,
            }
            alerts_emitted.append(alert)

            logger.info(
                "c2_alert_emitted",
                alert_id=alert_id,
                market=market.get("title", cid[:20]),
                score=result["score"],
                features=result["features_passed"],
                alignment=alignment.get("alignment_score"),
            )

        return alerts_emitted

    async def _emit_telegram(self, alert: dict) -> None:
        """Send C2 alert to Telegram."""
        if not self.bot:
            return

        from polybot.orchestrator.kill_switches import is_component_enabled

        if not is_component_enabled(self.db_path, "c2"):
            logger.info("c2_killed", alert_id=alert["alert_id"])
            return

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        message = self._format_alert(
            market=alert["market"],
            result=alert,
            alignment=alert["alignment"],
            risk_score=alert["risk_score"],
            risk_category=alert["risk_category"],
            alert_id=alert["alert_id"],
        )

        event_slug = alert["market"].get("event_slug")
        market_url = (
            f"https://polymarket.com/event/{event_slug}" if event_slug else "https://polymarket.com"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📊 Marché", url=market_url)],
            ]
        )

        # Route based on shadow mode
        topic = "ops" if self.settings.SHADOW_MODE else "alerts"
        msg_id = await self.bot.send_alert(topic, message, reply_markup=keyboard)

        from polybot.orchestrator.rate_limits import increment_counter

        increment_counter(self.db_path, "c2")

        if msg_id:
            db_write_with_retry(
                self.db_path,
                lambda con: con.execute(
                    "UPDATE alerts SET telegram_message_id = ? WHERE alert_id = ?",
                    [msg_id, alert["alert_id"]],
                ),
            )

    async def run_forever(self) -> None:
        """Main loop: scan every 5 min."""
        logger.info("c2_starting", scan_interval=self.settings.C2_SCAN_INTERVAL)
        while True:
            start = time.monotonic()
            try:
                alerts = self.scan_once()
                for alert in alerts:
                    await self._emit_telegram(alert)
                if alerts:
                    logger.info("c2_scan_complete", alerts=len(alerts))
            except Exception:
                logger.exception("c2_scan_error")
            elapsed = time.monotonic() - start
            sleep_time = max(0, self.settings.C2_SCAN_INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)
