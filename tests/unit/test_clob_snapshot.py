from datetime import UTC, datetime

from polybot.indexers.clob_snapshot import (
    build_snapshot_row,
    filter_top_markets,
    parse_order_book,
)


def test_filter_top_markets():
    """Filter markets by volume threshold and return top N."""
    markets = [
        {
            "conditionId": "a",
            "volume24hr": 100_000,
            "clobTokenIds": '["tok_a_yes","tok_a_no"]',
            "question": "Q1",
        },
        {
            "conditionId": "b",
            "volume24hr": 30_000,
            "clobTokenIds": '["tok_b_yes","tok_b_no"]',
            "question": "Q2",
        },
        {
            "conditionId": "c",
            "volume24hr": 60_000,
            "clobTokenIds": '["tok_c_yes","tok_c_no"]',
            "question": "Q3",
        },
    ]
    result = filter_top_markets(markets, top_n=2, min_volume=50_000)
    assert len(result) == 2
    assert result[0]["conditionId"] == "a"
    assert result[1]["conditionId"] == "c"


def test_filter_top_markets_none_volume():
    """Markets with None volume should be excluded."""
    markets = [
        {"conditionId": "a", "volume24hr": None},
        {"conditionId": "b", "volume24hr": 80_000},
    ]
    result = filter_top_markets(markets, top_n=10, min_volume=50_000)
    assert len(result) == 1
    assert result[0]["conditionId"] == "b"


def test_parse_order_book_basic():
    """Parse CLOB /book response into best bid/ask/depth."""
    book = {
        "bids": [
            {"price": "0.55", "size": "1000"},
            {"price": "0.54", "size": "2000"},
            {"price": "0.53", "size": "500"},
        ],
        "asks": [
            {"price": "0.57", "size": "800"},
            {"price": "0.58", "size": "1500"},
            {"price": "0.60", "size": "300"},
        ],
    }
    result = parse_order_book(book)
    assert result["best_bid"] == 0.55
    assert result["best_ask"] == 0.57
    assert abs(result["midpoint"] - 0.56) < 0.001
    assert abs(result["spread"] - 0.02) < 0.001


def test_parse_order_book_empty():
    """Empty book returns None values."""
    result = parse_order_book({"bids": [], "asks": []})
    assert result["best_bid"] is None
    assert result["best_ask"] is None
    assert result["midpoint"] is None
    assert result["spread"] is None


def test_build_snapshot_row():
    """Build a complete row for the Parquet output."""
    book_data = {
        "best_bid": 0.55,
        "best_ask": 0.57,
        "midpoint": 0.56,
        "spread": 0.02,
        "bid_depth_1pct": 3000.0,
        "ask_depth_1pct": 2300.0,
    }
    ts = datetime(2026, 4, 21, 14, 0, 0, tzinfo=UTC)
    row = build_snapshot_row("cond_1", "tok_yes", ts, book_data, volume_1h=15000.0)
    assert row["condition_id"] == "cond_1"
    assert row["token_id"] == "tok_yes"
    assert row["snapshot_ts"] == ts
    assert row["best_bid"] == 0.55
    assert row["volume_1h"] == 15000.0
