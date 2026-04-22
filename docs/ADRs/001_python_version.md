# ADR-001: Python version 3.13

**Date**: 2026-04-22
**Status**: Accepted
**Milestone**: M1

## Context

Choosing the Python version for the project. All critical dependencies (DuckDB, pydantic, httpx, boto3, structlog) support 3.9+. The development machine already runs 3.13.

## Options considered

- **3.11**: Stable, widely deployed. But misses 2 years of improvements.
- **3.12**: Stable recent. Good middle ground but no strong reason to pin here.
- **3.13**: Latest stable. Best typing features, performance improvements, active security support.

## Decision

Python 3.13. Already installed locally and on VPS via uv.

## Consequences

- Latest typing features (TypeAlias, improved generics) available
- Performance improvements over 3.11/3.12
- All critical libs confirmed compatible (tested in M1)
- Minor: editable install `.pth` processing issue observed on macOS 3.13.0 — workaround via `pythonpath = ["src"]` in pytest config
