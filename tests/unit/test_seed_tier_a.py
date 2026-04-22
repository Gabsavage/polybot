"""Tests for scripts/seed_tier_a.py."""

import sys
from pathlib import Path

import duckdb
import yaml

from polybot.db.migrations import apply_migrations

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
from seed_tier_a import seed  # noqa: E402

MOCK_WALLETS = [
    {
        "address": "0xaaaa",
        "alias": "TestWalletA1",
        "tier": "A",
        "confidence": "A1",
        "source": {"primary": "test_source"},
    },
    {
        "address": "0xbbbb",
        "alias": "TestWalletA2",
        "tier": "A",
        "confidence": "A2",
        "source": {"primary": "test_source"},
    },
    {
        "address": "0xcccc",
        "alias": "TestWalletA1bis",
        "tier": "A",
        "confidence": "A1",
        "source": {"primary": "leaderboard_dune"},
    },
]


def _setup_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(db_path), str(migrations_dir))
    return db_path


def test_seed_inserts_wallets(tmp_path: Path):
    db_path = _setup_db(tmp_path)
    result = seed(db_path, MOCK_WALLETS)

    assert result["total"] == 3

    con = duckdb.connect(str(db_path))
    rows = con.execute(
        "SELECT address, tier, active, source, tier_a_confidence, notes "
        "FROM tracked_wallets ORDER BY address"
    ).fetchall()
    con.close()

    assert len(rows) == 3
    # 0xaaaa — A1
    assert rows[0][0] == "0xaaaa"
    assert rows[0][1] == "A"
    assert rows[0][2] is True
    assert rows[0][3] == "test_source"
    assert float(rows[0][4]) == 0.90
    assert rows[0][5] == "TestWalletA1"
    # 0xbbbb — A2
    assert float(rows[1][4]) == 0.70


def test_seed_is_idempotent(tmp_path: Path):
    db_path = _setup_db(tmp_path)
    seed(db_path, MOCK_WALLETS)
    result = seed(db_path, MOCK_WALLETS)

    assert result["total"] == 3

    con = duckdb.connect(str(db_path))
    count = con.execute("SELECT COUNT(*) FROM tracked_wallets").fetchone()[0]
    con.close()
    assert count == 3


def test_seed_preserves_last_seen_timestamp(tmp_path: Path):
    db_path = _setup_db(tmp_path)
    seed(db_path, MOCK_WALLETS)

    # Simulate indexer having updated last_seen_timestamp
    con = duckdb.connect(str(db_path))
    con.execute(
        "UPDATE tracked_wallets SET last_seen_timestamp = 12345 WHERE address = '0xaaaa'"
    )
    con.close()

    # Re-seed
    seed(db_path, MOCK_WALLETS)

    con = duckdb.connect(str(db_path))
    ts = con.execute(
        "SELECT last_seen_timestamp FROM tracked_wallets WHERE address = '0xaaaa'"
    ).fetchone()[0]
    con.close()
    assert ts == 12345


def test_load_wallets_from_yaml(tmp_path: Path):
    yaml_path = tmp_path / "test_wallets.yaml"
    yaml_path.write_text(yaml.dump({"wallets": MOCK_WALLETS}))

    from seed_tier_a import load_wallets

    wallets = load_wallets(yaml_path)
    assert len(wallets) == 3
    assert wallets[0]["address"] == "0xaaaa"
