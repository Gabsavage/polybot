"""Polybot Telegram bot — commands + alert emission."""

import contextlib
from datetime import UTC, datetime, timedelta

import structlog
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from polybot.config import Settings
from polybot.db.connection import connect as db_connect, db_write_with_retry

logger = structlog.get_logger()


class PolyBot:
    """Telegram bot with commands and alert routing."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_path = str(settings.DUCKDB_PATH)
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.topics = {
            "alerts": settings.TELEGRAM_TOPIC_ALERTS,
            "ops": settings.TELEGRAM_TOPIC_OPS,
            "errors": settings.TELEGRAM_TOPIC_ERRORS,
            "risk": settings.TELEGRAM_TOPIC_RISK,
        }
        self.start_time = datetime.now(UTC)
        self.app = (
            Application.builder()
            .token(settings.TELEGRAM_BOT_TOKEN)
            .build()
        )
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("bankroll", self._cmd_bankroll))
        self.app.add_handler(CommandHandler("report", self._cmd_report))
        self.app.add_handler(CommandHandler("risk", self._cmd_risk))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("recent", self._cmd_recent))
        self.app.add_handler(CommandHandler("toggle", self._cmd_toggle))
        self.app.add_handler(CallbackQueryHandler(self._cb_alert_action))

    async def send_alert(
        self, topic: str, message: str, reply_markup=None
    ) -> int | None:
        """Send a message to a topic in the group. Returns message_id."""
        thread_id = self.topics.get(topic)
        if not thread_id:
            logger.warning("unknown_topic", topic=topic)
            return None
        try:
            msg = await self.app.bot.send_message(
                chat_id=self.chat_id,
                message_thread_id=thread_id,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
            return msg.message_id
        except Exception:
            logger.exception("telegram_send_failed", topic=topic)
            return None

    # --- Callback queries ---

    async def _cb_alert_action(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle Copié / Skip button presses."""
        query = update.callback_query
        await query.answer()

        data = query.data or ""
        if ":" not in data:
            return

        action, alert_id = data.split(":", 1)
        if action not in ("copied", "skip"):
            return

        # Update alignment_score in DB: copied=+1, skip=-1
        score = 1 if action == "copied" else -1
        db_write_with_retry(
            self.db_path,
            lambda con: con.execute(
                "UPDATE alerts SET alignment_score = ? WHERE alert_id = ?",
                [score, alert_id],
            ),
        )

        # Update button text to show selection
        label = "✅ Copié" if action == "copied" else "⏭️ Skip"
        try:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.edit_message_text(
                text=query.message.text_html + f"\n\n<i>{label}</i>",
                parse_mode="HTML",
            )
        except Exception:
            pass

        logger.info(
            "alert_action",
            alert_id=alert_id,
            action=action,
            score=score,
        )

    # --- Commands ---

    async def _cmd_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        con = db_connect(self.db_path, read_only=True)
        try:
            # Trades 24h
            trades_24h = con.execute(
                "SELECT COUNT(*) FROM trades "
                "WHERE timestamp_ts > NOW() - INTERVAL 24 HOUR"
            ).fetchone()[0]

            # Alerts 24h
            alerts_24h = con.execute(
                "SELECT COUNT(*) FROM alerts "
                "WHERE emitted_at > NOW() - INTERVAL 24 HOUR"
            ).fetchone()[0]

            # Last trade
            last_trade = con.execute(
                "SELECT MAX(timestamp_ts) FROM trades"
            ).fetchone()[0]

            # Indexer states
            indexers = con.execute(
                "SELECT indexer_name, last_run_status, last_synced_at "
                "FROM indexer_state ORDER BY indexer_name"
            ).fetchall()
        finally:
            con.close()

        uptime = datetime.now(UTC) - self.start_time
        uptime_str = f"{uptime.days}d {uptime.seconds // 3600}h"

        lines = [
            "<b>📊 Polybot Status</b>",
            f"⏱ Uptime: {uptime_str}",
            f"📈 Trades 24h: {trades_24h}",
            f"🎯 Alerts 24h: {alerts_24h}",
            f"🕐 Last trade: {last_trade or 'N/A'}",
            "",
            "<b>Indexers:</b>",
        ]
        for name, status, synced in indexers:
            icon = "✅" if status == "success" else "❌"
            lines.append(f"  {icon} {name}: {status} ({synced})")

        await update.message.reply_text(
            "\n".join(lines), parse_mode="HTML"
        )

    async def _cmd_bankroll(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        args = context.args or []

        if len(args) >= 2 and args[0].lower() == "set":
            try:
                amount = float(args[1])
            except ValueError:
                await update.message.reply_text("Usage: /bankroll set <montant>")
                return

            db_write_with_retry(
                self.db_path,
                lambda con: con.execute(
                    "INSERT OR REPLACE INTO bankroll_state (id, amount, updated_at) "
                    "VALUES (1, ?, CURRENT_TIMESTAMP)",
                    [amount],
                ),
            )
            await update.message.reply_text(f"Bankroll mis à jour : ${amount:,.2f}")
            return

        # Display current bankroll
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            "SELECT amount, updated_at FROM bankroll_state WHERE id = 1"
        ).fetchone()
        con.close()

        if not row:
            await update.message.reply_text(
                "Bankroll non configuré. Usage: /bankroll set <montant>"
            )
            return

        amount, updated_at = row
        age = datetime.now(UTC) - updated_at.replace(tzinfo=UTC)
        warning = ""
        if age > timedelta(days=14):
            warning = f"\n⚠️ Dernière MAJ il y a {age.days} jours"

        await update.message.reply_text(
            f"💰 Bankroll : ${float(amount):,.2f}\n"
            f"📅 MAJ : {updated_at}{warning}"
        )

    async def _cmd_report(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        from polybot.components.report import generate_report

        args = context.args or []
        days = 1
        if args:
            with contextlib.suppress(ValueError):
                days = min(int(args[0]), 30)

        report = generate_report(self.db_path, days=days, bot_start=self.start_time)
        await update.message.reply_text(report, parse_mode="HTML")

    async def _cmd_risk(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        from polybot.components.c3_resolution_risk import ResolutionRiskScorer

        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Usage: /risk &lt;slug ou URL polymarket&gt;",
                parse_mode="HTML",
            )
            return

        query = args[0]
        slug = query.rstrip("/").split("/")[-1] if "polymarket.com" in query else query

        # Lookup condition_id from slug or event_slug
        con = db_connect(self.db_path, read_only=True)
        row = con.execute(
            "SELECT condition_id, title, category, resolution_source, end_date, event_slug "
            "FROM markets WHERE slug = ? OR event_slug = ? LIMIT 1",
            [slug, slug],
        ).fetchone()
        con.close()

        if not row:
            await update.message.reply_text(f"Marché '{slug}' non trouvé.")
            return

        condition_id, title, category, res_source, end_date, event_slug = row

        if not self.settings.ANTHROPIC_API_KEY:
            await update.message.reply_text("ANTHROPIC_API_KEY non configurée.")
            return

        scorer = ResolutionRiskScorer(
            self.db_path, self.settings.ANTHROPIC_API_KEY
        )
        result = scorer.score_market(condition_id)

        risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(
            result["category"], "🟡"
        )

        cat = result["category"]
        sc = result["score"]
        lines = [
            f"⚖️ <b>Resolution Risk</b> — {risk_icon} <b>{cat}</b> ({sc:.2f})",
            "",
            f"<b>{title or slug}</b>",
            "",
        ]

        for r in result.get("reasons", [])[:3]:
            lines.append(f"✅ {r}")

        red_flags = result.get("red_flags", [])
        if red_flags:
            lines.append("")
            for flag in red_flags:
                lines.append(f"⚠️ {flag}")

        if result.get("llm_unavailable"):
            lines.append("\n<i>⚠️ Score basé sur les règles uniquement</i>")

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        market_url = (
            f"https://polymarket.com/event/{event_slug}"
            if event_slug
            else "https://polymarket.com"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Voir le marché", url=market_url)],
        ])

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )

    async def _cmd_toggle(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        args = context.args or []
        if not args or args[0].lower() != "shadow":
            await update.message.reply_text("Usage: /toggle shadow")
            return

        self.settings.SHADOW_MODE = not self.settings.SHADOW_MODE
        state = "ON" if self.settings.SHADOW_MODE else "OFF"
        channel = "#ops" if self.settings.SHADOW_MODE else "#alerts"
        await update.message.reply_text(
            f"Shadow mode: <b>{state}</b> — alertes dans {channel}",
            parse_mode="HTML",
        )
        logger.info("shadow_mode_toggled", shadow_mode=self.settings.SHADOW_MODE)

    async def _cmd_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.message.reply_text(
            "<b>Polybot Commands</b>\n\n"
            "/status — Santé du système\n"
            "/bankroll — Afficher le bankroll\n"
            "/bankroll set &lt;montant&gt; — Mettre à jour le bankroll\n"
            "/report [N] — Rapport performance (N jours, défaut 1)\n"
            "/risk &lt;slug&gt; — Analyse resolution risk d'un marché\n"
            "/recent [N] — N dernières alertes (défaut 5)\n"
            "/toggle shadow — Basculer shadow mode on/off\n"
            "/help — Cette aide",
            parse_mode="HTML",
        )

    async def _cmd_recent(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        args = context.args or []
        n = 5
        if args:
            with contextlib.suppress(ValueError):
                n = min(int(args[0]), 20)

        con = db_connect(self.db_path, read_only=True)
        rows = con.execute(
            "SELECT alert_id, wallet_address, condition_id, side, "
            "size_usd, emitted_at FROM alerts "
            "ORDER BY emitted_at DESC LIMIT ?",
            [n],
        ).fetchall()
        con.close()

        if not rows:
            await update.message.reply_text("Aucune alerte récente.")
            return

        lines = [f"<b>📋 {len(rows)} dernières alertes</b>"]
        for alert_id, wallet, _cond, side, size, ts in rows:
            w = wallet[:10] if wallet else "?"
            lines.append(f"  {alert_id} | {w}… | {side} ${float(size):,.0f} | {ts}")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
