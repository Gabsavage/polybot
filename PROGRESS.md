# Polymarket Bot — Progress

## 2026-04-22 — M1 deployed to prod, Tier A seed list complete

### M1 Deliverables

| Livrable | Status |
|----------|--------|
| Repo restructured (polybot package, src/ layout) | Done |
| DuckDB schema (12 tables) + migration runner | Done |
| Config module (pydantic-settings) | Done |
| R2 storage wrapper (boto3) | Done |
| CLOB snapshot indexer + refresh_universe | Done |
| Healthcheck | Done |
| Validation script | Done |
| GitHub Actions CI (ruff + pytest) | Done |
| systemd timers on VPS | Done, running |
| Seed list 15 wallets | Done |

### VPS Prod

- Contabo VPS 10, Atlanta US ($4/mois)
- 3 systemd timers: snapshot (hourly), universe-refresh (6h), healthcheck (6h)
- First automated snapshot: 300 rows, 150 markets, 0 errors
- Gate M1 preliminary at T+45min: all quantitative criteria met
- Final gate pending 3-4h stability window

### Tier A Discovery

- Discovery script v2: portfolio value via /value endpoint, anti-bot filters, auto-classification
- 3886 wallets scanned, 149 pre-filtered, 43 passed quantitative filters
- 9 A1 + 11 A2 candidates identified
- 9 wallets selected (5 A1 + 4 A2) to complete seed list to 15
- Tier B watchlist: 23 borderline rejects for M7 re-evaluation

### Documentation

- 11 ADRs (ADR-001 to 011) consolidated in docs/ADRs/
- Phase A ADRs migrated from A_architecture_technique.md §10
- Gate M1 preliminary in GATES.md

### Key metrics

- Unit tests: 17/17 pass
- R2 projection: 0.19 GB/year (52x margin on free tier)
- VPS resources: 511 MB RAM (6.5%), 3.3 GB disk (2.3%)
- Snapshot: 23.5 KB avg, 300 rows, ~6s CPU

Next: Gate M1 final (after 3-4h stability), then M2 (indexers + trades polling)

---

## 2026-04-21 — M1 code complete (local)

- Repo restructured: polycasquette -> polybot, src/ layout
- 11 commits: schema, config, R2, logging, indexer, healthcheck, validation, CI, README, deploy
- 12/12 unit tests pass, lint clean
- Integration tests: R2 connectivity OK, Gamma/CLOB APIs OK, 300 rows snapshot validated
- research/ directory created, Phase C notebook moved

---

## 2026-04-20 — Phase C complete

- Ground truth enriched (14/32 addresses via Polymarket API)
- Pilot notebook Iran cluster executed end-to-end
- Recall 71% (5/7), Precision 50% (5/10), F1 59%
- 4 adjustments identified for Phase B
- Tag: `phase-c-complete`

---

## Phase C — Detail

### Deliverables

| File | Description |
|------|-------------|
| `data/ground_truth/cases.csv` | 18 forensic cases |
| `data/ground_truth/wallets.csv` | 31 wallets (22 with address, 71%) |
| `data/ground_truth/sharps_positive.csv` | 9 sharps (6 with address, 67%) |
| `data/ground_truth/enrichment_log.md` | API lookup log |
| `data/ground_truth/iran_base_rate_investigation.csv` | 5 non-GT flags (all FP) |
| `research/phase_c/01_pilote_iran_cluster.ipynb` | Iran pilot notebook |
| `scripts/enrich_ground_truth.py` | Address enrichment script |

### Known limitations

| Problem | Impact | Workaround |
|---------|--------|------------|
| CLOB `/trades` auth-only | No market-first view | Data API per wallet + Dune |
| 12 GT addresses unrecoverable | Max recall ~7/11 | Accepted structural limit |
| Direction-blind heuristics | 50% precision | Adjustment 1: directional filter |
| GT biased winners-only | No contrarian ground truth | Document bias, no fix |
