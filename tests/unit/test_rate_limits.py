"""Tests for rate limits module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import duckdb
import pytest

from polybot.orchestrator.rate_limits import check_rate_limit, increment_counter


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("""
        CREATE TABLE rate_limit_counters (
            component VARCHAR,
            "window" VARCHAR,
            count INTEGER DEFAULT 0,
            window_start TIMESTAMP,
            PRIMARY KEY (component, "window")
        )
    """)
    con.close()
    return path


class TestRateLimitUnder:
    def test_first_call_is_under_limit(self, db_path):
        assert check_rate_limit(db_path, "c1") is True

    def test_five_calls_under_hourly_ten(self, db_path):
        for _ in range(5):
            increment_counter(db_path, "c1")
        assert check_rate_limit(db_path, "c1") is True


class TestRateLimitExceeded:
    def test_hourly_limit_exceeded(self, db_path):
        for _ in range(10):
            increment_counter(db_path, "c1")
        assert check_rate_limit(db_path, "c1") is False

    def test_daily_limit_exceeded(self, db_path):
        # c2 has daily limit of 5
        for _ in range(5):
            increment_counter(db_path, "c2")
        assert check_rate_limit(db_path, "c2") is False


class TestRateLimitWindowReset:
    def test_hourly_window_resets_after_one_hour(self, db_path):
        for _ in range(10):
            increment_counter(db_path, "c1")
        assert check_rate_limit(db_path, "c1") is False

        # Move window_start back 2 hours so it looks stale
        con = duckdb.connect(db_path)
        con.execute(
            "UPDATE rate_limit_counters SET window_start = window_start - INTERVAL 2 HOUR "
            "WHERE component = 'c1' AND \"window\" = 'hourly'"
        )
        con.close()

        assert check_rate_limit(db_path, "c1") is True

    def test_daily_window_resets_after_24h(self, db_path):
        for _ in range(5):
            increment_counter(db_path, "c2")
        assert check_rate_limit(db_path, "c2") is False

        con = duckdb.connect(db_path)
        con.execute(
            "UPDATE rate_limit_counters SET window_start = window_start - INTERVAL 25 HOUR "
            "WHERE component = 'c2' AND \"window\" = 'daily'"
        )
        con.close()

        assert check_rate_limit(db_path, "c2") is True
