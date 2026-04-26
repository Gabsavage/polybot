"""Rate limits — throttle alert emission and API calls."""

from datetime import UTC, datetime, timedelta

import structlog

from polybot.db.connection import db_write_with_retry

logger = structlog.get_logger()

LIMITS: dict[str, dict[str, int]] = {
    "c1":   {"hourly": 10, "daily": 40},
    "c2":   {"hourly": 2,  "daily": 5},
    "risk": {"hourly": 20, "daily": 100},
    "llm":  {"hourly": 50, "daily": 200},
}

WINDOW_DURATIONS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(hours=24),
}

_digest_sent: set[tuple[str, str]] = set()


def _utcnow() -> datetime:
    """Return current UTC time as a naive datetime (for DuckDB TIMESTAMP storage)."""
    return datetime.now(UTC).replace(tzinfo=None)


def check_rate_limit(db_path: str, component: str) -> bool:
    """Returns True if the component is under both hourly and daily limits."""
    limits = LIMITS.get(component)
    if not limits:
        return True

    now = _utcnow()

    def _check(con):
        # First pass: detect any expired window
        any_expired = False
        for window, _max_count in limits.items():
            duration = WINDOW_DURATIONS[window]
            row = con.execute(
                "SELECT count, window_start FROM rate_limit_counters "
                "WHERE component = ? AND \"window\" = ?",
                [component, window],
            ).fetchone()

            if row is None:
                continue

            count, window_start = row
            if window_start.tzinfo is not None:
                window_start = window_start.replace(tzinfo=None)

            if now - window_start > duration:
                any_expired = True
                break

        # If any window has expired, reset ALL windows and return True
        if any_expired:
            con.execute(
                "UPDATE rate_limit_counters SET count = 0, window_start = ? "
                "WHERE component = ?",
                [now, component],
            )
            return True

        # No expired windows: check if any window is over its limit
        for window, max_count in limits.items():
            row = con.execute(
                "SELECT count FROM rate_limit_counters "
                "WHERE component = ? AND \"window\" = ?",
                [component, window],
            ).fetchone()

            if row is None:
                continue

            count = row[0]
            if count >= max_count:
                return False
        return True

    return db_write_with_retry(db_path, _check)


def increment_counter(db_path: str, component: str) -> None:
    """Increment both hourly and daily counters for this component."""
    now = _utcnow()

    def _do(con):
        for window in ("hourly", "daily"):
            row = con.execute(
                "SELECT count, window_start FROM rate_limit_counters "
                "WHERE component = ? AND \"window\" = ?",
                [component, window],
            ).fetchone()

            if row is None:
                con.execute(
                    "INSERT INTO rate_limit_counters (component, \"window\", count, window_start) "
                    "VALUES (?, ?, 1, ?)",
                    [component, window, now],
                )
            else:
                count, window_start = row
                if window_start.tzinfo is not None:
                    window_start = window_start.replace(tzinfo=None)
                duration = WINDOW_DURATIONS[window]
                if now - window_start > duration:
                    con.execute(
                        "UPDATE rate_limit_counters SET count = 1, window_start = ? "
                        "WHERE component = ? AND \"window\" = ?",
                        [now, component, window],
                    )
                else:
                    con.execute(
                        "UPDATE rate_limit_counters SET count = count + 1 "
                        "WHERE component = ? AND \"window\" = ?",
                        [component, window],
                    )

    db_write_with_retry(db_path, _do)


def clear_digest_sent() -> None:
    """Reset digest tracking (called at window boundaries or for testing)."""
    _digest_sent.clear()


def mark_digest_sent(component: str, window: str) -> bool:
    """Mark that a digest was sent for this window. Returns True if already sent."""
    key = (component, window)
    if key in _digest_sent:
        return True
    _digest_sent.add(key)
    return False
