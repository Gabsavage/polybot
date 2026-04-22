# Component Specifications

Technical specs for each bot component and indexer. Used as reference when implementing or reviewing in Claude Code.

## Index

| Spec | Component | Milestone | Status |
|------|-----------|-----------|--------|
| [indexer_trades_spec.md](indexer_trades_spec.md) | Indexer Trades | M2 | Draft |
| [c1_sharp_money_spec.md](c1_sharp_money_spec.md) | C1 Sharp Money Copy | M4 | Draft |
| [c2_informed_trading_spec.md](c2_informed_trading_spec.md) | C2 Informed Trading | M6 | Draft |
| [c3_resolution_risk_spec.md](c3_resolution_risk_spec.md) | C3 Resolution Risk Filter | M5 | Draft |
| [m3_enrichment_spec.md](m3_enrichment_spec.md) | M3 Enrichment Layer (proxy-EOA, resolutions, goldsky, volume_1h) | M3 | Draft |

## Template

````markdown
# <Component Name> — Spec technique

## Objectif

<Brief description>

## Milestone

<MX>

## Dependances

<List>

## Source de donnees / Trigger

<...>

## Architecture / Logique

<...>

## Criteres de succes

<...>

## Edge cases

<...>

## A ne PAS faire

<...>

## Configuration

```python
class ComponentSettings(BaseSettings):
    ...
```
````
