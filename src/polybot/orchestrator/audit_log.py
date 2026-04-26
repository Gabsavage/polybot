"""Audit log — persistent record of system events."""

import structlog

from polybot.db.connection import db_write_with_retry

logger = structlog.get_logger()


def log_audit(
    db_path: str,
    event_type: str,
    target: str,
    action: str,
    reason: str = None,
    actor: str = "system",
) -> None:
    """Insert an event into the audit_log table."""
    def _do(con):
        con.execute(
            "INSERT INTO audit_log (event_type, target, action, reason, actor) "
            "VALUES (?, ?, ?, ?, ?)",
            [event_type, target, action, reason, actor],
        )

    db_write_with_retry(db_path, _do)
    logger.info("audit_logged", event_type=event_type, target=target, action=action)
