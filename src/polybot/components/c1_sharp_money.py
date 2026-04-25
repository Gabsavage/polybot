"""C1 Sharp Money — detect Tier A wallet trades and emit alerts."""

import asyncio
import hashlib
from datetime import UTC, datetime

import duckdb
import structlog

from polybot.components.sizing import compute_size
from polybot.config import Settings
from polybot.db.connection import connect as db_connect
from polybot.telegram.bot import PolyBot

logger = structlog.get_logger()


def _next_alert_id(con: duckdb.DuckDBPyConnection) -> str:
    """Generate next alert_id: AL_YYYYMMDD_XXXX (sequential daily)."""
    today = datetime.now(UTC).strftime("%Y%m%d")
    prefix = f"AL_{today}_"
    row = con.execute(
        "SELECT alert_id FROM alerts "
        "WHERE alert_id LIKE ? ORDER BY alert_id DESC LIMIT 1",
        [f"{prefix}%"],
    ).fetchone()
    seq = int(row[0].split("_")[-1]) + 1 if row else 1
    return f"{prefix}{seq:04d}"


def _dedup_hash(
    wallet: str, condition_id: str, side: str, ts_unix: int, bucket_s: int
) -> str:
    """Hash bucket for dedup: (wallet, market, side, time_bucket)."""
    bucket = f"{wallet}_{condition_id}_{side}_{ts_unix // bucket_s}"
    return hashlib.sha256(bucket.encode()).hexdigest()[:16]


def _get_bankroll(con: duckdb.DuckDBPyConnection) -> tuple[float | None, datetime | None]:
    """Read current bankroll. Returns (amount, updated_at) or (None, None)."""
    row = con.execute(
        "SELECT amount, updated_at FROM bankroll_state WHERE id = 1"
    ).fetchone()
    if row:
        return float(row[0]), row[1]
    return None, None


def _format_alert(
    wallet_name: str,
    tier_label: str,
    market_title: str,
    outcome: str,
    price: float,
    size_usd: float,
    size_suggested: float,
    bankroll: float,
    event_slug: str | None,
    alert_id: str,
    tags: list[str],
) -> str:
    """Format C1 alert message for Telegram."""
    pct = round(size_suggested / bankroll * 100, 1) if bankroll > 0 else 0
    tag_lines = "\n".join(tags) if tags else ""
    link = (
        f"https://polymarket.com/event/{event_slug}"
        if event_slug
        else "https://polymarket.com"
    )

    parts = [
        "🎯 <b>Sharp Money Alert (C1)</b>",
        f"👤 Wallet : {wallet_name} (Tier {tier_label})",
        f"📊 Marché : {market_title}",
        f"💰 Trade : BUY {outcome} @ {price:.2f}",
        f"💵 Size : ${size_usd:,.0f}",
        "⚖️ Resolution Risk : N/A",
        f"💡 Size suggéré : ${size_suggested:,.2f} ({pct}%, quarter-Kelly)",
    ]
    if tag_lines:
        parts.append(tag_lines)
    parts.append(f"🔗 {link}")
    parts.append(f"⏱️ {alert_id}")

    return "\n".join(parts)


