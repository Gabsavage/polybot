# ADR-009: Hybrid LLM + rules for C3 Resolution Risk

**Date**: 2026-04-22 (migrated from A_architecture_technique.md §10, phase A ADR-003)
**Status**: Accepted
**Milestone**: Phase A

## Context

C3 (Resolution Risk Filter) needs to assess the risk that a market resolves ambiguously or gets disputed. Market questions on Polymarket are often poorly worded, making pure rule-based classification unreliable.

## Options considered

- **Pure rule-based**: Fast, deterministic. But fails on ambiguous question phrasing, novel market types, and edge cases in resolution criteria.
- **Pure LLM (GPT-4o or Claude Opus)**: High quality but expensive per call, slow. Overkill for a classification task.
- **Hybrid: Claude Haiku once at market creation + dynamic rules at scoring time**: LLM handles semantic analysis (cached permanently), rules handle dynamic factors (dispute history, liquidity vs bond, oracle reliability).

## Decision

Hybrid approach. Claude Haiku called once per market at creation (result cached permanently in `resolution_risk_cache`). Dynamic rules applied at scoring time combining LLM score + real-time factors.

## Consequences

- Cost negligible: Haiku is cheap, one call per market (not per alert)
- Semantic quality far superior to pure rules on ambiguous questions
- Cache means no repeated API calls — LLM cost scales with new markets, not with alert volume
- Alternative rejected: GPT-4o — more expensive, not significantly better on this classification task
- Score formula: `0.5 * llm_score + 0.3 * rules_score + 0.2 * oracle_reliability`
