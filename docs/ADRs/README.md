# Architecture Decision Records (ADRs)

Documenting significant technical decisions for the Polymarket Bot project.

## Index

| ADR | Title | Milestone | Status |
|-----|-------|-----------|--------|
| [001](001_python_version.md) | Python version 3.13 | M1 | Accepted |
| [002](002_duckdb_local_storage.md) | DuckDB as local hot storage | M1 | Accepted |
| [003](003_parquet_zstd_partitioning.md) | Parquet + zstd + hourly partitioning | M1 | Accepted |
| [004](004_vps_provider_contabo.md) | VPS Provider: Contabo Atlanta | M1 | Accepted |
| [005](005_top_150_markets_selection.md) | Top-150 markets selection criterion | M1 | Accepted |
| [006](006_volume_1h_null_m1.md) | volume_1h null in M1, populated M3 | M1 | Accepted |
| [007](007_pagination_discovery_script.md) | Data API pagination cap for discovery | M1 | Accepted |
| [008](008_polling_60s_vs_websocket.md) | Polling 60s rather than WebSocket for C1 | Phase A | Accepted |
| [009](009_hybrid_llm_rules_c3.md) | Hybrid LLM + rules for C3 Resolution Risk | Phase A | Accepted |
| [010](010_no_auto_execution_v1.md) | No automatic trade execution in v1 | Phase A | Accepted |
| [011](011_proxy_eoa_mapping_mandatory.md) | Proxy-EOA mapping mandatory before scoring | Phase A | Accepted |

## Template

```markdown
# ADR-XXX: <Title>

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Milestone**: MX

## Context

<2-4 sentences describing the problem>

## Options considered

<List with pros/cons, 1-2 sentences each>

## Decision

<Chosen option, 1-2 sentences>

## Consequences

<Bullet points: positive and negative>
```
