# ADR-005: Top-150 markets selection criterion

**Date**: 2026-04-22
**Status**: Accepted
**Milestone**: M1

## Context

Snapshotting the order book of ALL Polymarket markets would be too costly in API calls and storage. Need a selection criterion that captures the most signal-rich markets while staying within R2 free tier.

## Options considered

- **Top 500 by volume_24h**: Comprehensive but produces ~4.4M snapshots/year, saturates R2 free tier in months.
- **Top 150 with volume_24h > $50K**: ~1.3M snapshots/year, captures 90%+ of useful signal (liquid markets where the edge exists).
- **Top 100 with volume_24h > $100K**: More restrictive, ~0.9M/year. Risk missing emerging high-activity markets.

## Decision

Top 150 markets sorted by volume_24h descending, filtered by volume_24h > $50K. Selection refreshed every 6h via dedicated `refresh_snapshot_universe` job.

## Consequences

- R2 storage controlled: 0.19 GB/year observed (well under 10 GB free tier)
- 6h refresh follows market rotation (new markets can spike on breaking news, resolved markets drop out)
- In practice, often < 150 markets pass the $50K filter — the min() of both constraints applies
- Edge case: during low-activity periods (weekends, holidays), fewer markets may pass the threshold

## Notes

Rationale detailed in B_plan_developpement.md section 3.4.
