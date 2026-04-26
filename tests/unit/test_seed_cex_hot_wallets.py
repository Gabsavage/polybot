from pathlib import Path

import duckdb
import pytest
import yaml

from polybot.db.migrations import apply_migrations


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(path), str(migrations_dir))
    return str(path)


MOCK_YAML = {
    "version": 1,
    "last_updated": "2026-04-26",
    "exchanges": {
        "binance": {
            "name": "Binance",
            "hot_wallets": [
                {
                    "address": "0xaaa1",
                    "label": "Binance HW 1",
                    "verified": True,
                    "source": "polygonscan",
                },
                {
                    "address": "0xaaa2",
                    "label": "Binance HW 2",
                    "verified": True,
                    "source": "arkham",
                },
            ],
        },
        "coinbase": {
            "name": "Coinbase",
            "hot_wallets": [
                {
                    "address": "0xbbb1",
                    "label": "Coinbase HW",
                    "verified": True,
                    "source": "polygonscan",
                },
            ],
        },
        "okx": {
            "name": "OKX",
            "hot_wallets": [
                {
                    "address": "0xCCC1",
                    "label": "OKX HW 1",
                    "verified": True,
                    "source": "arkham",
                },
                {
                    "address": "0xCCC2",
                    "label": "OKX HW 2",
                    "verified": False,
                    "source": "dune",
                },
            ],
        },
    },
}


@pytest.fixture()
def yaml_path(tmp_path: Path) -> Path:
    path = tmp_path / "cex_hot_wallets.yaml"
    with open(path, "w") as f:
        yaml.dump(MOCK_YAML, f)
    return path


def test_load_wallets(yaml_path: Path, db_path: str):
    from scripts.seed_cex_hot_wallets import load_wallets, seed

    wallets = load_wallets(yaml_path)
    result = seed(db_path, wallets)

    assert result["count"] == 5

    con = duckdb.connect(db_path)
    rows = con.execute("SELECT COUNT(*) FROM cex_hot_wallets").fetchone()[0]
    con.close()
    assert rows == 5


def test_idempotent(yaml_path: Path, db_path: str):
    from scripts.seed_cex_hot_wallets import load_wallets, seed

    wallets = load_wallets(yaml_path)
    seed(db_path, wallets)
    seed(db_path, wallets)

    con = duckdb.connect(db_path)
    rows = con.execute("SELECT COUNT(*) FROM cex_hot_wallets").fetchone()[0]
    con.close()
    assert rows == 5


def test_lowercase_normalization(yaml_path: Path, db_path: str):
    from scripts.seed_cex_hot_wallets import load_wallets, seed

    wallets = load_wallets(yaml_path)
    seed(db_path, wallets)

    con = duckdb.connect(db_path)
    addresses = [row[0] for row in con.execute("SELECT address FROM cex_hot_wallets").fetchall()]
    con.close()

    for addr in addresses:
        assert addr == addr.lower(), f"Address not lowercase: {addr}"
    assert "0xccc1" in addresses
    assert "0xccc2" in addresses


def test_yaml_structure():
    yaml_path = Path(__file__).parents[2] / "config" / "cex_hot_wallets.yaml"
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    assert "exchanges" in data
    total = 0
    for _key, exchange in data["exchanges"].items():
        assert "name" in exchange
        assert "hot_wallets" in exchange
        for wallet in exchange["hot_wallets"]:
            assert "address" in wallet
            assert wallet["address"].startswith("0x")
            assert wallet["address"] == wallet["address"].lower(), (
                f"Address not lowercase in YAML: {wallet['address']}"
            )
            total += 1
    assert total >= 20, f"Expected >= 20 wallets, got {total}"
