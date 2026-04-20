#!/usr/bin/env python3
"""Initialize DuckDB with all pending migrations."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from polybot.db.migrations import apply_migrations


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Apply DuckDB migrations")
    parser.add_argument("--db", default="data/pm.duckdb", help="Path to DuckDB file")
    parser.add_argument("--migrations", default="migrations", help="Path to migrations directory")
    args = parser.parse_args()

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    applied = apply_migrations(args.db, args.migrations)

    if applied:
        print(f"Applied {len(applied)} migration(s): {', '.join(applied)}")
    else:
        print("No new migrations to apply.")


if __name__ == "__main__":
    main()
