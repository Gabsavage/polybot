# ADR-006: volume_1h left null in M1, populated in M3

**Date**: 2026-04-22
**Status**: Accepted
**Milestone**: M1

## Context

The CLOB snapshot Parquet schema includes a `volume_1h` column, but the CLOB `/book` endpoint only returns the order book state (bids/asks), not volume data.

## Options considered

- **Separate /prices-history call per market**: Doubles API calls per snapshot cycle (~300 extra calls/hour). Significant latency and rate limit risk.
- **Compute from trades indexer (M3)**: Aggregate hourly volume from the trades table once `indexer_trades_dataapi` is running. Consistent and accurate.
- **Leave null in M1, populate in M3**: Keep schema stable, defer population to when the data source exists.

## Decision

Leave `volume_1h` as null in M1. Will be populated in M3 when the trades indexer provides hourly trade aggregations.

## Consequences

- Schema is stable from M1 — no migration needed when volume_1h gets populated
- M1 snapshots are complete for all other columns (9/10 non-null)
- Analyses requiring volume_1h must wait for M3 data
