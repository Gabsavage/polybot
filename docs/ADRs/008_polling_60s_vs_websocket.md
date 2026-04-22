# ADR-008: Polling 60s rather than WebSocket for C1

**Date**: 2026-04-22 (migrated from A_architecture_technique.md §10, phase A ADR-001)
**Status**: Accepted
**Milestone**: Phase A

## Context

C1 (Sharp Money Copy) needs to detect trades from tracked wallets with < 2 min latency. Two approaches: poll the CLOB/Data API every 60s, or maintain a persistent WebSocket connection to the CLOB streaming endpoint.

## Options considered

- **WebSocket**: Real-time push, ~5s latency. Requires reconnect logic, state machine for reorgs, heartbeat management. Complex for a v1 bot.
- **Polling 60s**: Simple HTTP GET on a timer. Latency ~60s worst case (trade happens right after a poll). Trivial to implement and debug.

## Decision

Polling every 60s on tracked wallets via Data API `/trades?user=<addr>`.

## Consequences

- Latency target < 2 min easily met (60s poll + processing time)
- Simple implementation — no reconnect logic, no state management
- Trade-off: if a sharp enters and exits a position in < 60s, we miss it. Rare for significant-size trades.
- Human operator takes 2-5 min to open Polymarket and trade anyway — sub-minute latency has no practical value in v1

## Notes

Revisitable in post-MVP if real-time becomes valuable (e.g., auto-execution in v2).
