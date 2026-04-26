#!/usr/bin/env python3
"""Seed cex_hot_wallets table from YAML config."""

from pathlib import Path

import duckdb
import yaml

PROJECT_ROOT = Path(__file__).parents[1]
DB_PATH = PROJECT_ROOT / "data" / "pm.duckdb"
YAML_PATH = PROJECT_ROOT / "config" / "cex_hot_wallets.yaml"

UPSERT_SQL = """
INSERT INTO cex_hot_wallets (address, exchange_name, label, verified, source)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (address) DO UPDATE SET
    exchange_name = EXCLUDED.exchange_name,
    label = EXCLUDED.label,
    verified = EXCLUDED.verified,
    source = EXCLUDED.source
"""


def load_wallets(yaml_path: Path) -> list[dict]:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    wallets = []
    for _key, exchange in data["exchanges"].items():
        for wallet in exchange["hot_wallets"]:
            wallets.append(
                {
                    "address": wallet["address"].lower(),
                    "exchange_name": exchange["name"],
                    "label": wallet.get("label"),
                    "verified": wallet.get("verified", True),
                    "source": wallet.get("source"),
                }
            )
    return wallets


def seed(db_path: str | Path, wallets: list[dict]) -> dict:
    con = duckdb.connect(str(db_path))
    for w in wallets:
        con.execute(
            UPSERT_SQL,
            [
                w["address"],
                w["exchange_name"],
                w["label"],
                w["verified"],
                w["source"],
            ],
        )
    con.close()
    return {"count": len(wallets)}


def main():
    wallets = load_wallets(YAML_PATH)
    result = seed(DB_PATH, wallets)
    print(f"Loaded {result['count']} CEX hot wallet addresses")


if __name__ == "__main__":
    main()
