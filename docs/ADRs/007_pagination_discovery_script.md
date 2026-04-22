# ADR-007: Data API pagination capped at 3100 for Tier A discovery

**Date**: 2026-04-22
**Status**: Accepted
**Milestone**: M1 (research/prep M2)

## Context

The Tier A discovery script pulls trade history for ~150 candidate wallets via Polymarket Data API `/trades`. Some wallets have tens of thousands of trades. Progressive pagination (phase 1: 500 trades quick scan, phase 2: full fetch if promising) balances speed vs completeness.

## Options considered

- **Cap 500**: v1 approach. Too low — 29/30 candidates hit the cap, biasing trades_count and preventing proper filtering.
- **Cap 3100**: 31 pages x 100. Sufficient to discriminate long vs short history, classify A1/A2/reject accurately. ~10s per heavy wallet.
- **Cap 10000**: Near-exhaustive. 3-5x slower on heavy wallets. Marginal benefit for classification purposes.
- **Unlimited**: Risk infinite pagination on market makers with 50K+ trades. Unacceptable runtime.

## Decision

Progressive pagination with effective cap ~3100. Phase 1 (500 trades) for quick filtering, phase 2 (up to cap) only for wallets with >= 15 unique markets. Column `trades_capped` flagged True when cap reached.

## Consequences

- Runtime: ~15 min for 150 wallets (acceptable for one-shot research script)
- Wallets with trades_capped=True may have underestimated track record metrics
- Sufficient for initial seed list classification (9 A1 + 4 A2 selected)
- Can be re-run with higher cap in M7 if refinement needed
