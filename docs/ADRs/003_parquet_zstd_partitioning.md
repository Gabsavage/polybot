# ADR-003: Parquet + zstd compression + hourly partitioning

**Date**: 2026-04-22
**Status**: Accepted
**Milestone**: M1

## Context

CLOB order book snapshots are the project's data moat — unique historical dataset. Need an efficient cold storage format on Cloudflare R2 with good compression, fast selective reads, and compatibility with DuckDB.

## Options considered

- **CSV**: Simple but uncompressed (~5x larger), no schema enforcement, slow to query.
- **JSON**: Human-readable but very verbose, no columnar optimization.
- **Parquet + snappy**: Columnar + fast compression. Good read speed, moderate compression ratio.
- **Parquet + zstd**: Columnar + best compression ratio. Slightly slower compression than snappy but 20-30% smaller files.

## Decision

Parquet with zstd compression. Partitioned by `snapshots/YYYY-MM-DD/HH.parquet` (one file per hourly snapshot).

## Consequences

- ~23 KB per snapshot (300 rows, 10 columns) — extremely compact
- Projection: 0.19 GB/year, R2 free tier (10 GB) holds 50+ years
- Path-based partitioning enables selective reads by date range
- DuckDB can query R2 Parquet directly via httpfs extension (future)
- Schema: condition_id, token_id, snapshot_ts, best_bid, best_ask, midpoint, spread, bid_depth_1pct, ask_depth_1pct, volume_1h
