"""Kill switches — disable components without restarting the daemon."""

import time

import structlog

from polybot.db.connection import db_read_with_retry, db_write_with_retry
from polybot.orchestrator.audit_log import log_audit

logger = structlog.get_logger()

VALID_TARGETS = frozenset({
    "c1", "c2", "c3", "all_alerts",
    "trades", "markets", "onchain", "resolutions",
})

ALERT_COMPONENTS = frozenset({"c1", "c2"})

_cache: set[str] = set()
_cache_time: float = 0.0
_CACHE_TTL = 10.0


def _invalidate_cache() -> None:
    global _cache, _cache_time
    _cache = set()
    _cache_time = 0.0


def _refresh_cache(db_path: str) -> None:
    global _cache, _cache_time

    now = time.monotonic()
    if now - _cache_time < _CACHE_TTL:
        return

    def _read(con):
        rows = con.execute(
            "SELECT target FROM kill_switches WHERE enabled = TRUE"
        ).fetchall()
        return {r[0] for r in rows}

    _cache = db_read_with_retry(db_path, _read)
    _cache_time = time.monotonic()


def is_component_enabled(db_path: str, component: str) -> bool:
    """Returns True if the component can operate.

    For alert components (c1, c2), also checks 'all_alerts'.
    """
    _refresh_cache(db_path)

    if component in _cache:
        return False
    return not (component in ALERT_COMPONENTS and "all_alerts" in _cache)


def set_kill_switch(
    db_path: str,
    target: str,
    enabled: bool,
    reason: str = None,
    actor: str = "manual",
) -> None:
    """Toggle a kill switch. Persists to DB, invalidates cache, logs to audit."""
    if target not in VALID_TARGETS:
        raise ValueError(f"Invalid kill switch target: {target}")

    def _do(con):
        con.execute(
            "INSERT INTO kill_switches (target, enabled, reason, toggled_at, toggled_by) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?) "
            "ON CONFLICT (target) DO UPDATE SET "
            "enabled = EXCLUDED.enabled, reason = EXCLUDED.reason, "
            "toggled_at = EXCLUDED.toggled_at, toggled_by = EXCLUDED.toggled_by",
            [target, enabled, reason, actor],
        )

    db_write_with_retry(db_path, _do)
    _invalidate_cache()

    action = "on" if enabled else "off"
    log_audit(db_path, "kill_switch", target, action, reason=reason, actor=actor)
    logger.info("kill_switch_set", target=target, enabled=enabled, reason=reason, actor=actor)
