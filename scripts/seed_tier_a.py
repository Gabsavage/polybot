#!/usr/bin/env python3
"""Seed tracked_wallets table with Tier A wallets from YAML config."""

from pathlib import Path

import duckdb
import yaml

CONFIDENCE_MAP = {"A1": 0.90, "A2": 0.70}

PROJECT_ROOT = Path(__file__).parents[1]
DB_PATH = PROJECT_ROOT / "data" / "pm.duckdb"
YAML_PATH = PROJECT_ROOT / "config" / "tracked_wallets_seed.yaml"

UPSERT_SQL = """
INSERT INTO tracked_wallets (
    address, tier, active, source, added_at, last_reviewed_at,
    honeypot_flag, honeypot_score, tier_a_confidence, notes,
    last_seen_timestamp
) VALUES (?, ?, ?, ?, NOW(), NOW(), ?, ?, ?, ?, 0)
ON CONFLICT (address) DO UPDATE SET
    tier = EXCLUDED.tier,
    active = EXCLUDED.active,
    source = EXCLUDED.source,
    last_reviewed_at = NOW(),
    honeypot_flag = EXCLUDED.honeypot_flag,
    honeypot_score = EXCLUDED.honeypot_score,
    tier_a_confidence = EXCLUDED.tier_a_confidence,
    notes = EXCLUDED.notes
"""


def load_wallets(yaml_path: Path) -> list[dict]:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return data["wallets"]


def seed(db_path: Path, wallets: list[dict]) -> dict[str, int]:
    con = duckdb.connect(str(db_path))
    counts: dict[str, int] = {}
    for w in wallets:
        confidence_key = w["confidence"]
        tier_a_confidence = CONFIDENCE_MAP.get(confidence_key, 0.50)
        notes = w.get("alias", "")
        source = w["source"]["primary"]

        con.execute(UPSERT_SQL, [
            w["address"],
            w["tier"],
            True,
            source,
            False,
            0.0,
            tier_a_confidence,
            notes,
        ])
        counts[confidence_key] = counts.get(confidence_key, 0) + 1

    total = con.execute(
        "SELECT COUNT(*) FROM tracked_wallets WHERE tier='A'"
    ).fetchone()[0]
    con.close()
    return {"counts": counts, "total": total}


def main():
    wallets = load_wallets(YAML_PATH)
    result = seed(DB_PATH, wallets)
    counts = result["counts"]
    parts = " + ".join(f"{v} {k}" for k, v in sorted(counts.items()))
    print(f"Seeded {sum(counts.values())} wallets ({parts})")
    print(f"Verification: SELECT COUNT(*) FROM tracked_wallets WHERE tier='A' → {result['total']}")


if __name__ == "__main__":
    main()
