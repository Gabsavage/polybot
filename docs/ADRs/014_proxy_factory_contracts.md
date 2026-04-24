# ADR-014: Proxy Factory contracts for EOA mapping

**Date**: 2026-04-24
**Status**: Accepted
**Milestone**: M3

## Context

Polymarket users interact via proxy wallets, not directly from their
EOA. Two factory contracts create these proxies on Polygon:

1. Gnosis Safe Proxy Factory (`0xa6b71e26c5e0845f74c812102ca7114b6a896ab2`)
   — used by MetaMask/EOA wallets. Actively creating proxies (~18
   ProxyCreation events per 1000 blocks as of April 2026).

2. Polymarket Custom Proxy Factory (`0xaB45c5A4B0c941a2F231C04C3f49182e1A254052`)
   — used by Magic.link/email wallets. No recent ProxyCreation events
   in last 1000 blocks, but historically active. Likely legacy or
   batch-creation pattern.

Without mapping proxy→EOA, a trader with multiple proxies appears as
separate wallets, fragmenting per-user metrics (ADR-011).

## Decision

Index both factories in `indexer_proxy_factory`:
- Gnosis Safe Factory: primary, active, captures majority of current
  proxy creations
- Polymarket Custom Factory: secondary, captures historical
  Magic.link proxies from backfill

Both use the same `ProxyCreation(address,address)` event
(topic: `0x4f51faf6c4561ff95f067657e43439f0f856d97c04d9ec9070a6199ad418e235`).

## Consequences

- Backfill scans both factories from block ~11M (early Polygon) to head
- Incremental hourly scans both but Polymarket factory may yield 0 new events
- Budget: ~1.5M CU one-shot backfill + ~50K CU/month incremental
  (< 1% of Alchemy free tier 300M CU/month)
- If a third factory is discovered later, add it to config without schema change
