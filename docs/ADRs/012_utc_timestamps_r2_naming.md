# ADR-012: UTC timestamps for R2 snapshot file naming

**Date**: 2026-04-22
**Status**: Accepted
**Milestone**: M1

## Context

CLOB snapshot files stored on Cloudflare R2 follow the naming convention `snapshots/YYYY-MM-DD/HH.parquet`. The question is which timezone the `HH` component reflects: server local time (CEST/CET given Contabo Atlanta VPS) or UTC.

Using local time creates ambiguity twice per year (DST transitions) and confuses analyses spanning timezones. Using UTC is unambiguous but creates a mental offset when comparing systemd logs (which display local time CEST) against file names.

## Options considered

- **Local time (CEST/CET)**: Matches systemd log display. But creates DST ambiguity (2 files named 02.parquet at fall DST, gap at spring DST) and timezone confusion in multi-region analyses.
- **UTC**: Unambiguous, industry standard, simplifies time-range queries. Requires mental offset when reading systemd logs (UTC+1 or UTC+2 depending on season).

## Decision

R2 file names use UTC timestamps for the `HH` component. This is already the behavior of the current implementation (`datetime.now(UTC).strftime("%H")`).

## Consequences

- Mental mapping required when correlating systemd logs (CEST display) with R2 file names (UTC). Offset: CEST = UTC + 2h in summer, CET = UTC + 1h in winter
- No DST ambiguity — every hour of every day produces exactly one file
- Queries spanning multiple days work correctly (no missing/duplicate hours at DST transitions)
- Cross-referencing with Polymarket APIs (which return timestamps in unix epoch UTC) is direct

## Notes

Explicit example for 2026-04-22 (CEST = UTC+2):
- Log: "polybot-snapshot started at 14:00:54 CEST"
- File: snapshots/2026-04-22/12.parquet

When reviewing a production incident, always cross-check timestamps in UTC before correlating systemd logs with R2 content.
