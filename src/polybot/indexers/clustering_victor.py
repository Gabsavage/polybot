"""Build wallet clusters from shared_funded_by signal."""

import hashlib
import time

import duckdb
import structlog

from polybot.db.connection import db_write_with_retry

logger = structlog.get_logger()

MAX_CLUSTER_SIZE = 50


def run(db_path: str) -> int:
    """Group wallets by funded_by, build clusters of size 2-50."""
    start_time = time.monotonic()

    con = duckdb.connect(db_path)

    rows = con.execute(
        """
        SELECT cfm.funded_by, COUNT(*) AS cnt,
               (SELECT cex_source FROM cex_funding_map cfm2
                WHERE cfm2.funded_by = cfm.funded_by AND cfm2.cex_source IS NOT NULL
                LIMIT 1) AS cex_source
        FROM cex_funding_map cfm
        WHERE cfm.funded_by IS NOT NULL
          AND cfm.funded_by NOT IN (SELECT address FROM cex_hot_wallets)
        GROUP BY cfm.funded_by
        HAVING COUNT(*) >= 2
        """
    ).fetchall()

    clusters_created = 0

    for funded_by, size, cex_source in rows:
        if size > MAX_CLUSTER_SIZE:
            logger.warning(
                "clustering_oversized_group",
                funded_by=funded_by[:16],
                size=size,
            )
            continue

        cluster_id = hashlib.sha256(funded_by.encode()).hexdigest()[:12]

        con.execute(
            """
            INSERT INTO wallet_clusters (cluster_id, funded_by, cex_source, size, updated_at)
            VALUES (?, ?, ?, ?, NOW())
            ON CONFLICT (cluster_id) DO UPDATE SET
                size = EXCLUDED.size,
                cex_source = EXCLUDED.cex_source,
                updated_at = NOW()
            """,
            [cluster_id, funded_by, cex_source, size],
        )

        members = con.execute(
            "SELECT wallet_address FROM cex_funding_map WHERE funded_by = ?",
            [funded_by],
        ).fetchall()

        for (wallet,) in members:
            con.execute(
                """
                INSERT INTO wallet_cluster_members (wallet_address, cluster_id, funded_by)
                VALUES (?, ?, ?)
                ON CONFLICT (wallet_address) DO UPDATE SET
                    cluster_id = EXCLUDED.cluster_id
                """,
                [wallet, cluster_id, funded_by],
            )

        clusters_created += 1

    con.close()

    duration_ms = int((time.monotonic() - start_time) * 1000)
    update_indexer_state(db_path, "success", clusters_created, duration_ms)
    logger.info("clustering_victor_complete", clusters=clusters_created, duration_ms=duration_ms)
    return clusters_created


def update_indexer_state(
    db_path: str,
    status: str,
    count: int,
    duration_ms: int,
    error: str | None = None,
) -> None:
    """Update indexer_state for 'clustering_victor'."""

    def _do(con):
        con.execute(
            """
            INSERT OR REPLACE INTO indexer_state (
                indexer_name, last_synced_at, last_run_status,
                last_run_duration_ms, ingested_count, last_error, updated_at
            ) VALUES ('clustering_victor', NOW(), ?, ?, ?, ?, NOW())
            """,
            [status, duration_ms, count, error],
        )

    db_write_with_retry(db_path, _do)


def main():
    from polybot.config import Settings
    from polybot.logging import setup_logging

    settings = Settings()
    setup_logging(settings.LOG_LEVEL, settings.LOG_DIR)
    logger.info("clustering_victor_starting")
    count = run(db_path=str(settings.DUCKDB_PATH))
    print(f"Clustering Victor complete: {count} clusters")


if __name__ == "__main__":
    main()
