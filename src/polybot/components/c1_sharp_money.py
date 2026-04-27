"""C1 Sharp Money — detect Tier A wallet trades and emit alerts."""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

import duckdb
import structlog

from polybot.components.sizing import compute_size
from polybot.config import Settings
from polybot.db.connection import connect as db_connect
from polybot.db.connection import db_write_with_retry
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


def _next_exit_id(con: duckdb.DuckDBPyConnection) -> str:
    """Generate next EXIT id: EXIT_YYYYMMDD_NNNN scanning audit_log.target."""
    today = datetime.now(UTC).strftime("%Y%m%d")
    prefix = f"EXIT_{today}_"
    row = con.execute(
        "SELECT target FROM audit_log "
        "WHERE event_type = 'position_exit' AND target LIKE ? "
        "ORDER BY target DESC LIMIT 1",
        [f"{prefix}%"],
    ).fetchone()
    if row is None:
        return f"{prefix}0001"
    last = row[0]
    n = int(last.rsplit("_", 1)[1]) + 1
    return f"{prefix}{n:04d}"


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


CURSOR_NAME = "c1_sharp_money"


def _load_cursor(db_path: str) -> datetime | None:
    """Load persisted last_check_ts from indexer_state, or None if not set."""
    from polybot.db.connection import db_read_with_retry

    def _do(con):
        row = con.execute(
            "SELECT last_cursor FROM indexer_state WHERE indexer_name = ?",
            [CURSOR_NAME],
        ).fetchone()
        if row and row[0]:
            try:
                return datetime.fromisoformat(row[0])
            except (ValueError, TypeError):
                return None
        return None

    return db_read_with_retry(db_path, _do)


def _persist_cursor(db_path: str, last_check_ts: datetime) -> None:
    """Upsert last_check_ts into indexer_state for c1_sharp_money."""
    def _do(con):
        con.execute(
            """
            INSERT OR REPLACE INTO indexer_state (
                indexer_name, last_synced_at, last_cursor,
                last_run_status, updated_at
            ) VALUES (?, NOW(), ?, 'success', NOW())
            """,
            [CURSOR_NAME, last_check_ts.isoformat()],
        )

    db_write_with_retry(db_path, _do)


def _format_alert(
    wallet_name: str,
    tier_label: str,
    market_title: str,
    outcome: str,
    price: float,
    size_usd: float,
    size_suggested: float,
    bankroll: float,
    alert_id: str,
    tags: list[str],
    risk_score: float = 0.3,
    risk_category: str = "MEDIUM",
    risk_reason: str | None = None,
) -> str:
    """Format C1 alert message for Telegram — compact, mobile-first."""
    pct = round(size_suggested / bankroll * 100, 1) if bankroll > 0 else 0

    risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(
        risk_category, "🟡"
    )
    risk_line = f"⚖️ Risk : {risk_icon} {risk_category} ({risk_score:.2f})"
    if risk_reason:
        risk_line += f"\n   └ {risk_reason}"

    parts = [
        f"🎯 <b>C1 Sharp Money</b>  ·  <code>{alert_id}</code>",
        "",
        f"<b>{market_title}</b>",
        f"👤 {wallet_name}  ·  Tier {tier_label}",
        "",
        f"BUY {outcome} @ <b>{price:.2f}</b>  ·  ${size_usd:,.0f}",
        f"💡 Sizing : <b>${size_suggested:,.0f}</b> ({pct}% bankroll)",
        risk_line,
    ]
    if tags:
        parts.append("\n".join(tags))

    return "\n".join(parts)


def _humanize_time_held(delta: timedelta) -> str:
    """Format a timedelta as 'Xh' (< 24h) or 'Xj' (>= 24h). Negative → '0h'."""
    total_seconds = max(0.0, delta.total_seconds())
    hours = int(total_seconds // 3600)
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}j"


