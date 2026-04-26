"""Polybot Dashboard API — read-only access to DuckDB monitoring data."""

from typing import Annotated

import duckdb
import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from polybot.config import Settings

logger = structlog.get_logger()

settings = Settings()

app = FastAPI(title="Polybot Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    con = duckdb.connect(str(settings.DUCKDB_PATH), read_only=True)
    try:
        yield con
    finally:
        con.close()


DB = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]


@app.get("/api/status")
def get_status(con: DB):
    kill_switches = con.execute(
        "SELECT target, enabled, reason, toggled_at "
        "FROM kill_switches WHERE enabled = TRUE"
    ).fetchall()

    rate_limits = con.execute(
        'SELECT component, "window", count, window_start FROM rate_limit_counters'
    ).fetchall()

    indexers = con.execute(
        "SELECT indexer_name, last_run_status, last_synced_at, "
        "last_run_duration_ms, ingested_count "
        "FROM indexer_state ORDER BY indexer_name"
    ).fetchall()

    return {
        "kill_switches": [
            {
                "target": r[0],
                "enabled": r[1],
                "reason": r[2],
                "toggled_at": str(r[3]) if r[3] else None,
            }
            for r in kill_switches
        ],
        "rate_limits": [
            {
                "component": r[0],
                "window": r[1],
                "count": r[2],
                "window_start": str(r[3]) if r[3] else None,
            }
            for r in rate_limits
        ],
        "indexers": [
            {
                "name": r[0],
                "status": r[1],
                "last_synced_at": str(r[2]) if r[2] else None,
                "duration_ms": r[3],
                "ingested_count": r[4],
            }
            for r in indexers
        ],
    }
