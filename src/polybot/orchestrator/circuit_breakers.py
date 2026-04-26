"""Circuit breakers — automatic safeguards based on system health."""

import asyncio
import os

import structlog

from polybot.db.connection import db_read_with_retry
from polybot.orchestrator.audit_log import log_audit
from polybot.orchestrator.kill_switches import (
    _invalidate_cache,
    is_component_enabled,
    set_kill_switch,
)

logger = structlog.get_logger()

INDEXER_NAME_TO_TARGET = {
    "onchain_alchemy": "onchain",
    "resolutions_uma": "resolutions",
    "markets_gamma": "markets",
    "proxy_factory": "markets",
    "trades_dataapi": "trades",
}

FAILURE_THRESHOLD = 3
LLM_COST_PER_CALL = 0.001
LLM_MONTHLY_LIMIT = 3.0
DISK_USAGE_THRESHOLD = 0.80
CHECK_INTERVAL = 300


class CircuitBreaker:
    def __init__(self, db_path: str, bot=None):
        self.db_path = db_path
        self.bot = bot
        self._indexer_failures: dict[str, int] = {}
        self._disk_warning_sent = False

    def check_indexer_health(self) -> None:
        """Check indexer_state for consecutive failures."""
        def _read(con):
            return con.execute(
                "SELECT indexer_name, last_run_status FROM indexer_state"
            ).fetchall()

        rows = db_read_with_retry(self.db_path, _read)

        for name, status in rows:
            target = INDEXER_NAME_TO_TARGET.get(name)
            if not target:
                continue

            if status == "failed":
                self._indexer_failures[name] = self._indexer_failures.get(name, 0) + 1
                failures = self._indexer_failures[name]
                if failures >= FAILURE_THRESHOLD and is_component_enabled(self.db_path, target):
                    reason = f"{name}: {failures} consecutive failures"
                    set_kill_switch(
                        self.db_path, target, enabled=True,
                        reason=reason, actor="circuit_breaker",
                    )
                    logger.error(
                        "circuit_breaker_indexer", indexer=name, failures=failures,
                    )
            else:
                self._indexer_failures[name] = 0

    def check_llm_cost(self) -> None:
        """Estimate monthly LLM cost and kill C3 if over budget."""
        def _read(con):
            return con.execute(
                "SELECT COUNT(*) FROM resolution_risk_cache "
                "WHERE computed_at >= date_trunc('month', CURRENT_DATE)"
            ).fetchone()[0]

        monthly_calls = db_read_with_retry(self.db_path, _read)
        estimated_cost = monthly_calls * LLM_COST_PER_CALL

        if estimated_cost > LLM_MONTHLY_LIMIT and is_component_enabled(self.db_path, "c3"):
            _invalidate_cache()
            set_kill_switch(
                self.db_path, "c3", enabled=True,
                reason=f"LLM cost ${estimated_cost:.2f} > ${LLM_MONTHLY_LIMIT:.2f} limit",
                actor="circuit_breaker",
            )
            logger.error(
                "circuit_breaker_llm_cost", estimated=estimated_cost, limit=LLM_MONTHLY_LIMIT,
            )

    def check_disk_usage(self) -> None:
        """Warn if disk usage exceeds threshold."""
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        stat = os.statvfs(db_dir)
        usage_pct = 1 - (stat.f_bavail / stat.f_blocks)

        if usage_pct > DISK_USAGE_THRESHOLD:
            if not self._disk_warning_sent:
                self._disk_warning_sent = True
                logger.error("circuit_breaker_disk", usage_pct=f"{usage_pct:.1%}")
                log_audit(
                    self.db_path, "circuit_breaker", "disk",
                    "warning", reason=f"Disk usage {usage_pct:.1%}", actor="system",
                )
        else:
            self._disk_warning_sent = False

    async def run_forever(self) -> None:
        """Check all circuit breakers every 5 minutes."""
        while True:
            try:
                self.check_indexer_health()
                self.check_llm_cost()
                self.check_disk_usage()
            except Exception:
                logger.exception("circuit_breaker_error")
            await asyncio.sleep(CHECK_INTERVAL)
