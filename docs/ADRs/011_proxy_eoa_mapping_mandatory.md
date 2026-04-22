# ADR-011: Proxy-EOA mapping mandatory before any scoring

**Date**: 2026-04-22 (migrated from A_architecture_technique.md §10, phase A ADR-005)
**Status**: Accepted
**Milestone**: Phase A

## Context

Polymarket uses proxy wallets (Safe Proxy + custom Polymarket Proxy Factory). A single user (EOA) can have multiple proxy addresses. Without mapping proxy to EOA, per-user metrics are fragmented — a trader with 3 proxies appears as 3 separate wallets with 1/3 of their real volume each.

## Options considered

- **Ignore proxies**: Treat each address as independent. Fast to implement but produces phantom wallets, duplicate alerts, and incorrect leaderboard rankings.
- **Map proxy-EOA in M3 before scoring components**: Index `ProxyCreation` events from both factory contracts, build `proxy_eoa_map` table. All downstream scoring queries join through this mapping.

## Decision

`indexer_proxy_factory` delivered in M3, before any scoring component (C1 in M4, C2 in M6). Backfill ~100K+ proxies + incremental hourly updates.

## Consequences

- Per-user metrics are correct from the start — no retroactive fix needed
- Leaderboard and wallet scoring produce clean results (no phantom duplicates)
- Dependency: M4-M6 components blocked until M3 proxy mapping is operational
- Source: rapport 4 section 9.5 documents this requirement

## Notes

Related to ADR-002 (DuckDB schema includes `proxy_eoa_map` table from M1, populated in M3).