class SharpMoneyDetector:
    """Polls trades table and emits C1 alerts for Tier A wallets."""

    def __init__(self, bot: PolyBot, settings: Settings):
        self.bot = bot
        self.settings = settings
        self.db_path = str(settings.DUCKDB_PATH)
        self.last_check_ts = datetime.now(UTC)

    def _fetch_new_trades(self) -> list[dict]:
        """Query trades since last check, joined with tracked_wallets."""
        con = db_connect(self.db_path, read_only=True)
        rows = con.execute(
            """
            SELECT t.transaction_hash, t.proxy_wallet, t.condition_id,
                   t.side, t.size_usd, t.price, t.outcome,
                   t.timestamp_ts, t.market_title, t.event_slug,
                   tw.tier_a_confidence,
                   COALESCE(t.wallet_name, t.proxy_wallet) AS wallet_name,
                   m.liquidity_usd
            FROM trades t
            JOIN tracked_wallets tw ON t.proxy_wallet = tw.address
            LEFT JOIN markets m ON t.condition_id = m.condition_id
            WHERE t.timestamp_ts > ?
              AND tw.tier = 'A'
              AND tw.active = TRUE
            ORDER BY t.timestamp_ts ASC
            """,
            [self.last_check_ts],
        ).fetchall()
        con.close()

        columns = [
            "transaction_hash", "proxy_wallet", "condition_id",
            "side", "size_usd", "price", "outcome",
            "timestamp_ts", "market_title", "event_slug",
            "tier_a_confidence", "wallet_name", "liquidity_usd",
        ]
        return [dict(zip(columns, row, strict=False)) for row in rows]

    def _check_rate_limit(self, wallet: str, condition_id: str) -> bool:
        """Returns True if rate-limited (alert already exists within window)."""
        hours = self.settings.C1_RATE_LIMIT_HOURS
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            "SELECT 1 FROM alerts "
            "WHERE wallet_address = ? AND condition_id = ? "
            f"AND emitted_at > NOW() - INTERVAL {hours} HOUR "
            "LIMIT 1",
            [wallet, condition_id],
        ).fetchone()
        con.close()
        return row is not None

    def _check_dedup(self, dedup_hash: str) -> bool:
        """Returns True if this hash was already seen recently."""
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            "SELECT 1 FROM alerts WHERE dedup_hash = ? LIMIT 1",
            [dedup_hash],
        ).fetchone()
        con.close()
        return row is not None

    def _build_tags(
        self, liquidity: float | None, size_suggested: float, bankroll_age_days: int
    ) -> list[str]:
        tags = []
        if liquidity is not None and liquidity < 10 * size_suggested:
            tags.append("⚠️ low_liquidity")
        if bankroll_age_days > 14:
            tags.append(f"⚠️ bankroll_stale ({bankroll_age_days}j)")
        return tags

    async def _process_trade(self, trade: dict) -> bool:
        """Apply filters and emit alert if trade passes. Returns True if emitted."""
        # Filter: BUY only
        if trade["side"] != "BUY":
            return False

        # Filter 1: Size minimum
        size_usd = float(trade["size_usd"])
        if size_usd < self.settings.C1_SIZE_MIN_USD:
            return False

        # Filter 4: Liquidity minimum
        liquidity = float(trade["liquidity_usd"]) if trade["liquidity_usd"] else None
        if liquidity is not None and liquidity < self.settings.C1_LIQUIDITY_MIN_DEPTH:
            return False

        wallet = trade["proxy_wallet"]
        condition_id = trade["condition_id"]

        # Filter 2: Rate limit
        if self._check_rate_limit(wallet, condition_id):
            return False

        # Filter 3: Dedup
        ts_unix = int(trade["timestamp_ts"].timestamp()) if trade["timestamp_ts"] else 0
        dhash = _dedup_hash(
            wallet, condition_id, trade["side"],
            ts_unix, self.settings.C1_DEDUP_BUCKET_SECONDS,
        )
        if self._check_dedup(dhash):
            return False

        # Sizing
        con = db_connect(self.db_path, read_only=True)
        bankroll, bankroll_updated = _get_bankroll(con)
        con.close()

        if bankroll is None or bankroll <= 0:
            logger.warning("no_bankroll_set")
            return False

        tier_a_conf = float(trade["tier_a_confidence"]) if trade["tier_a_confidence"] else 0.5
        size_suggested = compute_size(bankroll, tier_a_conf, self.settings)
        if size_suggested is None:
            return False

        # Tags
        bankroll_age_days = 0
        if bankroll_updated:
            bankroll_age_days = (
                datetime.now(UTC) - bankroll_updated.replace(tzinfo=UTC)
            ).days
        tags = self._build_tags(liquidity, size_suggested, bankroll_age_days)

        # Build tier label
        tier_label = "A1" if tier_a_conf >= 0.90 else "A2"

        # Format alert
        message = _format_alert(
            wallet_name=trade["wallet_name"] or wallet[:12],
            tier_label=tier_label,
            market_title=trade["market_title"] or condition_id[:20],
            outcome=trade["outcome"] or "Yes",
            price=float(trade["price"]),
            size_usd=size_usd,
            size_suggested=size_suggested,
            bankroll=bankroll,
            event_slug=trade["event_slug"],
            alert_id="",  # placeholder, set after DB insert
            tags=tags,
        )

        # Insert alert into DB
        con = db_connect(self.db_path)
        alert_id = _next_alert_id(con)
        con.execute(
            """
            INSERT INTO alerts (
                alert_id, component, emitted_at, trade_hash,
                wallet_address, condition_id, side, size_usd, price,
                size_suggested_usd, resolution_risk_score,
                tags, shadow_mode, dedup_hash
            ) VALUES (?, 'C1', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, 0.3, ?, TRUE, ?)
            """,
            [
                alert_id,
                trade["transaction_hash"],
                wallet,
                condition_id,
                trade["side"],
                size_usd,
                float(trade["price"]),
                size_suggested,
                ",".join(tags) if tags else None,
                dhash,
            ],
        )
        con.close()

        # Update alert_id in message and send
        message = message.replace("⏱️ ", f"⏱️ {alert_id}")

        # M4: all alerts go to #ops (shadow/dry run)
        msg_id = await self.bot.send_alert("ops", message)

        if msg_id:
            con = db_connect(self.db_path)
            con.execute(
                "UPDATE alerts SET telegram_message_id = ? WHERE alert_id = ?",
                [msg_id, alert_id],
            )
            con.close()

        logger.info(
            "c1_alert_emitted",
            alert_id=alert_id,
            wallet=wallet[:10],
            market=condition_id[:10],
            size_usd=size_usd,
            size_suggested=size_suggested,
        )
        return True

    async def poll_once(self) -> int:
        """One polling cycle. Returns number of alerts emitted."""
        trades = self._fetch_new_trades()
        if not trades:
            return 0

        emitted = 0
        for trade in trades:
            try:
                if await self._process_trade(trade):
                    emitted += 1
            except Exception:
                logger.exception(
                    "c1_trade_processing_error",
                    tx=trade.get("transaction_hash", "?")[:16],
                )

        # Update cursor to latest trade timestamp
        max_ts = max(
            (t["timestamp_ts"] for t in trades if t["timestamp_ts"]),
            default=self.last_check_ts,
        )
        self.last_check_ts = max_ts

        if emitted:
            logger.info("c1_poll_complete", new_alerts=emitted, trades_checked=len(trades))
        return emitted

    async def run_forever(self) -> None:
        """Main loop: poll trades every C1_POLL_INTERVAL seconds."""
        logger.info("c1_starting", poll_interval=self.settings.C1_POLL_INTERVAL)
        while True:
            try:
                await self.poll_once()
            except Exception:
                logger.exception("c1_poll_error")
            await asyncio.sleep(self.settings.C1_POLL_INTERVAL)
