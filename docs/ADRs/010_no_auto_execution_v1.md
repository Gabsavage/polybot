# ADR-010: No automatic trade execution in v1

**Date**: 2026-04-22 (migrated from A_architecture_technique.md §10, phase A ADR-004)
**Status**: Accepted
**Milestone**: Phase A

## Context

The bot could theoretically place trades automatically via the CLOB API (signed orders). Need to decide whether v1 includes auto-execution or stays signals-only with human operator.

## Options considered

- **Auto-execution**: Bot places trades directly. Fast, no human latency. But: regulatory risk (CASP/MiCA if copy-trading is published), catastrophic bug risk in v1, no track record to trust sizing yet.
- **Signals + sizing recommendation**: Bot emits alerts with recommended position size. Human operator executes manually on Polymarket. Safe, auditable, reversible.

## Decision

Signals-only in v1. Bot emits alerts with sizing recommendation via Telegram. Human-in-the-loop for all execution.

## Consequences

- Human-in-the-loop protects against catastrophic v1 bugs (wrong sizing, inverted signals, API misunderstanding)
- Regulatory risk eliminated — no automated copy-trading service
- Trade-off: 2-5 min human latency between alert and execution. Acceptable for the signal types we track (sharp money moves, not HFT)
- Revisitable after 3-6 months of validated track record (post-M12, live limited phase)
