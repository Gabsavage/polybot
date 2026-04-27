"""Tests for daemon scheduling helpers (drift-resistant sleep + loop lag monitor)."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import structlog

from polybot.daemon import _monitor_loop_lag, _wait_until


class TestWaitUntil:
    @pytest.mark.asyncio
    async def test_returns_immediately_when_target_in_past(self):
        loop = asyncio.get_event_loop()
        target = datetime.now(timezone.utc) - timedelta(seconds=10)
        t0 = loop.time()
        await _wait_until(target)
        elapsed = loop.time() - t0
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_fires_within_chunk_of_target(self):
        # Target 0.4s away, chunks of 0.1s — should land within ~0.1s of target.
        loop = asyncio.get_event_loop()
        target = datetime.now(timezone.utc) + timedelta(seconds=0.4)
        t0 = loop.time()
        await _wait_until(target, chunk_s=0.1)
        elapsed = loop.time() - t0
        assert 0.35 <= elapsed <= 0.55

    @pytest.mark.asyncio
    async def test_resilient_to_individual_sleep_drift(self):
        # Even if one chunk gets delayed, next iteration's wall-clock check corrects.
        # Simulate by patching asyncio.sleep to add a one-time extra delay.
        from polybot import daemon as daemon_mod

        target = datetime.now(timezone.utc) + timedelta(seconds=0.5)
        real_sleep = asyncio.sleep
        calls = {"n": 0}

        async def laggy_sleep(s):
            calls["n"] += 1
            # First chunk gets a 0.2s "starvation" surcharge, later ones are normal.
            extra = 0.2 if calls["n"] == 1 else 0.0
            await real_sleep(s + extra)

        loop = asyncio.get_event_loop()
        t0 = loop.time()
        # Patch the asyncio.sleep used inside _wait_until
        original = daemon_mod.asyncio.sleep
        daemon_mod.asyncio.sleep = laggy_sleep
        try:
            await _wait_until(target, chunk_s=0.1)
        finally:
            daemon_mod.asyncio.sleep = original
        elapsed = loop.time() - t0
        # First chunk drift was 0.2s, so we miss target by at most 0.2s + one chunk.
        assert elapsed <= 0.5 + 0.3


class TestMonitorLoopLag:
    @pytest.mark.asyncio
    async def test_logs_when_loop_blocked_beyond_threshold(self, caplog):
        # Run the monitor concurrently with a sync block on the loop.
        events: list[dict] = []

        def capture(_logger, _name, event_dict):
            events.append(dict(event_dict))
            return ""

        structlog.configure(processors=[capture])

        async def block_briefly():
            # Sleep first so the monitor's sleep(1.0) starts; then block for 2.5s.
            await asyncio.sleep(0.05)
            import time as time_mod

            time_mod.sleep(2.5)

        monitor_task = asyncio.create_task(
            _monitor_loop_lag(threshold_s=1.0, interval_s=1.0)
        )
        try:
            await block_briefly()
            await asyncio.sleep(0.3)
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        lag_events = [e for e in events if e.get("event") == "event_loop_lag"]
        assert lag_events, f"expected event_loop_lag, got {events}"
        assert lag_events[0]["lag_s"] >= 1.0

    @pytest.mark.asyncio
    async def test_silent_when_loop_healthy(self):
        events: list[dict] = []

        def capture(_logger, _name, event_dict):
            events.append(dict(event_dict))
            return ""

        structlog.configure(processors=[capture])

        monitor_task = asyncio.create_task(
            _monitor_loop_lag(threshold_s=1.0, interval_s=1.0)
        )
        try:
            await asyncio.sleep(1.5)
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        lag_events = [e for e in events if e.get("event") == "event_loop_lag"]
        assert not lag_events
