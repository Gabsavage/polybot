"""Tests for clustering_victor indexer."""

import hashlib
from pathlib import Path

import duckdb
import pytest

from polybot.db.migrations import apply_migrations


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


def _seed_funding(db_path: str, wallets: list[tuple[str, str]]):
    """Insert (wallet_address, funded_by) rows into cex_funding_map."""
    con = duckdb.connect(db_path)
    for wallet, funded_by in wallets:
        con.execute(
            """INSERT INTO cex_funding_map (wallet_address, funded_by, funded_by_hop2,
               cex_source, deposit_address, confidence, method)
               VALUES (?, ?, NULL, NULL, NULL, 0.0, NULL)
               ON CONFLICT DO NOTHING""",
            [wallet, funded_by],
        )
    con.close()


def _seed_hot_wallet(db_path: str, address: str, exchange: str = "Binance"):
    """Insert a hot wallet into cex_hot_wallets."""
    con = duckdb.connect(db_path)
    con.execute(
        "INSERT INTO cex_hot_wallets (address, exchange_name) VALUES (?, ?)",
        [address, exchange],
    )
    con.close()


class TestBasicClustering:
    def test_basic_clustering(self, db_path):
        """5 wallets, 3 share funded_by -> 1 cluster size 3."""
        from polybot.indexers.clustering_victor import run

        _seed_funding(db_path, [
            ("0xaaa1", "0xfunder_a"),
            ("0xaaa2", "0xfunder_a"),
            ("0xaaa3", "0xfunder_a"),
            ("0xbbb1", "0xfunder_b"),
            ("0xccc1", "0xfunder_c"),
        ])
        count = run(db_path)
        assert count == 1

        con = duckdb.connect(db_path, read_only=True)
        clusters = con.execute("SELECT * FROM wallet_clusters").fetchall()
        assert len(clusters) == 1
        assert clusters[0][3] == 3  # size column

        members = con.execute(
            "SELECT wallet_address FROM wallet_cluster_members ORDER BY wallet_address"
        ).fetchall()
        assert [r[0] for r in members] == ["0xaaa1", "0xaaa2", "0xaaa3"]
        con.close()

    def test_singleton_excluded(self, db_path):
        """1 wallet alone -> no cluster."""
        from polybot.indexers.clustering_victor import run

        _seed_funding(db_path, [("0xaaa1", "0xfunder_solo")])
        count = run(db_path)
        assert count == 0

    def test_large_cluster_skipped(self, db_path):
        """60 wallets same funded_by -> warning logged, no cluster."""
        from polybot.indexers.clustering_victor import run

        wallets = [(f"0xwallet_{i:03d}", "0xfunder_big") for i in range(60)]
        _seed_funding(db_path, wallets)
        count = run(db_path)
        assert count == 0

        con = duckdb.connect(db_path, read_only=True)
        clusters = con.execute("SELECT * FROM wallet_clusters").fetchall()
        assert len(clusters) == 0
        con.close()

    def test_hot_wallet_excluded(self, db_path):
        """funded_by = known hot wallet -> no cluster."""
        from polybot.indexers.clustering_victor import run

        hot = "0xhot_wallet_binance"
        _seed_hot_wallet(db_path, hot)
        _seed_funding(db_path, [
            ("0xaaa1", hot),
            ("0xaaa2", hot),
            ("0xaaa3", hot),
        ])
        count = run(db_path)
        assert count == 0

    def test_idempotent(self, db_path):
        """run() twice -> same cluster count, no duplicates."""
        from polybot.indexers.clustering_victor import run

        _seed_funding(db_path, [
            ("0xaaa1", "0xfunder_a"),
            ("0xaaa2", "0xfunder_a"),
        ])
        run(db_path)
        run(db_path)

        con = duckdb.connect(db_path, read_only=True)
        clusters = con.execute("SELECT * FROM wallet_clusters").fetchall()
        assert len(clusters) == 1
        members = con.execute("SELECT * FROM wallet_cluster_members").fetchall()
        assert len(members) == 2
        con.close()

    def test_cluster_id_deterministic(self, db_path):
        """Same funded_by always gives same cluster_id."""
        from polybot.indexers.clustering_victor import run

        funded_by = "0xfunder_deterministic"
        expected_id = hashlib.sha256(funded_by.encode()).hexdigest()[:12]

        _seed_funding(db_path, [
            ("0xaaa1", funded_by),
            ("0xaaa2", funded_by),
        ])
        run(db_path)

        con = duckdb.connect(db_path, read_only=True)
        row = con.execute("SELECT cluster_id FROM wallet_clusters").fetchone()
        assert row[0] == expected_id
        con.close()
