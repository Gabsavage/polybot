# ADR-004: VPS Provider — Contabo Atlanta

**Date**: 2026-04-22
**Status**: Accepted
**Milestone**: M1

## Context

M1 requires a VPS to run CLOB snapshot indexer (hourly), universe refresh (6h), and healthcheck (6h) as systemd timers. Polymarket APIs are geo-blocked outside the US, so the VPS must have a US IP. Need 4+ GB RAM for DuckDB + concurrent Python processes.

## Options considered

- **Hetzner CX22 Nuremberg**: 2 vCPU, 4 GB, 40 GB, ~5 EUR. Geo-blocked by Polymarket — requires WireGuard/VPN overlay (extra complexity + cost).
- **Hetzner CPX11 Ashburn**: 2 vCPU, 2 GB, 40 GB, ~$4.50. Only 2 GB RAM, tight for DuckDB + Python.
- **Hetzner CPX21 Ashburn**: 3 vCPU, 4 GB, 80 GB, ~$8. Good but 2x cost of Contabo for less RAM.
- **Contabo VPS 10 Atlanta**: 4 vCPU, 8 GB RAM, 75 GB NVMe, $4/mois. Best price/performance ratio.
- **Vultr/DigitalOcean US**: 2 vCPU, 4 GB at $12-24/mois. Expensive for a side project.

## Decision

Contabo Cloud VPS 10, Carlstadt NJ (US-East), $4/mois. 4 vCPU, 8 GB RAM, 75 GB NVMe SSD.

## Consequences

- US location eliminates VPN complexity — direct API access, simpler ops
- 8 GB RAM gives headroom for M7+ enrichment jobs without upgrade
- $4/mois keeps infra well under the 30 EUR/mois budget cap
- Risk: Contabo less reliable than Hetzner (occasional network issues reported). Acceptable for side project — redeploy to Hetzner US in 30 min if needed
- Monitoring uptime manually for first month
