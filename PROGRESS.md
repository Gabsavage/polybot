# Polymarket Bot — Progress

## 2026-04-22 — C4 Macro Discovery (exploration indépendante)

> **Nota** : C4 est un composant exploratoire **séparé** du plan B (M1-M12).
> Il s'agit d'un composant additionnel qui traderait systématiquement les marchés
> macro US (CPI, NFP, FOMC, GDP, etc.) en exploitant les nowcasts des Federal
> Reserve Banks régionales. Ce travail de discovery est un pré-requis avant toute
> décision d'intégration dans le plan de dev.

### Scan terrain Gamma API

- Script `research/phase_c4_macro/scan_macro_markets.py` : scan exhaustif des ~51k marchés actifs Polymarket
- Filtrage par keywords macro avec regex word-boundary + exclusion bruit (sports, pays non-US)
- **225 marchés US macro actifs** identifiés, répartis en 4 catégories

### Résultats clés

| Catégorie | Marchés | Liquidité médiane | Liquidité totale | Vol 24h total |
|-----------|---------|-------------------|------------------|---------------|
| Fed       | 147     | $15k              | $19.2M           | $6.3M         |
| CPI       | 41      | $3.8k             | $295k            | $24k          |
| GDP       | 23      | $1.9k             | $62k             | $9.7k         |
| Labor     | 14      | $3k               | $55k             | $1.8k         |

### Observations terrain

- **Fed rates = marché dominant** : 65% des marchés, >99% du volume. Top marché : $8.9M liquidity
- **CPI/Inflation** : granularité fine (monthly/annual par tranche 0.1%), résolution 12 mai
- **GDP** : Q1 2026, résolution 30 avril (advance estimate)
- **Labor** : unemployment rate par tranche, résolution 8 mai (NFP)
- **Gap** : aucun marché actif sur retail sales, PCE, PPI, ISM/PMI, jobless claims, housing starts, consumer confidence
- **Prochaines résolutions** : FOMC 29 avril, GDP 30 avril, unemployment 8 mai, CPI 12 mai

### Livrables

| Fichier | Description |
|---------|-------------|
| `research/phase_c4_macro/scan_macro_markets.py` | Script de scan (~95 lignes) |
| `research/phase_c4_macro/polymarket_macro_markets.csv` | 225 marchés, toutes colonnes |
| `research/phase_c4_macro/polymarket_macro_markets.md` | Tableau de synthèse + observations |

---

## 2026-04-24 — M2 COMPLETE (indexers deployed + gate validated)

### M2 Deliverables

| Livrable | Status |
|----------|--------|
| Migration 002 (schema alignment: trades, markets_gamma) | Done |
| Indexer trades (Data API, paginated, backfill + incremental) | Done |
| Indexer markets_gamma (bulk upsert via pyarrow + staging table) | Done |
| Seed Tier A script (15 wallets into DuckDB) | Done |
| systemd units: polybot-trades.service, polybot-markets.service/timer | Done |
| Unit tests: trades_dataapi, markets_gamma, seed_tier_a | Done |
| ADR-012 (UTC timestamps R2 naming) + ADR-013 (direct DuckDB writes M2) | Done |
| Specs: C2 informed trading (M6), C3 resolution risk (M5) | Done |
| M2 backlog consolidation (docs/M2_backlog.md) | Done |
| GitHub repo (Gabsavage/polybot, private) | Done |

### Key metrics (gate)

- **64K markets** indexed via Gamma API
- **871 trades** indexed via Data API for 15 Tier A wallets
- **15 Tier A wallets** seeded (11 A1 + 4 A2)
- Indexers stable on VPS, 0 errors in journalctl
- Bulk upsert perf: pyarrow + staging table (ADR-013)

### Commits (8)

| Hash | Description |
|------|-------------|
| `afc44d2` | ADR-012 UTC timestamps + timezone conventions |
| `5affb11` | C2 informed trading spec (515 lines, M6) |
| `a0b1ed5` | C3 resolution risk spec (M5) |
| `40faf5e` | Consolidate M2 backlog |
| `49a95f4` | Indexers, migration 002, seed script, systemd units |
| `d997099` | Fix deploy: align systemd units with VPS layout |
| `a17d392` | Perf: bulk upsert via pyarrow + staging table |
| `324567d` | C4 macro market discovery (225 US markets) |

### M2 Gate — VALIDATED

- Date : 2026-04-24
- Tag : `m2-complete`
- Decision : **GO**
- Next : M3

---

## 2026-04-22 — M1 COMPLETE (deployed + gate validated)

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

### M1 Final Gate — VALIDATED

- Date : 2026-04-22 15:15 CEST (T+3h after deployment)
- All quantitative criteria met, qualitative validation passed
- Decision : GO
- Next : M2 (indexer trades + indexer markets)

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
