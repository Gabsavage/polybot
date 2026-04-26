"""Polybot unified daemon — bot + C1 + C2 + all indexers + dashboard in one process."""

import asyncio
import threading
import time as time_mod
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta, timezone
from functools import partial

import structlog
import uvicorn
from telegram import BotCommand

from polybot.components.c1_sharp_money import SharpMoneyDetector
from polybot.components.c2_informed_trading import InformedTradingDetector
from polybot.components.report import generate_report
from polybot.components.weekly_report import generate_weekly_report
from polybot.config import Settings
from polybot.dashboard.api import app as dashboard_app
from polybot.indexers.cex_funding import run as run_cex_funding
from polybot.indexers.markets_gamma import run as run_markets
from polybot.indexers.onchain_alchemy import run as run_onchain
from polybot.indexers.proxy_factory import run as run_proxy
from polybot.indexers.resolutions_uma import run as run_resolutions
from polybot.indexers.trades_dataapi import run_forever as run_trades
from polybot.jobs.log_alert_outcomes import log_alert_outcomes
from polybot.logging import setup_logging
from polybot.orchestrator.circuit_breakers import CircuitBreaker
from polybot.orchestrator.kill_switches import is_component_enabled
from polybot.telegram.bot import PolyBot

logger = structlog.get_logger()

CEST = timezone(timedelta(hours=2))
DAILY_REPORT_HOUR = 9  # 09:00 CEST

INDEXER_KILL_TARGETS = {
    "markets_gamma": "markets",
    "proxy_factory": "markets",
    "resolutions_uma": "resolutions",
    "onchain_alchemy": "onchain",
}


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


async def schedule_weekly_report(bot: PolyBot, db_path: str) -> None:
    """Send weekly report every Sunday at 20:00 CEST."""
    while True:
        now = datetime.now(CEST)
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour >= 20:
            days_until_sunday = 7
        target = datetime.combine(
            now.date() + timedelta(days=days_until_sunday),
            time(20, 0),
            CEST,
        )
        wait = (target - now).total_seconds()
        logger.info("weekly_report_scheduled", next_at=target.isoformat(), wait_s=int(wait))
        await asyncio.sleep(wait)
        try:
            report = generate_weekly_report(db_path)
            await bot.send_alert("ops", report)
            logger.info("weekly_report_sent")
        except Exception:
            logger.exception("weekly_report_failed")


def _run_dashboard_blocking() -> None:
    """Run uvicorn in a blocking fashion (for use in a thread)."""
    uvicorn.run(
        dashboard_app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
    )


async def run_scheduled_indexer(
    name: str,
    fn,
    interval: int,
    executor: ThreadPoolExecutor,
    initial_delay: int = 0,
    **kwargs,
) -> None:
    """Run a sync indexer function periodically via the shared executor."""
    loop = asyncio.get_event_loop()
    logger.info("indexer_scheduled", indexer=name, interval=interval, initial_delay=initial_delay)

    if initial_delay:
        await asyncio.sleep(initial_delay)

    while True:
        kill_target = INDEXER_KILL_TARGETS.get(name)
        if kill_target and not is_component_enabled(kwargs.get("db_path", ""), kill_target):
            logger.info("indexer_killed", indexer=name)
            await asyncio.sleep(interval)
            continue
        start = time_mod.monotonic()
        try:
            bound = partial(fn, **kwargs)
            count = await loop.run_in_executor(executor, bound)
            elapsed_ms = int((time_mod.monotonic() - start) * 1000)
            logger.info("indexer_completed", indexer=name, count=count, duration_ms=elapsed_ms)
        except Exception:
            elapsed_ms = int((time_mod.monotonic() - start) * 1000)
            logger.exception("indexer_failed", indexer=name, duration_ms=elapsed_ms)

        elapsed = time_mod.monotonic() - start
        await asyncio.sleep(max(0, interval - elapsed))


async def main() -> None:
    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)

    logger.info("daemon_starting")

    bot = PolyBot(settings)
    c1 = SharpMoneyDetector(bot=bot, settings=settings)
    c2 = InformedTradingDetector(settings=settings, bot=bot)
    db_path = str(settings.DUCKDB_PATH)
    alchemy_url = settings.ALCHEMY_POLYGON_URL

    db_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="db-writer")
    circuit = CircuitBreaker(db_path=db_path, bot=bot)

    async with bot.app:
        await bot.app.start()
        await bot.app.updater.start_polling(drop_pending_updates=True)
        await bot.app.bot.set_my_commands(
            [
                BotCommand("status", "Santé du système"),
                BotCommand("bankroll", "Afficher / mettre à jour le bankroll"),
                BotCommand("report", "Rapport performance quotidien"),
                BotCommand("risk", "Analyse resolution risk d'un marché"),
                BotCommand("recent", "Dernières alertes C1"),
                BotCommand("toggle", "Kill switch / shadow mode"),
                BotCommand("audit", "Derniers événements d'audit"),
                BotCommand("weekly", "Rapport hebdomadaire"),
                BotCommand("help", "Liste des commandes"),
            ]
        )
        logger.info("telegram_bot_started")

        dashboard_thread = threading.Thread(
            target=_run_dashboard_blocking,
            daemon=True,
            name="dashboard-api",
        )
        dashboard_thread.start()
        logger.info("dashboard_api_started", host="127.0.0.1", port=8000)

        try:
            await asyncio.gather(
                c1.run_forever(),
                c2.run_forever(),
                schedule_daily_report(bot, db_path),
                schedule_weekly_report(bot, db_path),
                run_trades(db_path),
                run_scheduled_indexer(
                    "markets_gamma",
                    run_markets,
                    900,
                    db_executor,
                    initial_delay=0,
                    db_path=db_path,
                ),
                run_scheduled_indexer(
                    "proxy_factory",
                    run_proxy,
                    3600,
                    db_executor,
                    initial_delay=0,
                    db_path=db_path,
                    alchemy_url=alchemy_url,
                ),
                run_scheduled_indexer(
                    "resolutions_uma",
                    run_resolutions,
                    3600,
                    db_executor,
                    initial_delay=300,
                    db_path=db_path,
                    alchemy_url=alchemy_url,
                ),
                run_scheduled_indexer(
                    "onchain_alchemy",
                    run_onchain,
                    3600,
                    db_executor,
                    initial_delay=600,
                    db_path=db_path,
                    alchemy_url=alchemy_url,
                ),
                run_scheduled_indexer(
                    "cex_funding",
                    run_cex_funding,
                    3600,
                    db_executor,
                    initial_delay=1200,
                    db_path=db_path,
                    alchemy_url=alchemy_url,
                ),
                run_scheduled_indexer(
                    "alert_outcomes",
                    log_alert_outcomes,
                    3600,
                    db_executor,
                    initial_delay=900,
                    db_path=db_path,
                ),
                circuit.run_forever(),
            )
        finally:
            db_executor.shutdown(wait=False)
            await bot.app.updater.stop()
            await bot.app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("daemon_stopped_by_user")
