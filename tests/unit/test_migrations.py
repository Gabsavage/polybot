from pathlib import Path

import duckdb

from polybot.db.migrations import apply_migrations

M1_TABLES = [
    "markets",
    "trades",
    "wallets",
    "tracked_wallets",
    "alerts",
    "kill_switches",
    "audit_log",
    "rate_limit_counters",
    "bankroll_state",
    "resolution_risk_cache",
    "snapshot_universe",
]

M2_TABLES = M1_TABLES + ["indexer_state"]

M9_TABLES = M2_TABLES + ["cex_hot_wallets", "cex_funding_map"]


def test_apply_migrations_creates_all_tables(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(db_path), str(migrations_dir))

    con = duckdb.connect(str(db_path))
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    con.close()

    for table in M9_TABLES:
        assert table in tables, f"Missing table: {table}"


def test_apply_migrations_idempotent(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(db_path), str(migrations_dir))
    apply_migrations(str(db_path), str(migrations_dir))

    con = duckdb.connect(str(db_path))
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    con.close()

    for table in M9_TABLES:
        assert table in tables


def test_migrations_tracking(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    migrations_dir = Path(__file__).parents[2] / "migrations"
    apply_migrations(str(db_path), str(migrations_dir))

    con = duckdb.connect(str(db_path))
    applied = con.execute("SELECT filename FROM _migrations ORDER BY applied_at").fetchall()
    con.close()

    assert len(applied) == 8
    assert applied[0][0] == "001_initial_schema.sql"
    assert applied[1][0] == "002_m2_schema_alignment.sql"
    assert applied[2][0] == "003_m3_enrichment_tables.sql"
    assert applied[3][0] == "004_trades_all_composite_pk.sql"
    assert applied[4][0] == "005_alerts_bankroll_v2.sql"
    assert applied[5][0] == "006_m6_c2_alert_outcomes.sql"
    assert applied[6][0] == "007_m8a_orchestration_tables.sql"
    assert applied[7][0] == "008_m9_cex_funding.sql"
