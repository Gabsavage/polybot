# ADR-013: Direct DuckDB writes in M2 (vs staging Parquet pattern)

**Date**: 2026-04-22
**Status**: Accepted
**Milestone**: M2

## Context

A_architecture_technique.md §1.4 describes a staging pattern: indexers write to Parquet staging files, a compactor merges them into DuckDB every 5 min. This handles DuckDB's single-writer constraint under concurrent multi-process workloads.

In M2, two indexers run: indexer_markets_gamma (systemd timer, 15 min) and indexer_trades_dataapi (daemon, 60s loop). Both are single-process and rarely overlap in time.

## Options considered

- **Staging Parquet + compactor**: Designed for concurrent writes. Adds a compactor process, staging directory management, and merge logic. Overkill when write collisions are rare (<10%).
- **Direct DuckDB writes**: Each indexer opens a DuckDB connection and writes directly. DuckDB handles collisions via internal lock (blocks briefly, no crash). Simpler code, fewer moving parts.

## Decision

Direct DuckDB writes in M2. No staging Parquet, no compactor process.

## Consequences

- Simpler architecture: no staging dir, no compactor timer, no merge logic
- DuckDB lock may cause brief blocking if both indexers write simultaneously (~10% chance per cycle) — acceptable latency impact (<1s)
- If M3+ adds more concurrent writers and blocking becomes measurable, revisit with staging pattern
- Consistent with solo-builder principle: minimize operational overhead
