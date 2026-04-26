# Polymarket Bot — Progress

## 2026-04-27 — M8-M10 déployés, dashboard v2 shipped

### M7-lite — Wallet Scoring (2026-04-25)
- score_tier_a.py : 15 wallets scorés
  - Erasmus démoté (0/13 win rate, -$82K P&L)
  - 9 wallets avec 0 trades résolus (données insuffisantes)
  - aenews2, extractive-manatee, TheMangler positifs (petit échantillon)
- scan_new_sharps.py : funnel 33K wallets → 825 filtrés → 14 candidats (score ≥7)
- lookup_candidates.py : Data API deep-dive sur top 5 — aucun candidat clair (bots sports volume-heavy)
- À relancer dans 2 semaines avec plus de données

### M8-A — Orchestrateur (2026-04-26)
- Kill switches : 8 targets (c1, c2, c3, all_alerts, trades, markets, onchain, resolutions)
- Rate limits centralisés : C1 10/h 40/j, C2 2/h 5/j, /risk 20/h, LLM 50/h
- Circuit breakers : indexer health (3 fails → auto-kill), LLM cost ($3/mois), disk 80%
- Audit log : événements persistés, commande /audit
- Migration 007 (kill_switches, rate_limit_counters, audit_log recreated)

### M8-C — Rapport hebdo (2026-04-26)
- generate_weekly_report() séparé du daily
- Dimanche 20h CEST automatique, commande /weekly
- Sections : alertes C1/C2, performance shadow, wallets, alignment, orchestrateur, coûts

### M8-B v1 — Dashboard Web (2026-04-26)
- FastAPI backend intégré dans le daemon (uvicorn embarqué — résout conflit DuckDB lock)
- React frontend, Caddy reverse proxy avec basic auth
- 5 pages : Overview, Alerts, Wallets, Performance, System
- Accessible http://62.146.230.73:3000

### M8-B v2 — Dashboard refonte (2026-04-27)
- Frontend wipé + reconstruit : SWR + Tailwind v4 (`@theme`) + Geist font + lucide-react
- Design "trading terminal" : liquid-glass cards, ambient gradient, font-light hero numbers, sidebar flottante
- Logo Polybot intégré (sidebar 128×128 + favicon)
- Palette : `accent-blue` (#4f70ff, ex-orange) + `accent-violet` + `accent-cyan` (radar feel)
- Responsive : sidebar desktop ≥768px, bottom tab bar mobile, mobile header
- 6 pages incluant nouvelle WalletDetail (`/wallets/:address`)
- 3 nouveaux endpoints API : `/api/clusters`, `/api/wallets/{address}` (avec cex/cluster), `/api/wallets/{address}/trades`
- `/api/markets/hot` modifié : ranking par C2 score (BREAKING)
- 240 tests, lint clean

### Daemon unifié (2026-04-25)
- Tous les indexers + bot + C1 + C2 fusionnés dans un seul process
- ThreadPoolExecutor(max_workers=1) sérialise les écritures DuckDB
- Élimine la contention multi-process (cause racine des 1863 restarts trades, 83 erreurs)
- Anciens timers M2-M3 supprimés, 3 timers M1 conservés
- Circuit breaker loop intégrée

### M9 — CEX Funding Detection (2026-04-26)
- 24 CEX hot wallets vérifiés Polygonscan (Binance 7+1 discovered, Coinbase 3, OKX 3, Kraken 3, etc.)
- indexer_cex_funding : traçage 2 hops USDC via Alchemy, 50 wallets/heure
- shared_cex_deposit_ratio : 8ème feature C2 (>30% = signal)
- Migration 008 (cex_hot_wallets, cex_funding_map)
- Découverte : hot wallet Binance 0xf70da978... trouvé via validation ground truth Iran

### M10 — Wallet Clustering Victor (2026-04-26)
- Session 1 calibration : signal shared_funded_by validé
  - Théo 4/4 (même funded_by 0x4b6f17...)
  - Iran 6/6 (même funded_by 0xf70da9...)
  - Témoin : 0 faux cluster (hors HW Binance découvert)
  - Pas besoin de grid search — le signal est binaire
- Session 2 prod : clustering daily, 2 clusters trouvés (Théo/4 + 1 paire organique)
- cluster_co_presence : bonus +1 au score C2 si ≥3 wallets même cluster
- Migration 009 (wallet_clusters, wallet_cluster_members)

### État actuel du système
- Shadow mode ON (alertes dans #ops)
- 7 indexers actifs : trades (60s), markets (15min), proxy_factory (1h), resolutions (1h), onchain (1h), cex_funding (1h), clustering (daily)
- C1 : 18 alertes émises, 6 résolues, Shadow P&L +$156.97
- C2 : scanne 300+ marchés hot / 5 min, 0 alertes (seuil 4/8 non atteint)
- C3 : 14+ marchés scorés, cache LLM actif
- Dashboard v2 déployé (http://62.146.230.73:3000)
- 240 tests, lint clean
- RAM : 1.2 GB / 7.8 GB, Disk : 21 GB / 145 GB

---

## 2026-04-26 — Gate M3-M6 PASSED

### Daemon unifié

Tous les indexers et composants fusionnés dans un seul process daemon.
Élimine la contention DuckDB multi-process (ADR-013 obsolète).
- ThreadPoolExecutor(max_workers=1) sérialise les écritures
- Anciens timers M2-M3 supprimés
- 164 tests, lint clean

### M6 — C2 Informed Trading (déployé 2026-04-25)

- 7 features on-chain : fresh_wallets, concentration, time_to_event,
  niche_market, momentum, volume_zscore, single_dominance
- Score >= 4/7 → alerte
- Alignment v0 (informatif, pas filtrant)
- alert_outcomes job (10 outcomes enrichis post-résolution)
- /toggle shadow pour promotion #ops → #alerts

### M5 — C3 Resolution Risk (déployé 2026-04-25)

- Haiku one-shot + cache permanent + 4 rules dynamiques
- Score composite : 50% LLM + 30% rules + 20% oracle
- /risk command < 5s (cache hit < 100ms)
- Intégré dans C1 (remplace placeholder 0.3) — 11/11 alertes avec vrai score

### M4 — Bot Telegram + C1 Sharp Money (déployé 2026-04-25)

- Bot : /status, /bankroll, /help, /recent, /risk, /report, /toggle
- C1 : 4 filtres, BUY only, Quarter-Kelly sizing, shadow mode
- 11 alertes C1 émises, bankroll $2000
- Alert IDs : AL_YYYYMMDD_XXXX séquentiels

### M3 — Enrichissement minimal (déployé 2026-04-25)

- proxy_eoa_map : 91,974 proxies, 15/15 Tier A matchés
- resolutions : 1,014,570 via ConditionalTokens events
- trades_all : 5,332,147 via Alchemy RPC direct
- Pivots : Goldsky mort → Alchemy, UMA Oracle → ConditionalTokens, factory scan → lookup ciblé

### M7-lite — Wallet scoring (scripts prêts)

- score_tier_a.py : 15 wallets scorés, Erasmus démoté (0/13)
- scan_new_sharps.py + lookup_candidates.py : funnel de découverte
- À relancer dans 2 semaines avec plus de données

---

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
