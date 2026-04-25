"""Polybot M4 daemon — Telegram bot + C1 Sharp Money detector."""

import asyncio

import structlog
from telegram import BotCommand

from polybot.components.c1_sharp_money import SharpMoneyDetector
from polybot.config import Settings
from polybot.logging import setup_logging
from polybot.telegram.bot import PolyBot

logger = structlog.get_logger()


async def main() -> None:
    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)

    logger.info("daemon_starting")

    bot = PolyBot(settings)
    c1 = SharpMoneyDetector(bot=bot, settings=settings)

    # Start bot polling + C1 loop concurrently
    async with bot.app:
        await bot.app.start()
        await bot.app.updater.start_polling(drop_pending_updates=True)
        await bot.app.bot.set_my_commands([
            BotCommand("status", "Santé du système"),
            BotCommand("bankroll", "Afficher / mettre à jour le bankroll"),
            BotCommand("recent", "Dernières alertes C1"),
            BotCommand("help", "Liste des commandes"),
        ])
        logger.info("telegram_bot_started")

        try:
            await c1.run_forever()
        finally:
            await bot.app.updater.stop()
            await bot.app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("daemon_stopped_by_user")
