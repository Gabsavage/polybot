"""Lightweight migration runner for DuckDB — no external deps."""

from pathlib import Path

import duckdb


def apply_migrations(db_path: str, migrations_dir: str) -> list[str]:
    """Apply pending SQL migrations in filename order. Returns list of newly applied filenames."""
    con = duckdb.connect(db_path)

    con.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            filename VARCHAR PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    applied = {
        row[0] for row in con.execute("SELECT filename FROM _migrations").fetchall()
    }

    migrations_path = Path(migrations_dir)
    sql_files = sorted(migrations_path.glob("*.sql"))
    newly_applied = []

    for sql_file in sql_files:
        if sql_file.name in applied:
            continue
        sql = sql_file.read_text()
        con.execute(sql)
        con.execute("INSERT INTO _migrations (filename) VALUES (?)", [sql_file.name])
        newly_applied.append(sql_file.name)

    con.close()
    return newly_applied
