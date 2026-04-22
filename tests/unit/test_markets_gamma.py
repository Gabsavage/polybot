"""Tests for indexer_markets_gamma."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import httpx
import pytest

from polybot.db.migrations import apply_migrations
from polybot.indexers.markets_gamma import (
    fetch_all_markets,
    map_market,
    run,
    update_indexer_state,
    upsert_markets,
)

_FAKE_REQUEST = httpx.Request("GET", "https://gamma-api.polymarket.com/markets")


def _make_market(condition_id: str, **overrides) -> dict:
    """Build a minimal Gamma-style market dict."""
    base = {
        "conditionId": condition_id,
        "questionID": f"qid_{condition_id}",
        "question": f"Will {condition_id} happen?",
        "description": "Some description",
        "category": "politics",
        "outcomes": '["Yes", "No"]',
        "negRisk": False,
        "resolutionSource": "",
        "endDate": "2026-12-31T00:00:00Z",
        "startDate": "2026-01-01T00:00:00Z",
        "createdAt": "2026-01-01T00:00:00Z",
        "closedTime": None,
        "volume": "1000.50",
        "liquidity": "500.25",
        "volume24hr": 100.5,
        "active": True,
        "closed": False,
        "slug": f"slug-{condition_id}",
        "events": [{"slug": f"event-{condition_id}"}],
    }
    base.update(overrides)
    return base


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


class TestPagination:
    def test_fetches_multiple_pages(self):
        page1 = [_make_market(f"c{i}") for i in range(500)]
        page2 = [_make_market(f"c{i}") for i in range(500, 1000)]
        page3 = [_make_market(f"c{i}") for i in range(1000, 1200)]

        responses = [
            httpx.Response(200, json=page1, request=_FAKE_REQUEST),
            httpx.Response(200, json=page2, request=_FAKE_REQUEST),
            httpx.Response(200, json=page3, request=_FAKE_REQUEST),
        ]
        call_count = 0

        def mock_get(url, **kwargs):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        with (
            patch("polybot.indexers.markets_gamma.httpx.Client") as mock_client_cls,
            patch("polybot.indexers.markets_gamma.time.sleep"),
        ):
            mock_client = MagicMock()
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            markets = fetch_all_markets()
            assert len(markets) == 1200
            assert mock_client.get.call_count == 3


class TestUpsert:
    def test_insert_and_update(self, db_path: str):
        markets = [_make_market(f"c{i}") for i in range(5)]
        count = upsert_markets(db_path, markets)
        assert count == 5

        # Update 3 existing + add 2 new
        updated = [_make_market(f"c{i}", volume="9999.0") for i in range(3)]
        new = [_make_market(f"c{i}") for i in range(5, 7)]
        count = upsert_markets(db_path, updated + new)
        assert count == 5

        con = duckdb.connect(db_path, read_only=True)
        total = con.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
        updated_vol = con.execute(
            "SELECT volume_cumulative_usd FROM markets WHERE condition_id = 'c0'"
        ).fetchone()[0]
        con.close()

        assert total == 7
        assert float(updated_vol) == 9999.0

    def test_nullable_fields(self, db_path: str):
        market = _make_market(
            "nullable_test",
            eventSlug=None,
            closedTime=None,
            category=None,
            startDate=None,
            events=[],
        )
        count = upsert_markets(db_path, [market])
        assert count == 1

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT event_slug, closed_at, category, start_date "
            "FROM markets WHERE condition_id = 'nullable_test'"
        ).fetchone()
        con.close()

        assert row[0] is None  # event_slug
        assert row[1] is None  # closed_at
        assert row[2] is None  # category
        assert row[3] is None  # start_date

    def test_skips_markets_without_condition_id(self, db_path: str):
        markets = [
            _make_market("valid"),
            {"question": "no conditionId"},
        ]
        count = upsert_markets(db_path, markets)
        assert count == 1


class TestBackoff429:
    def test_retries_on_429_then_succeeds(self):
        page = [_make_market("c1")]
        responses = [
            httpx.Response(429, request=_FAKE_REQUEST),
            httpx.Response(429, request=_FAKE_REQUEST),
            httpx.Response(200, json=page, request=_FAKE_REQUEST),
        ]
        call_count = 0

        def mock_get(url, **kwargs):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        with (
            patch("polybot.indexers.markets_gamma.httpx.Client") as mock_client_cls,
            patch("polybot.indexers.markets_gamma.time.sleep") as mock_sleep,
        ):
            mock_client = MagicMock()
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            markets = fetch_all_markets()
            assert len(markets) == 1
            # 2 backoff sleeps (429s) + 0 pagination sleep (last page < 500)
            assert mock_sleep.call_count == 2


class TestIndexerState:
    def test_updates_state_on_success(self, db_path: str):
        update_indexer_state(db_path, "success", 100, 5000)

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT indexer_name, last_run_status, ingested_count, last_run_duration_ms "
            "FROM indexer_state WHERE indexer_name = 'markets_gamma'"
        ).fetchone()
        con.close()

        assert row[0] == "markets_gamma"
        assert row[1] == "success"
        assert row[2] == 100
        assert row[3] == 5000

    def test_full_run_updates_state(self, db_path: str):
        page = [_make_market(f"c{i}") for i in range(3)]

        with (
            patch("polybot.indexers.markets_gamma.httpx.Client") as mock_client_cls,
            patch("polybot.indexers.markets_gamma.time.sleep"),
        ):
            mock_client = MagicMock()
            mock_client.get.return_value = httpx.Response(200, json=page, request=_FAKE_REQUEST)
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            count = run(db_path)
            assert count == 3

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute(
            "SELECT last_run_status, ingested_count FROM indexer_state "
            "WHERE indexer_name = 'markets_gamma'"
        ).fetchone()
        con.close()

        assert row[0] == "success"
        assert row[1] == 3


class TestMapping:
    def test_map_market_parses_all_fields(self):
        m = _make_market("test_map", volume24hr=42.5, closedTime="2026-06-01T00:00:00Z")
        row = map_market(m)
        assert row[0] == "test_map"  # condition_id
        assert row[1] == "qid_test_map"  # question_id
        assert row[6] == ["Yes", "No"]  # outcomes parsed from JSON string
        assert row[19] == 42.5  # volume_24h
        assert row[11] is not None  # closed_at parsed

    def test_outcomes_as_list(self):
        m = _make_market("list_out", outcomes=["Yes", "No"])
        row = map_market(m)
        assert row[6] == ["Yes", "No"]