def _format_exit_message(
    exit_id: str,
    wallet_name: str,
    tier_label: str,
    market_title: str,
    outcome: str,
    entry_price: float,
    exit_price: float,
    exit_size_usd: float,
    pnl_pct: float,
    time_held: str,
) -> str:
    """Format an EXIT notification message for Telegram (HTML)."""
    pnl_sign = "+" if pnl_pct >= 0 else ""
    parts = [
        f"⚠️ <b>Position Exit</b>  ·  <code>{exit_id}</code>",
        "",
        f"<b>{market_title}</b>",
        f"👤 {wallet_name}  ·  Tier {tier_label}",
        "",
        f"💰 Entrée : BUY {outcome} @ <b>{entry_price:.2f}</b>  (il y a {time_held})",
        f"📤 Sortie : SELL @ <b>{exit_price:.2f}</b>  ({pnl_sign}{pnl_pct:.1f}%)",
        f"💵 Size exit : ${exit_size_usd:,.0f}",
        "",
        "💡 Si vous avez copié, envisagez de sortir aussi.",
    ]
    return "\n".join(parts)


def _build_inline_keyboard(
    event_slug: str | None,
    wallet: str,
    alert_id: str,
):
    """Build inline keyboard for the alert message."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    market_url = (
        f"https://polymarket.com/event/{event_slug}"
        if event_slug
        else "https://polymarket.com"
    )
    wallet_url = f"https://polymarket.com/portfolio/{wallet}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Marché", url=market_url),
            InlineKeyboardButton("👤 Wallet", url=wallet_url),
        ],
        [
            InlineKeyboardButton("✅ Copié", callback_data=f"copied:{alert_id}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{alert_id}"),
        ],
    ])


class SharpMoneyDetector:
    """Polls trades table and emits C1 alerts for Tier A wallets."""

    def __init__(self, bot: PolyBot, settings: Settings):
        self.bot = bot
        self.settings = settings
        self.db_path = str(settings.DUCKDB_PATH)
        loaded = _load_cursor(self.db_path)
        self.last_check_ts = loaded if loaded else datetime.now(UTC)
        if loaded:
            logger.info("c1_cursor_loaded", last_check_ts=loaded.isoformat())
        self.risk_scorer = None
        if settings.ANTHROPIC_API_KEY:
            from polybot.components.c3_resolution_risk import ResolutionRiskScorer

            self.risk_scorer = ResolutionRiskScorer(
                db_path=self.db_path,
                anthropic_api_key=settings.ANTHROPIC_API_KEY,
            )
        self._exit_notified: set[tuple[str, str, str]] = set()

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

        # C3 Resolution Risk
        risk_score = 0.3
        risk_category = "MEDIUM"
        risk_reason = None
        if self.risk_scorer:
            try:
                risk_result = self.risk_scorer.score_market(condition_id)
                risk_score = risk_result["score"]
                risk_category = risk_result["category"]
                if risk_result.get("reasons"):
                    risk_reason = risk_result["reasons"][0]
                if risk_result.get("llm_unavailable"):
                    tags.append("⚠️ LLM unavailable — rules-only score")
            except Exception:
                logger.warning("c3_scoring_failed", condition_id=condition_id[:16])

        if risk_category == "CRITICAL":
            tags.insert(0, "🔴 CRITICAL RISK")

        # Build tier label
        tier_label = "A1" if tier_a_conf >= 0.90 else "A2"

        # Insert alert into DB first to get alert_id
        def _insert_alert(con):
            aid = _next_alert_id(con)
            con.execute(
                """
                INSERT INTO alerts (
                    alert_id, component, emitted_at, trade_hash,
                    wallet_address, condition_id, side, size_usd, price,
                    size_suggested_usd, resolution_risk_score,
                    tags, shadow_mode, dedup_hash
                ) VALUES (?, 'C1', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE, ?)
                """,
                [
                    aid,
                    trade["transaction_hash"],
                    wallet,
                    condition_id,
                    trade["side"],
                    size_usd,
                    float(trade["price"]),
                    size_suggested,
                    risk_score,
                    ",".join(tags) if tags else None,
                    dhash,
                ],
            )
            return aid

        alert_id = db_write_with_retry(self.db_path, _insert_alert)

        # Format alert + inline keyboard
        message = _format_alert(
            wallet_name=trade["wallet_name"] or wallet[:12],
            tier_label=tier_label,
            market_title=trade["market_title"] or condition_id[:20],
            outcome=trade["outcome"] or "Yes",
            price=float(trade["price"]),
            size_usd=size_usd,
            size_suggested=size_suggested,
            bankroll=bankroll,
            alert_id=alert_id,
            tags=tags,
            risk_score=risk_score,
            risk_category=risk_category,
            risk_reason=risk_reason,
        )
        keyboard = _build_inline_keyboard(
            event_slug=trade["event_slug"],
            wallet=wallet,
            alert_id=alert_id,
        )

        from polybot.orchestrator.kill_switches import is_component_enabled
        from polybot.orchestrator.rate_limits import check_rate_limit, increment_counter

        if not is_component_enabled(self.db_path, "c1"):
            logger.info("c1_killed", alert_id=alert_id)
            return

        if not check_rate_limit(self.db_path, "c1"):
            logger.warning("c1_rate_limit_exceeded", alert_id=alert_id)
            return

        # Route based on shadow mode
        topic = "ops" if self.settings.SHADOW_MODE else "alerts"
        msg_id = await self.bot.send_alert(topic, message, reply_markup=keyboard)

        increment_counter(self.db_path, "c1")

        # Also send to #risk if CRITICAL
        if risk_category == "CRITICAL":
            await self.bot.send_alert("risk", message)

        if msg_id:
            db_write_with_retry(
                self.db_path,
                lambda con: con.execute(
                    "UPDATE alerts SET telegram_message_id = ? WHERE alert_id = ?",
                    [msg_id, alert_id],
                ),
            )

        logger.info(
            "c1_alert_emitted",
            alert_id=alert_id,
            wallet=wallet[:10],
            market=condition_id[:10],
            size_usd=size_usd,
            size_suggested=size_suggested,
        )
        return True

    async def _process_exit(self, trade: dict) -> bool:
        """Emit an EXIT notification if SELL closes a pending C1 position.

        Returns True if a notification was emitted.
        """
        # Filter: SELL only (defensive — caller already routes by side).
        if trade["side"] != "SELL":
            return False

        # Filter: minimum size for EXIT.
        size_usd = float(trade["size_usd"])
        if size_usd < self.settings.C1_EXIT_SIZE_MIN_USD:
            return False

        wallet = trade["proxy_wallet"]
        condition_id = trade["condition_id"]
        sell_outcome = trade["outcome"]

        # In-memory dedup: one notification per (wallet, market, outcome).
        key = (wallet, condition_id, sell_outcome)
        if key in self._exit_notified:
            return False

        # Look up a pending C1 alert that matches outcome.
        pending = self._find_pending_buy_alert(wallet, condition_id, sell_outcome)
        if pending is None:
            return False

        # Happy path lands in Task 6.
        return False

    def _find_pending_buy_alert(
        self, wallet: str, condition_id: str, outcome: str
    ) -> dict | None:
        """Return the most recent unresolved C1 BUY alert on (wallet, market, outcome)."""
        con = db_connect(self.db_path, read_only=True)
        try:
            row = con.execute(
                """
                SELECT a.alert_id, t_buy.outcome, a.price AS entry_price,
                       a.size_suggested_usd, a.emitted_at
                FROM alerts a
                JOIN trades t_buy ON a.trade_hash = t_buy.transaction_hash
                LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
                WHERE a.component = 'C1'
                  AND a.wallet_address = ?
                  AND a.condition_id = ?
                  AND t_buy.outcome = ?
                  AND (ao.resolution_outcome IS NULL
                       OR ao.resolution_outcome = 'PENDING')
                ORDER BY a.emitted_at DESC LIMIT 1
                """,
                [wallet, condition_id, outcome],
            ).fetchone()
        finally:
            con.close()

        if row is None:
            return None
        return {
            "alert_id": row[0],
            "outcome": row[1],
            "entry_price": float(row[2]),
            "size_suggested_usd": float(row[3]) if row[3] is not None else None,
            "emitted_at": row[4],
        }

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

        # Update cursor to latest trade timestamp + persist to DB
        max_ts = max(
            (t["timestamp_ts"] for t in trades if t["timestamp_ts"]),
            default=self.last_check_ts,
        )
        self.last_check_ts = max_ts
        try:
            _persist_cursor(self.db_path, self.last_check_ts)
        except Exception:
            logger.exception("c1_cursor_persist_failed")

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
