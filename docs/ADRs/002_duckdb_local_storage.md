# ADR-002: DuckDB as local hot storage

**Date**: 2026-04-22
**Status**: Accepted
**Milestone**: M1

## Context

Need a local database for structured data (trades, wallets, alerts, markets) with support for analytical queries (aggregations, window functions, joins on millions of rows). Must be embedded (no server to manage) and Parquet-compatible.

## Options considered

- **PostgreSQL**: Full RDBMS, excellent for concurrent writes. Overkill for a solo bot — requires server management, backup complexity.
- **SQLite**: Embedded, widely used. Poor at analytical queries (no columnar storage, slow aggregations on large tables).
- **DuckDB**: OLAP-native embedded database. Columnar storage, vectorized execution, native Parquet read/write, single-file deployment.

## Decision

DuckDB. Single file at `data/pm.duckdb`, migrations via lightweight Python runner.

## Consequences

- Fast analytical queries (vectorized columnar engine)
- Parquet integration trivial (`read_parquet`, `COPY TO`)
- Single-file deployment — easy backup, easy rsync to VPS
- No concurrent write support (single writer at a time) — not a problem for a sequential bot
- Schema managed via versioned SQL migrations in `migrations/`
