# ADR-004: VPS Provider — Contabo Atlanta

**Date:** 2026-04-22
**Status:** Accepted
**Deciders:** Gab

## Context

M1 requires a VPS to run CLOB snapshot indexer (hourly), universe refresh (6h), and healthcheck (6h) as systemd timers. Polymarket APIs are geo-blocked outside the US, so the VPS must have a US IP.

## Decision

Contabo Cloud VPS 10, Carlstadt NJ (US-East), $4/mois.

Specs: 4 vCPU, 8 GB RAM, 75 GB NVMe SSD, unlimited traffic.

## Alternatives Considered

| Provider | Location | Specs | Cost | Issue |
|----------|----------|-------|------|-------|
| Hetzner CX22 | Nuremberg DE | 2 vCPU, 4 GB, 40 GB | ~5 EUR | Geo-blocked by Polymarket, needs VPN overlay |
| Hetzner CPX11 | Ashburn US | 2 vCPU, 2 GB, 40 GB | ~$4.50 | Only 2 GB RAM, tight for DuckDB + Python |
| Hetzner CPX21 | Ashburn US | 3 vCPU, 4 GB, 80 GB | ~$8 | 2x cost of Contabo for less RAM |
| Vultr | US | 2 vCPU, 4 GB | ~$24 | Expensive |

## Rationale

- **US location eliminates VPN complexity.** No WireGuard/Mullvad needed. Direct API access, simpler ops, one less failure mode.
- **8 GB RAM for $4/mois.** DuckDB can be RAM-hungry on analytical queries. 8 GB gives headroom for M7+ enrichment jobs.
- **Contabo reputation trade-off.** Less reliable than Hetzner (occasional network issues reported on forums). Acceptable for a side project — redeploy to Hetzner US in 30 min if Contabo becomes unreliable.
- **75 GB SSD.** Sufficient for DuckDB hot storage + Python venv. R2 handles cold Parquet storage.

## Consequences

- Monitoring uptime manually for first month (no auto-failover)
- If Contabo unreliable after 1 month, migrate to Hetzner CPX21 Ashburn ($8/mois)
- VPS IP: 62.146.230.73 (Carlstadt NJ)
