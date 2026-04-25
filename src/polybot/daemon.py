"""Polybot M6 daemon — Telegram bot + C1 Sharp Money + C2 Informed Trading + daily report."""

import asyncio
from datetime import datetime, time, timedelta, timezone

import structlog
from telegram import BotCommand

from polybot.components.c1_sharp_money import SharpMoneyDetector
from polybot.components.c2_informed_trading import InformedTradingDetector
from polybot.components.report import generate_report
from polybot.config import Settings
from polybot.jobs.log_alert_outcomes import log_alert_outcomes
from polybot.logging import setup_logging
from polybot.telegram.bot import PolyBot

logger = structlog.get_logger()

CEST = timezone(timedelta(hours=2))
DAILY_REPORT_HOUR = 9  # 09:00 CEST


async def schedule_daily_report(bot: PolyBot, db_path: str) -> None:
    """Send daily report at 09:00 CEST every day."""
    while True:
        now = datetime.now(CEST)
        target = datetime.combine(now.date(), time(DAILY_REPORT_HOUR, 0), CEST)
        if now >= target:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        logger.info("daily_report_scheduled", next_at=target.isoformat(), wait_s=int(wait_seconds))
        await asyncio.sleep(wait_seconds)

        try:
            resolved = log_alert_outcomes(db_path)
            if resolved:
                logger.info("alert_outcomes_enriched", count=resolved)
            report = generate_report(db_path, days=1, bot_start=bot.start_time)
            await bot.send_alert("ops", report)
            logger.info("daily_report_sent")
        except Exception:
            logger.exception("daily_report_failed")


async def main() -> None:
    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)

    logger.info("daemon_starting")

    bot = PolyBot(settings)
    c1 = SharpMoneyDetector(bot=bot, settings=settings)
    c2 = InformedTradingDetector(settings=settings, bot=bot)
    db_path = str(settings.DUCKDB_PATH)

    async with bot.app:
        await bot.app.start()
        await bot.app.updater.start_polling(drop_pending_updates=True)
        await bot.app.bot.set_my_commands([
            BotCommand("status", "Santé du système"),
            BotCommand("bankroll", "Afficher / mettre à jour le bankroll"),
            BotCommand("report", "Rapport performance quotidien"),
            BotCommand("risk", "Analyse resolution risk d'un marché"),
            BotCommand("recent", "Dernières alertes C1"),
            BotCommand("toggle", "Toggle shadow mode on/off"),
            BotCommand("help", "Liste des commandes"),
        ])
        logger.info("telegram_bot_started")

        try:
            await asyncio.gather(
                c1.run_forever(),
                c2.run_forever(),
                schedule_daily_report(bot, db_path),
            )
        finally:
            await bot.app.updater.stop()
            await bot.app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("daemon_stopped_by_user")
