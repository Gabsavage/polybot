# Phase B — Plan de développement du Polymarket Bot

*Document de référence pour la phase d'implémentation. Destiné à être versionné dans les project files.*

*Version 2.2 — avril 2026. Recalibrée en milestones (sans timeline calendaire) avec decision gates méthodologiques. v2.1 a intégré 3 amendments post-review (escape valve M12, snapshot top-150, alignement v0 dès M6). v2.2 ajoute 3 raffinements mineurs : critère top-150 explicité (M1), routine shadow mode opérationnelle consolidée (M6 + §6.3), protocole R-O7 avec 3 jalons calendaires (sem 4 / sem 8 / sem 12).*

---

## 0. TL;DR de la phase B

Plan de développement structuré en **12 milestones** (M1 à M12), organisés en 3 blocs : MVP (M1-M6), MVP enrichi (M7-M9), Post-MVP avancé (M10-M12). Entre chaque milestone, un **decision gate** : bilan écrit obligatoire répondant à 3-5 questions méthodologiques avant passage au milestone suivant. Le goulot n'est pas le code mais les décisions structurantes — les gates sont là pour forcer la digestion.

**Shadow mode anticipé** : dès que M6 est terminé (MVP C1+C2+C3 minimaux opérationnels), le bot bascule en shadow mode **en parallèle** du développement des milestones M7-M12. Cela permet d'accumuler des semaines de data live réelle pendant que le dev des features avancées continue. Plus on accumule tôt, mieux c'est.

**Décisions de cadrage consolidées en amont** :

1. C1 en v1 = tracking seed-list manuelle uniquement, pas de leaderboard auto ni d'anti-honeypot sophistiqué. Reportés post-MVP après accumulation de data.
2. Signal d'alignement directionnel en dual-layer : pas de news-sentiment temps réel en v1, logging exhaustif des alertes avec outcomes pour affinage empirique.
3. Budget infra variable, cap 100 €/mois. Démarrage ~10 €.
4. Shadow mode anticipé, démarre dès M6. Minimum 4 semaines calendaires de shadow avant live limité (pas milestones — durée calendaire pour accumuler des résolutions réelles).
5. Snapshot CLOB historique dès M1 (non-négociable, moat 12-18 mois).
6. **Clustering Victor déplacé en post-MVP (M10)**, pas par contrainte temps mais parce que la phase C ne l'a pas validé empiriquement sur data Polymarket. On valide méthodologiquement avant branchement prod.
7. Strictement signals-mode, human-in-the-loop partout, git commit après chaque brique, pas d'auto-exec v1.

**Principe méthodologique transversal** : chaque brique testable indépendamment avant intégration. Entre deux milestones, passage obligatoire par un decision gate (section dédiée).

---

## 1. Architecture finale consolidée

### 1.1 Vue d'ensemble des composants

Le système s'articule en 6 couches :

1. **Couche ingestion** — 5 indexers (markets, trades, on-chain, resolutions, CLOB snapshots). Fréquences distinctes.
2. **Couche stockage** — DuckDB hot (< 90j) + Parquet cold partitionné par mois, et R2 pour snapshots CLOB.
3. **Couche enrichissement** — jobs batch : proxy↔EOA, wallet_metrics, alert_outcomes post-résolution, CEX funding (M9), clustering Victor (M10).
4. **Couche composants** — C1, C2, C3.
5. **Couche orchestration** — orchestrator central, kill switches, rate limits, dédup, sizing, audit log.
6. **Couche sortie** — bot Telegram avec topics, dashboard Streamlit local, commandes.

### 1.2 Intégration des 4 ajustements phase C — séquencée par milestone

Les 4 ajustements identifiés par le pilote sont intégrés en plusieurs vagues, pas tous en un coup. Cet échelonnement reflète une **priorisation méthodologique** : on ne branche un ajustement en prod qu'une fois qu'il est validé sur data live ou data archivée réelle.

| Ajustement | Milestone | Motivation du timing |
|---|---|---|
| 2 — Features de diversification | M7 | Calcul simple sur `wallet_metrics`, validable immédiatement sur les 18 cas forensiques archivés |
| 1 — Alignement directionnel (tri-layer) | M6 (v0 informatif) puis M8 (post-résolution) puis M11 (temps-réel calibré) | v0 dès M6 (price_momentum simple, non-filtrant, juste loggé) pour accumuler data shadow corrélée ; layer post-résolution M8 ; layer temps-réel calibré M11 sur 50+ alertes (cf amendment 3) |
| 4 — CEX funding source detection | M9 | Nécessite backfill Alchemy et calibration sur cluster Iran — testable sur 1 cas connu avant prod |
| 3 — Clustering Victor | M10 | **Le plus délicat** — pas validé en phase C sur data Polymarket. Méthodologie académique à valider empiriquement avant prod. Détail §1.4 |

### 1.3 Composants : spécifications v1

**C1 Sharp Money Copy (MVP minimal)**
- Scope : tracker 15 wallets Tier A seedés manuellement (Domer, Aenews2, Kickstand7, gopfan2, HolyMoses7, Beachboy4, + 9 à identifier via rapport 3 et leaderboards publics Dune).
- Polling : 60s via Data API `/trades?user=<addr>` par batch de 20 wallets.
- Trigger alerte : trade size USD ≥ 500 $, liquidité marché ≥ 5000 $, dédup `(wallet, market, side)` sur 30 min.
- **Pas d'anti-honeypot sophistiqué** (reporté post-MVP). 15 wallets vettés — risque honeypot marginal.
- **Pas de leaderboard auto** — reporté après 2-3 mois de data.
- Sizing : quarter-Kelly, cap 3% bankroll.

**C2 Informed Trading Alert (v1 minimal à M6, enrichi M7-M10)**
- Scan : 5 min sur `markets_hot` (volume 1h > 1000 $ OU move > 300 bps 1h OU résolution < 72h).
- Features v1 MVP (8 features avec ajout `alignment_score` v0 — `shared_cex_deposit_ratio` reporté M9) : `fresh_wallet_concentration`, `niche_market_flag`, `time_to_event`, `top5_concentration`, `price_momentum_1h`, `volume_zscore_robust`, `order_book_imbalance`, `alignment_score` (loggé non-filtrant).
- Score composite v1 règles : `fresh > 0.5` AND `top5 > 0.7` AND `time_to_event < 48h` AND `niche_market_flag` → 4 points.
- Enrichissements par milestone :
  - M6 : `alignment_score` v0 (price_momentum_alignment, loggé non-filtrant — cf amendment 3)
  - M7 : pénalité diversification (ajustement 2)
  - M8 : alignement post-résolution loggé dans `alert_outcomes`
  - M9 : `shared_cex_deposit_ratio` activé (ajustement 4)
  - M10 : bonus clustering (ajustement 3)
  - M11 : alignement directionnel temps-réel calibré (passage de v0 informatif à v1 filtrant)

**C3 Resolution Risk Filter (v1 complet à M5)**
- Étage 1 : LLM Haiku une fois par marché à la création (cache permanent).
- Étage 2 : rules dynamiques (historique disputes catégorie, liquidité vs bond, oracle reliability).
- Score composite : `0.5 * llm + 0.3 * rules + 0.2 * oracle_reliability`.

### 1.4 Pourquoi déplacer le clustering Victor en M10

Décision méthodologique explicite. Le clustering Victor 2020 (deposit-address-reuse) est cité par tous les rapports comme l'heuristique la plus puissante pour Polymarket, utilisée par Chainalysis sur le cas Fredi9999. **Pourtant, la phase C ne l'a pas validé empiriquement** — le pilote Iran a explicitement exclu le critère CEX funding (§1 synthèse pilote : "Le 5e critère du rapport 3 n'a **pas** été évalué").

Conséquences :
- On ne connaît pas le vrai taux de faux positifs de l'algo sur data Polymarket (les hot wallets CEX fundent des millions d'adresses — le filtrage doit être très précis)
- On ne connaît pas les seuils optimaux de `amount_diff` et `block_diff` pour Polygon (valeurs littérature pour Ethereum mainnet)
- On ne sait pas si les clusters obtenus seront de taille raisonnable (cluster à 1000 wallets = inutilisable)

**Approche** : M10 est un milestone **dédié à la validation + implémentation** du clustering. Session 1 = notebook de calibration sur 7 wallets Iran + échantillon témoin, avant de brancher en prod. Session 2 = implémentation prod avec config validée.

Alternatives rejetées :
- Intégrer en MVP avec seuils littérature → risque pourrir les alertes C2 avec clusters faux positifs
- Ne jamais intégrer → on rate la valeur documentée par Chainalysis/Bubblemaps

**En M6-M9, C2 tourne sans clustering**. Les alertes sont toujours émises, juste avec un critère en moins. Le pilote a montré 71% recall sans clustering — on garde ce niveau jusqu'à M10.

### 1.5 Principe du shadow mode anticipé

Dès la fin de M6, le bot est en shadow mode sur les 3 composants MVP, **en parallèle du dev M7-M12**.

```
Timeline personnelle            Bot en prod (VPS)
─────────────────────           ──────────────────────────

M1-M6 (dev MVP)            ──►  Dev + tests, alertes dans #ops
                                Snapshot CLOB actif

M6 decision gate pass      ──►  Alertes promues dans #alerts
                                SHADOW MODE démarre
                                operator_traded = false partout

M7-M12 (dev features)      ──►  Bot tourne en shadow, dev en parallèle
                                Chaque M7-M12 pushé en prod dès validé
                                Shadow data s'accumule en continu

Fin M12 + shadow ≥ 4 sem   ──►  Gate live limité
+ ≥ 15 alertes résolues
+ precision ≥ 40%

Live limité ≥ 4 sem calend. ──►  Cap $30-50/trade, max 1 trade ouvert
≥ 15 trades + P&L positif   ──►  Live complet, sizing Kelly adaptatif
```

**Pourquoi ça change tout** : la phase shadow dure **au minimum 4 semaines calendaires** pour accumuler des résolutions réelles (les marchés mettent des semaines à se résoudre). Ce n'est pas parallèle à ton temps de dev — c'est du temps calendaire qui tourne pendant que tu vis. Donc plus tu démarres tôt, plus tu as de data shadow avant live limité. Si tu boucles M1-M12 en 3 semaines calendaires, le bot aura déjà 3 semaines de shadow accumulée.

### 1.6 Diagramme de flux (avec milestone d'intro)

```
                         ┌─────────────────────────────────────┐
                         │  SOURCES EXTERNES                   │
                         │  Gamma / Data API / CLOB / Goldsky  │
                         │  Alchemy RPC Polygon / UMA / R2     │
                         └──┬────┬────┬────┬────┬────┬────┬────┘
                            │    │    │    │    │    │    │
       ┌────────────────────┘    │    │    │    │    │    └──────────────────┐
       │                         │    │    │    │    │                       │
       ▼                         ▼    ▼    ▼    ▼    ▼                       ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────────────┐
│ indexer_     │ │ indexer_     │ │ indexer_     │ │ indexer_    │ │ indexer_         │
│ markets_     │ │ trades_      │ │ onchain_     │ │ resolutions │ │ clob_snapshot    │
│ gamma        │ │ dataapi      │ │ goldsky      │ │ _uma        │ │ (hourly top-150) │
│ [M2] 15min   │ │ [M2] 60s     │ │ [M3] 1h      │ │ [M3] 1h     │ │ [M1] - MOAT      │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬──────┘ └────────┬─────────┘
       │                │                │                │                 │
       └────────┬───────┴────────┬───────┴────────┬───────┘                 │
                │                │                │                         │
                ▼                ▼                ▼                         ▼
        ┌─────────────────────────────────────────────────┐    ┌─────────────────────┐
        │  STOCKAGE HOT : DuckDB (/data/pm.duckdb)         │    │  COLD : R2          │
        │                                                   │    │  orderbook_         │
        │  [M1] markets, trades, wallets, alerts,          │    │  snapshots_*.parquet│
        │       kill_switches, rate_limit_counters,        │    │  partitionné mois   │
        │       audit_log                                  │    │                     │
        │  [M3] proxy_eoa_map, resolutions, trades_all     │    │                     │
        │  [M6] alert_outcomes                             │    │                     │
        │  [M7] wallet_metrics (diversification)           │    │                     │
        │  [M9] cex_hot_wallets, cex_funding_map           │    │                     │
        │  [M10] wallet_clusters, wallet_cluster_members   │    │                     │
        └────────────┬───────────────────────────┬──────────┘    └─────────────────────┘
                     │                           │
                     ▼                           ▼
    ┌────────────────────────────┐   ┌──────────────────────────────┐
    │  JOBS BATCH (APScheduler)  │   │  COMPOSANTS (poll/scan)      │
    │                            │   │                              │
    │  [M1] snapshot_clob          │ │  [M4] C1 Sharp Money Copy    │
    │  [M3] compute_proxy_eoa_map  │ │    poll 60s Tier A (15)      │
    │  [M5] backup_db daily        │ │                              │
    │  [M6] log_alert_outcomes     │ │  [M6] C2 Informed Trading    │
    │  [M7] compute_wallet_metrics │ │    scan 5min markets_hot     │
    │  [M9] trace_cex_funding      │ │    [M7] + pénalité divers.   │
    │  [M10] cluster_wallets_victor│ │    [M9] + shared_cex_deposit │
    │                              │ │    [M10] + bonus clustering  │
    │                              │ │    [M11] + alignment v2      │
    │                              │ │                              │
    │                              │ │  [M5] C3 Resolution Risk     │
    │                              │ │    LLM Haiku + rules         │
    └────────────┬───────────────┘   └──────────────┬───────────────┘
                 │                                  │
                 └─────────────────┬────────────────┘
                                   ▼
                    ┌─────────────────────────────────┐
                    │  [M8] ORCHESTRATEUR             │
                    │  rate limits, kill switches,    │
                    │  dédup alertes, sizing Kelly,   │
                    │  audit log, scheduler daemon    │
                    └────────────────┬────────────────┘
                                     ▼
                    ┌─────────────────────────────────┐
                    │  [M4-M5] BOT TELEGRAM           │
                    │  #alerts (C1, C2)               │
                    │  #risk (C3 enrichissement)      │
                    │  #ops (digests, kill switches)  │
                    │  #errors (alerts techniques)    │
                    │  commandes : /risk /bankroll    │
                    │              /status /toggle    │
                    └─────────────────────────────────┘
```

---

## 2. Stack technique détaillée

### 2.1 Services externes

| Service | Usage | Plan démarrage | Coût | Seuil upgrade |
|---|---|---|---|---|
| Gamma API | Metadata marchés | Public | 0 € | Jamais (stable) |
| Data API | Trades par wallet, holders | Public | 0 € | Jamais |
| CLOB API | Order book, midpoint, spread | Public (read) | 0 € | Jamais pour read |
| Goldsky subgraph | Activity on-chain large | Free tier | 0 € | Si < 50 req/s insuffisant |
| Alchemy RPC Polygon | Events, funding trace | Free 300M CU | 0 € | Si backfill > 50% CU |
| Dune Analytics | Backfill historique SQL | Free (2500 credits) | 0 € | Si credits < 500 avant fin mois |
| Anthropic API Haiku | C3 scoring | Pay-per-use | < 1 €/mois | Jamais |
| Telegram Bot API | Alertes | Public | 0 € | Jamais |
| R2 (Cloudflare) | Snapshot CLOB + backups | Free 10 GB | 0 € | Si > 10 GB (~6 mois) |

**Budget services démarrage : 0 €/mois** (hors VPS).

### 2.2 Infrastructure

| Composant | Choix | Coût mensuel |
|---|---|---|
| VPS | Hetzner CX22 (2 vCPU, 4 GB RAM, 40 GB NVMe, Nuremberg) | ~5 € |
| OS | Ubuntu 24.04 LTS | 0 € |
| Process supervision | systemd | 0 € |
| Reverse proxy | Caddy | 0 € |
| Backups | rclone → R2 | 0 € (free tier) |

**Total démarrage : ~10 €/mois**.

### 2.3 Seuils d'upgrade empiriques

| Trigger | Décision | Coût additionnel |
|---|---|---|
| Goldsky rate limited / timeout | Upgrade Dune Plus ($49) | +45 €/mois |
| Alchemy CU > 90% quota | Alchemy Growth ou queries batch nocturne | +45 €/mois |
| DuckDB rame sur > 10M trades | MotherDuck ou ClickHouse Cloud Dev | +25 € ou variable |
| R2 > 10 GB | R2 pay-per-use | +1-5 € |
| VPS saturé (RAM > 3.5 GB, CPU > 80%) | Hetzner CX32 | +10 € |

**Cap total : 100 €/mois**. Au-delà, revue obligatoire.

### 2.4 Libs Python — versions cibles

```
# Core data
python==3.11
polars>=0.20
duckdb>=0.10
pyarrow>=14.0
pandas>=2.1

# HTTP / API
httpx>=0.26
tenacity>=8.2
py-clob-client>=0.10
web3>=6.0
eth-abi>=4.0
eth-utils>=3.0

# Telegram
python-telegram-bot>=20.0

# LLM
anthropic>=0.40

# Scheduling
apscheduler>=3.10

# Storage
boto3>=1.34  # R2 via S3-compatible API

# Config
pydantic>=2.5
pydantic-settings>=2.1
python-dotenv>=1.0

# Logging
structlog>=24.1
sentry-sdk>=1.40  # optionnel

# ML / stats
scipy>=1.11
statsmodels>=0.14  # FDR BH
scikit-learn>=1.3
networkx>=3.2  # clustering Victor M10

# Dashboard
streamlit>=1.30
plotly>=5.18

# Dev
pytest>=7.4
pytest-asyncio>=0.23
ruff>=0.1
mypy>=1.8
```

### 2.5 Structure repo cible

```
polymarket-bot/
├── README.md
├── RUNBOOK.md
├── GATES.md                      # log des decision gates franchis
├── pyproject.toml
├── .env.example
├── .gitignore
├── config/
│   ├── thresholds.yaml
│   ├── cex_hot_wallets.yaml      # M9
│   └── tracked_wallets_seed.yaml
├── migrations/
│   ├── 001_initial_schema.sql
│   ├── 002_proxy_eoa.sql         # M3
│   ├── 003_alert_outcomes.sql    # M6
│   ├── 004_wallet_metrics.sql    # M7
│   ├── 005_cex_funding.sql       # M9
│   └── 006_wallet_clusters.sql   # M10
├── src/polybot/
│   ├── settings.py
│   ├── db/
│   ├── ingestion/
│   ├── indexers/
│   ├── enrichment/
│   ├── components/
│   │   ├── c1_sharp_money.py
│   │   ├── c2_informed_trading.py
│   │   └── c3_resolution_risk.py
│   ├── orchestrator/
│   ├── telegram/
│   └── dashboard/
├── scripts/
│   ├── backfill_historical.py
│   ├── seed_tier_a.py
│   ├── restore_from_backup.py
│   └── validate_clustering.py    # M10
├── tests/
│   ├── unit/
│   └── integration/
└── notebooks/
    ├── 01_pilote_iran_cluster.ipynb       # phase C
    ├── 02_analyse_alert_outcomes.ipynb    # post-shadow
    ├── 03_calibration_victor.ipynb        # M10 session 1
    └── 04_rescoring_after_live.ipynb      # M11
```

---

## 3. Modèle de données

### 3.1 Stratégie globale

DuckDB hot (`/data/pm.duckdb`) pour < 90 jours. Parquet cold partitionné par mois dans `/data/parquet/<table>/<YYYY-MM>/`. **R2 pour snapshot CLOB historique** (le moat).

Job batch hebdomadaire `cold_migration` : déplace rows > 90j vers Parquet cold, DELETE de DuckDB. Queries analytiques > 90j via `DuckDB ATTACH` sur Parquet.

### 3.2 Tables créées par milestone

| Milestone | Tables créées |
|---|---|
| M1 | `markets`, `trades`, `wallets`, `alerts`, `kill_switches`, `audit_log`, `rate_limit_counters`, `tracked_wallets`, `bankroll_state`, `resolution_risk_cache` |
| M3 | `proxy_eoa_map`, `resolutions`, `trades_all` |
| M5 | `positions` (si nécessaire pour C3) |
| M6 | `alert_outcomes` — critique pour shadow mode |
| M7 | Extension `wallet_metrics` avec features diversification |
| M9 | `cex_hot_wallets`, `cex_funding_map` |
| M10 | `wallet_clusters`, `wallet_cluster_members` |

### 3.3 Schémas clés (nouveaux / modifiés)

**`alert_outcomes` (M6)** — critique pour shadow mode et ajustement 1
```sql
alert_id                VARCHAR PRIMARY KEY REFERENCES alerts
resolved_at             TIMESTAMP
resolution_outcome      VARCHAR    -- 'YES' ou 'NO' final
was_direction_correct   BOOLEAN
realized_pnl_usd        DECIMAL(18,2)
price_at_resolution     DECIMAL(6,4)
time_to_resolution_hours  INTEGER
operator_traded         BOOLEAN
operator_size_usd       DECIMAL(18,2)
shadow_pnl_simulated    DECIMAL(18,2)  -- P&L simulé au sizing suggéré
```

Le champ `shadow_pnl_simulated` est calculé automatiquement à la résolution. Indispensable en shadow mode.

**`wallet_metrics` extension (M7)**
```sql
-- Colonnes ajoutées aux colonnes phase A
nb_markets_lifetime     INTEGER
nb_categories_active    INTEGER
pct_geopolitical        DECIMAL(5,4)
pct_sports              DECIMAL(5,4)
pct_crypto              DECIMAL(5,4)
pct_politics            DECIMAL(5,4)
pct_other               DECIMAL(5,4)
still_active_post_last_event  BOOLEAN
first_trade_date        TIMESTAMP
last_trade_date         TIMESTAMP
pnl_lifetime_usd        DECIMAL(18,2)
diversity_score         DECIMAL(5,4)
```

**`cex_hot_wallets` (M9)**
```sql
address                 VARCHAR PRIMARY KEY
exchange                VARCHAR
label                   VARCHAR
added_at                TIMESTAMP
verified_source         VARCHAR
is_active               BOOLEAN
```

**`cex_funding_map` (M9)**
```sql
wallet_address          VARCHAR
deposit_address         VARCHAR
hot_wallet_address      VARCHAR REFERENCES cex_hot_wallets
PRIMARY KEY (wallet_address, deposit_address)
first_funding_tx        VARCHAR
first_funding_amount    DECIMAL(18,6)
first_funding_block     BIGINT
first_funding_ts        TIMESTAMP
hops_to_hot_wallet      INTEGER
confidence_score        DECIMAL(3,2)
computed_at             TIMESTAMP
```

**`wallet_clusters` + `wallet_cluster_members` (M10)**
```sql
-- wallet_clusters
cluster_id              VARCHAR PRIMARY KEY
member_count            INTEGER
computed_at             TIMESTAMP
method                  VARCHAR    -- 'victor_deposit_reuse', 'manual'
edge_count              INTEGER
confidence_score        DECIMAL(3,2)
last_joint_activity_at  TIMESTAMP

-- wallet_cluster_members
address                 VARCHAR
cluster_id              VARCHAR REFERENCES wallet_clusters
joined_at               TIMESTAMP
PRIMARY KEY (address, cluster_id)
```

**`clob_orderbook_snapshots` (M1, cold only R2)**
Schéma Parquet partitionné par `YYYY-MM-DD/HH.parquet` :
```
condition_id, token_id, snapshot_ts, best_bid, best_ask, midpoint,
spread, bid_depth_1pct, ask_depth_1pct, volume_1h
```
~500 marchés × 2 tokens × 24h × 365j = 4.4M lignes/an, ~150 MB/an compressé. *Note v2.1 : ce volume théorique (top-500) est revu à la baisse en §3.4 — le scope effectif est top-150 (~1.3M lignes/an, 10-50 GB/an).*

### 3.4 Stratégie de snapshot CLOB (le moat)

**Scope** : top-150 marchés actifs sélectionnés sur `volume_24h > $50K` (tri `volume_24h` desc via Gamma). Refresh de la sélection toutes les 6h pour suivre la rotation des marchés actifs. Pour chaque marché, les 2 tokens YES/NO.

*Rationale du choix top-150 (vs top-500 envisagé en v2.0)* : un top-500 produirait ~4.4M snapshots/an et saturerait le R2 free tier (10 GB) en quelques mois. Tracker les marchés à < $50K de volume apporte une valeur marginale — l'edge se joue sur les marchés liquides. Le top-150 capture 90%+ du signal utile tout en restant dans R2 free 6-12 mois.

**Fréquence** : toutes les heures.

**Contenu** : best bid, best ask, midpoint, spread, bid depth cumulée à -1% midpoint, ask depth à +1%, volume horaire. Via CLOB `/book?token_id=...` (public).

**Stockage** : Parquet directement sur R2 via `boto3`. Format `snapshots/YYYY-MM-DD/HH.parquet`, compressé zstd.

**Script** : `src/polybot/indexers/clob_snapshot.py`, dédié, indépendant du reste. Tourne même si le bot est down.

**Volume estimé** :
- Snapshots : 150 × 2 tokens × 24h × 365j ≈ 1.3M lignes/an
- Storage : 30-150 MB/jour selon volatilité contenu, soit ~10-50 GB/an
- R2 free (10 GB) OK pour 6-12 mois selon le rythme effectif

**Stratégie quand R2 free sature** (probablement vers M+9 à M+12) :
- Option A : compactor qui archive les marchés résolus depuis > 90j vers un format plus compressé (ou les supprime si peu d'intérêt analytique)
- Option B : passage R2 plan payant ($0.015/GB/mois, soit ~1 € pour 50 GB) — toujours bien sous le cap 100 €/mois

**Valeur 12-18 mois** : le moat reste pleinement valide. Le top-150 capture 90%+ du signal utile (gros marchés liquides où se joue l'edge réel). Seul dataset order book Polymarket granulaire hors Polymarket eux-mêmes.

---

## 4. Les 12 milestones

### Principe des decision gates

Entre chaque milestone, un **decision gate** : bilan écrit obligatoire dans `GATES.md` répondant à 3-5 questions méthodologiques. Pas de passage au milestone suivant sans gate validé. Objectif : forcer la digestion, empêcher de passer au suivant par inertie de code.

Format du gate :

```markdown
## Gate M[N] — [nom]

Date :
Sessions passées sur M[N] :
Lignes de code ajoutées :

### Questions méthodologiques

1. [Question 1] — Réponse :
2. [Question 2] — Réponse :
3. [Question 3] — Réponse :

### Décisions prises
- [Décision + motivation]

### Backlog créé (à traiter plus tard)
- [Item]

### ADRs ajoutés
- [ADR-XXX — titre]

### GO/NO-GO M[N+1] :
```

Si un gate est NO-GO, on itère sur M[N] ou on descope vers post-MVP. Un gate peut aussi aboutir à un "GO conditionnel" (bug connu + mitigation planifiée).

---

## Bloc 1 — MVP (M1 à M6)

Objectif du bloc : bot minimal qui émet des alertes C1+C2+C3 de base, snapshot CLOB qui tourne, infrastructure robuste. À la fin de M6 : shadow mode démarre.

---

### M1 — Fondations infra + snapshot CLOB en prod

**Objectif** : VPS opérationnel, repo initial, DB schema, snapshot CLOB qui tourne en prod **avant la fin du milestone**.

**Livrables** :
1. VPS Hetzner CX22 provisionné, Ubuntu 24.04, SSH hardened (key-only, UFW, fail2ban)
2. Repo `polymarket-bot` GitHub privé, `pyproject.toml`, structure §2.5, `.env.example`
3. CI minimal GitHub Actions : lint (ruff), tests unitaires (pytest)
4. DuckDB schema via migration `001_initial_schema.sql`
5. Bucket R2 Cloudflare créé, accès API configuré
6. **`indexer_clob_snapshot` en prod** : systemd timer hourly, snapshot CLOB `/book`, écrit Parquet R2. Sélection des marchés à snapshotter :
   - **Critère** : top-150 marchés tri `volume_24h` descendant via Gamma API, filtre `volume_24h > $50K` (les deux conditions : on prend les 150 premiers du tri qui passent aussi le filtre — donc en pratique souvent < 150 si peu de marchés dépassent le seuil)
   - **Refresh** : sélection recalculée toutes les 6h via job dédié `refresh_snapshot_universe`. La liste active des `condition_id` à snapshotter est stockée dans une table légère `snapshot_universe` (timestamp + array de condition_ids), consommée par `indexer_clob_snapshot` à chaque tick horaire
   - **Rationale du refresh 6h vs daily** : les marchés à fort volume tournent vite (un marché politique peut exploser en 24h sur breaking news), un refresh quotidien rate ces fenêtres ; un refresh horaire est inutile et coûte des appels Gamma. 6h est le compromis
7. Heartbeat minimal : script `healthcheck.py` qui pousse heartbeat dans #ops toutes les 6h
8. README setup reproducible

**Critères de validation** :
- VPS SSH accessible, systemd green
- CI verte sur PR test
- `duckdb /data/pm.duckdb "SHOW TABLES"` retourne tables attendues
- R2 : ≥ 4 snapshots complets après 4h de run
- Script `validate_snapshot.py` : un snapshot récent contient ~300 rows (150 × 2 tokens) avec `best_bid`, `best_ask` non-null
- Sélection top-150 effectivement filtrée sur `volume_24h > $50K` (vérifier que tous les marchés snapshottés sont au-dessus du seuil)

**Decision gate M1 → M2** :
1. La stratégie snapshot R2 tient-elle le volume réel observé ? (Extrapoler sur 12 mois, vérifier < 10 GB free tier)
2. Y a-t-il eu un échec de snapshot sur les 48h de run ? Si oui, nature (rate limit, API, bug) et mitigation ?
3. Le heartbeat fonctionne-t-il, ou bruit > rassurance ?
4. ADR à figer (choix VPS provider, format Parquet, partitionnement) ?

---

### M2 — Indexers de base + seed list Tier A

**Objectif** : les 2 indexers critiques alimentent DuckDB en continu. Seed list finalisée.

**Livrables** :
1. `indexer_markets_gamma` — polling 15 min, upsert `markets`, pagination + rate limit
2. `indexer_trades_dataapi` — polling 60s sur 15 wallets Tier A, insert `trades`, dédup `(tx_hash, log_index)`
3. Seed list Tier A finalisée : 15 wallets dans `config/tracked_wallets_seed.yaml` avec address, source, confidence (A1/A2), notes
4. Script `scripts/seed_tier_a.py`
5. Tests d'intégration : mock APIs
6. Logs structurés `/var/log/polybot/`

**Critères de validation** :
- Après 24h : `COUNT(markets)` > 10 000
- Après 24h avec Tier A actif : `COUNT(trades)` > 10
- `COUNT(tracked_wallets WHERE tier='A')` = 15
- Logs < 1% erreurs / 24h

**Decision gate M2 → M3** :
1. La seed list est-elle défendable ? Pour chaque wallet, je peux justifier en 1 phrase pourquoi Tier A
2. Rate limit Data API tient à 60s × 15 wallets ? Marge si on passe à 30 wallets ?
3. Ai-je repéré des patterns inattendus dans les données brutes qui devraient modifier le plan aval ?
4. Un wallet Tier A silencieux > 30j ? Remplacement envisagé ?

---

### M3 — Enrichissement minimal : proxy↔EOA + resolutions UMA + Goldsky

**Objectif** : couche d'enrichissement critique pour métriques per-user correctes.

**Livrables** :
1. `indexer_proxy_factory` — scan events `ProxyCreation` 2 factories (Safe Proxy + Polymarket Custom), mapping `proxy_eoa_map`. Backfill initial ~100k proxies + incrémental horaire
2. `indexer_resolutions_uma` — polling horaire RPC Alchemy, events `ProposePrice`/`DisputePrice`/`Settle`, insert `resolutions`
3. `indexer_onchain_goldsky` — polling horaire, subgraph Polymarket, enrichit `trades_all`
4. Job batch `compute_proxy_eoa_map` 6h pour maintenance

**Critères de validation** :
- `COUNT(proxy_eoa_map)` > 100 000 après backfill
- `COUNT(resolutions)` > 100 après 48h
- Test end-to-end : sur un wallet Tier A, EOA owner correctement résolu
- Pas de doublon proxy_address

**Decision gate M3 → M4** :
1. Les 2 factories couvrent-elles 100% des wallets Polymarket, ou proxies hors couverture ?
2. Alchemy CU consommé par backfill : % du quota mensuel ? Trajectoire soutenable ?
3. Goldsky stable à fréquence horaire ?
4. `trades_all` grossit comme prévu ? Projection 90j ?

---

### M4 — Bot Telegram + C1 Sharp Money Copy

**Objectif** : bot Telegram opérationnel + C1 émet des alertes (d'abord #ops en dry run, puis #alerts fin de M4).

**Livrables** :
1. Bot Telegram connecté groupe privé avec topics (#alerts, #ops, #errors, #risk)
2. Commandes :
   - `/status`, `/bankroll` (avec `set`), `/help`, `/recent [component]`
3. Module `c1_sharp_money.py` :
   - Listener polling DuckDB chaque minute
   - Filtre `size_usd ≥ 500`, `liquidity_market ≥ 5000`
   - Dédup `(wallet, market, side)` 30 min
   - Appel C3 **en placeholder** (`risk_score=0.3` en dur, vrai C3 en M5)
   - Payload d'alerte format §9.2
4. Module `sizing.py` : `quarter_kelly` cappé 3% bankroll et 5% liquidité marché
5. `bankroll_state` initialisé manuellement
6. Mode dry run → alertes dans #ops pendant validation

**Critères de validation** :
- Trade test Tier A → alerte #ops en < 2 min
- Format alerte lisible, tous champs présents
- Dédup OK
- Commandes fonctionnent
- Test injection : insérer row `trades` → alerte émise

**Decision gate M4 → M5** :
1. Format d'alerte lisible à 3h du matin sur mobile ? (Test réel)
2. Seuil `size_usd ≥ 500` calibré pour cette seed list ? Certains Tier A tradent plus petit ?
3. Faux positifs évidents (bug, dédup qui saute) à fixer avant M5 ?
4. `/status` donne vraiment l'info utile en cas d'incident ?

---

### M5 — C3 Resolution Risk Filter

**Objectif** : C3 opérationnel, appelé automatiquement par C1, disponible via `/risk`.

**Livrables** :
1. Module `c3_resolution_risk.py` :
   - Étage 1 LLM : prompt structuré Claude Haiku, output JSON `{ambiguity_score, reasons, red_flags}`. Cache permanent `resolution_risk_cache`
   - Étage 2 rules : `dispute_rate_by_category`, `liquidity_vs_bond_ratio`, `oracle_source_reliability`
   - Score composite `0.5 * llm + 0.3 * rules + 0.2 * oracle`. Catégorie LOW/MEDIUM/HIGH/CRITICAL
2. Commande `/risk <url_ou_slug>` : parse URL → `condition_id` → pipeline → réponse < 5s
3. Intégration C1 : chaque alerte C1 appelle C3 réel (remplace placeholder M4)
4. Fallback : si Haiku down, rules-only + flag `llm_unavailable=true`
5. Test sur `markets_disputed.csv` phase C : Zelensky, Ukraine minerals, Barron Trump → HIGH ou CRITICAL

**Critères de validation** :
- `/risk <url>` < 5s
- Cache : 2ème appel même marché = 0 LLM
- 3 cas historiques sortent HIGH/CRITICAL (100% sur CRITICAL)
- Alertes C1 incluent verdict C3 non-placeholder
- Coût LLM cumulé M5 < 0.50 €

**Decision gate M5 → M6** :
1. Prompt Haiku a-t-il bien classé les 3 cas historiques ? Si un a raté, pourquoi et fix ?
2. Pondération 50/30/20 défendable après tests, ou déjà ajuster ?
3. Cas de figure où Haiku hallucine visiblement ?
4. Cache permanent vraiment permanent, ou prévoir invalidation (question éditée Polymarket) ?
5. ADR à logger : choix Haiku vs alternatives ?

---

### M6 — C2 MVP + alert_outcomes + promotion shadow mode

**Objectif** : C2 MVP + table `alert_outcomes` remplie automatiquement + **bascule shadow mode** avec promotion #alerts.

**Livrables** :
1. Materialized view `markets_hot` (recalcul 5 min) : volume 1h > 1000 $ OU move > 300 bps 1h OU résolution < 72h
2. Module `c2_informed_trading.py` MVP :
   - 7 features (`shared_cex_deposit_ratio` reporté M9)
   - Score règles : `fresh > 0.5` AND `top5 > 0.7` AND `time_to_event < 48h` AND `niche_market_flag` → alerte
   - Dédup 6h/marché, cap 2/h 5/jour
3. Indexer `prices_1m` pour `volume_zscore_robust` et `price_momentum_1h` : polling CLOB `/midpoint` marchés hot chaque minute
4. Table `alert_outcomes` + job `log_alert_outcomes` daily : enrichit alertes passées avec `resolution_outcome`, `was_direction_correct`, `price_at_resolution`, `shadow_pnl_simulated`
5. **Promotion shadow mode** : alertes C1 et C2 dans #alerts. `operator_traded=false` partout
6. Résumé quotidien #ops : "X alertes hier, Y résolues, Z% direction correcte, shadow P&L cumulé W $"
7. **Alignement directionnel minimal v0** (anticipation ajustement 4 — précédemment planifié M11) :

   Pour chaque alerte C2 émise, calcul d'un signal `price_momentum_alignment` :

   1. Récupérer le mouvement de prix du token concerné sur les 4h précédant le trade flaggé (delta entre prix t-4h et prix au moment du trade)
   2. Comparer avec la direction du trade :
      - Si trade BUY YES et `price_momentum > +1%` : `alignment_score = +1` (informé probable, suit le mouvement)
      - Si trade BUY YES et `price_momentum < -1%` : `alignment_score = -1` (contrariant probable, va contre le mouvement)
      - Si flat (-1% ≤ momentum ≤ +1%) : `alignment_score = 0` (neutre)
      - Symétrique pour BUY NO
   3. Inclure `price_momentum_alignment` dans le payload de l'alerte Telegram, en information visible (mais **pas filtrante en v0**)
   4. Logger systématiquement dans nouvelle colonne `alerts.alignment_score`

   *Pourquoi v0 minimal et non filtrant* : on log mais on ne pénalise pas encore le score composite, parce que les contrariants vraiment informés peuvent bouger le marché eux-mêmes (le momentum est endogène). On accumule des données, on observe la corrélation `alignment_score` vs `outcome`, et en M11 on calibre la pondération empirique.

   *Limitation acceptée et documentée* : le `price_momentum` est une approximation grossière du sentiment marché. Une vraie détection d'alignement nécessite news + sentiment + cross-marchés corrélés (M11).

   *Migration DB requise* : ajouter colonne `alignment_score INTEGER` à la table `alerts` (peut être NULL pour les alertes pré-M6 si rétrocompat nécessaire — sinon table créée propre dès M1 avec champ NULLable).

**Critères de validation** :
- Scan C2 5 min stable, durée < 30s
- ≥ 1 alerte C2 sur 48h (sinon recalibrer avant shadow)
- 8 features (les 7 prévues + `alignment_score`) sans NaN silencieux
- `alert_outcomes` peuplée pour ≥ 1 alerte résolue
- `alignment_score` rempli (valeur dans {-1, 0, +1}) pour 100% des alertes C2 émises
- Résumé quotidien apparaît

**Comment se passe l'entrée en shadow mode concrètement**

Cette section décrit la routine opérationnelle qui démarre une fois le gate M6 validé. C'est important parce que shadow mode ≠ "le bot tourne tout seul, je reviens dans 4 semaines" — il y a une routine humaine qui en fait une vraie phase d'observation active.

*Bascule technique* :
- Au moment où le gate M6 est validé (ADR documenté), exécuter `/toggle c1_channel alerts` et `/toggle c2_channel alerts` dans Telegram. Les nouvelles alertes basculent immédiatement de #ops vers #alerts.
- Date de bascule notée dans `GATES.md` (champ "Shadow mode démarré le : YYYY-MM-DD"). C'est cette date qui sert de référence pour le décompte des 4 / 8 / 12 semaines calendaires (cf §6.3 et amendment 1).
- `bankroll_state.shadow_mode_active = true` activé en DB pour bloquer toute commande de trade côté opérateur (ceinture + bretelles : même si `operator_traded=false` est le défaut, la flag DB est une sécurité supplémentaire).

*Routine quotidienne pendant shadow* (~2-4h/semaine total) :

1. **Matin (5 min)** — check du résumé quotidien #ops émis automatiquement par `log_alert_outcomes`. Identifier rapidement : nb d'alertes la veille, dont combien résolues, % direction correcte, shadow P&L cumulé. Si rien d'anormal, on passe.

2. **À chaque nouvelle alerte (5-10 min/alerte)** — lecture de l'alerte sur mobile, annotation rapide manuelle dans `GATES.md` section "Shadow log" :
   - alert_id
   - Mon ressenti subjectif : aurais-je tradé cette alerte si j'étais en live ? (oui / non / hésitant)
   - Pourquoi : 1 phrase
   - Si oui, à quel size ? (estimation rapide)
   
   Cette annotation manuelle est **critique** : c'est la seule façon de mesurer rétroactivement à la sortie de shadow le "decision quality" — pas seulement la perf brute du bot, mais l'écart entre ce que le bot propose et ce qu'un humain qualifié déciderait. Si le bot émet 30 alertes en 4 sem mais que je n'aurais tradé que 5, c'est une info précieuse pour M11/M12.

3. **Hebdomadaire dimanche soir (30 min)** — revue notebook `02_analyse_alert_outcomes.ipynb`. Analyse sommaire :
   - Distribution des `alignment_score` (-1, 0, +1) — y a-t-il un biais évident ?
   - Corrélation `alignment_score` vs `was_direction_correct` sur les alertes résolues — émerge-t-elle déjà ?
   - Précision empirique cumulée par composant
   - Identification de pattern parmi les alertes "j'aurais pas tradé" (matching avec features qui distinguent)

4. **Continu** — si quelque chose casse (heartbeat manquant > 12h, indexer en erreur dans #errors), intervention. Mais en théorie, c'est rare.

*Critères de check intermédiaires* (engagement à respecter, pas optionnel) :
- **Sem 4 shadow** : check de santé. Si < 5 alertes émises au total, investigation obligatoire (cf protocole R-O7 §8.3 ajusté). Pas encore de gate dur sur la précision (échantillon trop petit).
- **Sem 8 shadow** : check méthodologique. Si < 15 alertes résolues OU precision C2 empirique < 25% : déclencher pré-réflexion sur l'escape valve M12 (ne pas attendre 12 semaines pour commencer à réfléchir aux 3 options).
- **Sem 12 shadow** : escape valve activée formellement si critères toujours pas atteints (cf amendment 1 et gate M12).

*Discipline mentale* : la grosse tentation pendant shadow est de "trader juste cette alerte qui a l'air vraiment belle". **Règle non-négociable** : zéro trade. Une seule entorse rend invalide toute mesure de précision empirique sur les semaines suivantes. Si l'envie est forte, écrire le trade hypothétique dans `GATES.md` section "Shadow log" — c'est cathartique et ça enrichit l'analyse rétrospective.

**Decision gate M6 → shadow mode actif + M7** :

**Le gate le plus important.** Point de bascule prod shadow.

1. Les 8 features C2 (7 prévues + `alignment_score`) toutes valides empiriquement (pas de distribution aberrante) ?
2. Seuil composite 4/4 donne 0-3 alertes/semaine en projection, ou 0 / >10 (recalibrer) ?
3. Shadow P&L simulé bien calculé : je sais reproduire à la main l'algo pour 1-2 alertes ?
4. `log_alert_outcomes` traite correctement les marchés neg-risk (3+ outcomes) ou limiter aux binaires pour l'instant ?
5. **Engagement explicite** : shadow mode démarre aujourd'hui, je ne trade aucune alerte jusqu'à ≥ 4 sem calendaires + ≥ 15 alertes résolues + precision ≥ 40%. Règle, pas guideline.
6. Le `alignment_score` affiché dans les alertes est-il intuitivement cohérent avec mon ressenti sur 3-5 alertes manuelles ? Si non, bug probable de calcul.
7. La routine quotidienne shadow est-elle réaliste pour mon emploi du temps personnel ? Suis-je prêt à 2-4h/semaine d'observation active ?
8. Si critères passage live (§6) non atteints après 4 sem, extension 2-4 sem ou descope.

---

## Bloc 2 — MVP enrichi (M7 à M9)

Objectif : intégrer les ajustements phase C dont la méthodologie est validée. Le bot tourne en shadow pendant ce bloc.

---

### M7 — Ajustement 2 : Features diversification + pénalité C2

**Objectif** : intégrer pénalité "anti-sharp" au scoring C2 pour éviter de flagger sharps géopolitiques actifs comme insiders.

**Livrables** :
1. Extension `wallet_metrics` avec features diversification (§3.3)
2. Job batch weekly `compute_wallet_metrics` : hebdomadaire pour wallets 90j actifs. Tourne dimanche soir
3. Fonction `compute_diversity_score(wallet_metrics) → float` : composite pondéré
4. Modification `c2_informed_trading.py` :
   - Calcul `diversity_score_top5` : moyenne `diversity_score` top-5 traders marché
   - Pénalité : si `diversity_score_top5 > seuil_sharp` (calibrer sur 4-5 sharps connus), score C2 -= 1
   - Ajout `c2_score_breakdown` JSON dans `alerts`

**Critères de validation** :
- `wallet_metrics` peuplée pour wallets 90j actifs
- Test manuel : Domer, Aenews2, Beachboy4 ont `diversity_score > seuil` et **ne sont pas** flaggés en C2
- Sur pilote Iran (si data dispo), les 5 wallets GT restent flaggés malgré pénalité (ils ont `diversity_score` bas — test que la pénalité discrimine)

**Decision gate M7 → M8** :
1. `seuil_sharp` calibré sur combien de sharps ? Robuste si on ajoute un sharp supplémentaire ?
2. Pénalité -1 point bonne magnitude, ou -0.5 / -2 ?
3. `c2_score_breakdown` permet vraiment de diagnostiquer pourquoi alerte sortie ? Test sur 3 alertes passées
4. Des shadow alertes M6 auraient été différentes avec cette pénalité ? Combien ?

---

### M8 — Orchestrateur complet + dashboard + alignement post-résolution

**Objectif** : robustesse opérationnelle + observabilité + layer post-résolution ajustement 1.

**Livrables** :

Partie A — Orchestrateur :
1. Module `kill_switch.py` : flags `c1_off`, `c2_off`, `c3_off`, `trading_off`. Commande `/toggle`
2. Module `rate_limits.py` : compteurs par (composant, heure)/(jour). Limites C1 10/h 40/j, C2 2/h 5/j, `/risk` 20/h 100/j, LLM 50/h 200/j
3. Circuit breakers :
   - Indexer erreur > 10 min → auto-OFF + #errors
   - > 5 erreurs 500 consécutives → backoff 5 min
   - Coût LLM mois > 3 € → C3 LLM OFF, rules-only
   - DB > 80% disque → alerte + pause backfill
4. Graceful degradation : C1 sans Goldsky = CLOB-only, C3 sans LLM = rules-only
5. Audit log : toggle/kill/modif seuil/ajout wallet dans `audit_log`

Partie B — Dashboard Streamlit (local, SSH tunnel) :
1. Page Ops : état indexers, dernières alertes, kill switches, rate limits, coûts cumulés
2. Page Wallets Tier A : leaderboard manuel, trades récents, métriques
3. Page Alertes : historique, filtre composant, statuts outcomes
4. Page Performance : P&L shadow cumulé (simulé), P&L réel si renseigné, precision empirique

Partie C — Alignement post-résolution (ajustement 1, layer 1) :
1. Dans `log_alert_outcomes`, calcul `direction_alignment_retroactive` : `outcome_traded` vs `resolution_outcome`
2. Rapport hebdo auto #ops : "Cette semaine, N alertes résolues, K% direction correcte. Par composant : C1 A%, C2 B%"

**Critères de validation** :
- Test `/toggle c1 off` → injection trade Tier A → pas d'alerte + log `audit_log`
- Test 50 erreurs 500 simulées → circuit breaker
- Test coût LLM > 3 € forcé → C3 rules-only
- Dashboard accessible `ssh -L 8501:localhost:8501 vps`
- Rapport hebdo émis dimanche

**Decision gate M8 → M9** :
1. Kill switches testés sous charge ou à vide seulement ?
2. Top-3 risques opérationnels NON couverts par circuit breaker M8 ? En ajouter ?
3. Dashboard consultable mobile ou desktop seulement ? Impact réactivité incident ?
4. Rapport hebdo utile tel quel, ajouter/retirer métriques ?
5. Après N semaines shadow, précision empirique C1/C2 cohérente (C1 ≥ 50%, C2 ≥ 30%) ou loin plan ?

---

### M9 — Ajustement 4 : CEX funding source detection

**Objectif** : brancher `shared_cex_deposit_ratio` dans C2, activer critère manquant le plus discriminant.

**Livrables** :
1. `config/cex_hot_wallets.yaml` : ~50 adresses hard-codées (Binance, Coinbase, OKX, Kraken, Bybit, Kucoin). Sources Arkham + Etherscan. Versionné Git, maintenance trimestrielle
2. Chargement en base `cex_hot_wallets`
3. `indexer_cex_funding` : pour chaque wallet nouveau `trades_all`, trace 2 premiers hops funding entrant via Alchemy. Remplit `cex_funding_map`
4. Backfill initial : tracer funding des ~50 top wallets actuels (Tier A + top traders 30j) pour baseline
5. Modification `c2_informed_trading.py` :
   - Calcul `shared_cex_deposit_ratio` : parmi top-5 traders 1h, % partageant deposit address CEX forwardant même hot wallet exchange
   - Réintégration score composite : `niche_market_flag OR shared_cex_deposit_ratio > 0.3`
6. Test non-régression pilote Iran : 4+ wallets GT doivent partager même deposit Binance

**Critères de validation** :
- `cex_funding_map` remplie Tier A + top traders 30j
- Test Iran : ≥ 4/7 GT ont `hot_wallet_address` = Binance confirmé
- Alchemy CU backfill : rapport détaillé dans gate
- En shadow, alertes C2 avec `shared_cex_deposit_ratio > 0.3` plus rares mais plus conviction (à vérifier semaines suivantes)

**Decision gate M9 → M10** :
1. Sur échantillon Iran, combien GT confirmés via CEX funding ? Si < 4, algo correct ou liste `cex_hot_wallets` incomplète ?
2. Faux positifs évidents (wallets légitimes partageant deposit Binance) ? Quel taux ?
3. Alchemy CU : trajectoire soutenable si scale à 500 wallets ? Migration Dune Plus ?
4. Fréquence maintenance trimestrielle `cex_hot_wallets.yaml` réaliste, ou automatiser ?
5. En shadow, bonus précision mesurable ? (Besoin 50+ alertes post-M9, peut-être pas atteint — gate peut accepter "à ré-examiner M12")

---

## Bloc 3 — Post-MVP avancé (M10 à M12)

Objectif : clustering Victor (avec validation), alignement directionnel temps-réel v2, polish et documentation.

---

### M10 — Ajustement 3 : Clustering Victor (avec validation méthodologique)

**Objectif** : le plus délicat. Valider méthodologiquement clustering Victor sur data Polymarket **avant** branchement prod C2.

**Approche en 2 sessions** :

**Session 1 — Notebook de calibration** (`notebooks/03_calibration_victor.ipynb`)

Objectif : trouver paramètres `amount_diff_max` et `block_diff_max` qui donnent bons clusters sur corpus validé, avant coder prod.

1. Dataset de calibration :
   - **Cluster positif 1** : 7 wallets Iran (rapport 3) — devraient être 1 cluster
   - **Cluster positif 2** : 4-11 wallets Théo (rapport 3) — devraient être 1 cluster
   - **Témoin négatif** : 50 wallets aléatoires 30j — NE DOIVENT PAS former gros cluster artificiel
2. Implémentation Victor :
   - Fetch 50 dernières tx sortantes via Alchemy par wallet
   - Identifier transferts vers addresses forwardant vers `cex_hot_wallets` (2 hops)
   - Grid search `amount_diff_max ∈ {0.001, 0.01, 0.1, 1.0}` ETH-eq et `block_diff_max ∈ {500, 1600, 3200, 10000}` blocs
   - Pour chaque combo (16) :
     - Recall cluster Iran (7 wallets dans 1 cluster ? 1.0 si oui)
     - Recall cluster Théo
     - Taille max cluster témoin (doit < 5)
3. Choix config : max recall positif + contrainte cluster témoin < 5
4. Documentation 2-3 pages dans GATES.md : ce qu'on a appris (seuils optimaux Polygon vs Ethereum, cas où Victor échoue, cas où il hallucine)

**Session 2 — Implémentation prod**

1. `indexer_clustering_victor` (job batch weekly) : tous wallets actifs 30j, config validée session 1
2. Tables `wallet_clusters` + `wallet_cluster_members` peuplées
3. Feature `cluster_co_presence` dans `c2_informed_trading.py` : pour chaque marché chaud, nb wallets même `cluster_id` dans top-10 traders
4. Bonus scoring : si `cluster_co_presence ≥ 3`, score C2 += 1
5. Seuil alerte recalibré tenant compte bonus (peut-être ≥ 4/4 ou ≥ 4.5/5 après bonus)

**Critères de validation** :
- Notebook calibration documenté, config défendable
- Cluster Iran : ≥ 5/7 GT dans 1 cluster commun
- Cluster Théo : ≥ 4 dans 1 cluster commun
- Aucun cluster témoin > 5 wallets
- En prod, après 1 run complet, taille max clusters réels < 50 (sinon algo trop loose)

**Decision gate M10 → M11** :
1. Seuils choisis Polymarket diffèrent substantiellement des valeurs littérature Ethereum ? Documenter
2. Cas où Victor échoue clairement (wallets fundés > 3 hops, bridge inter-chain) ? Quelles fractions ?
3. Bonus +1 point C2 calibré sur test (simulation 2-3 cas), ou pifomètre ?
4. Règle "cluster > 50 = suspect, on ignore" codée dans indexer ou juste documentée ?
5. ADR : pourquoi ces seuils, pourquoi cette implémentation

---

### M11 — Ajustement 1 v2 : Alignement directionnel temps-réel

**Objectif** : maintenant qu'on a (ou qu'on va bientôt avoir) ≥ 50 alertes shadow résolues avec `was_direction_correct` labellisé, construire signal d'alignement temps-réel basé sur **nos propres données**.

**Pré-requis** : ≥ 50 alertes résolues en shadow. Si non atteint, M11 différé.

**Approche** :
1. Notebook `04_rescoring_after_live.ipynb` : analyse exploratoire des 50+ alertes résolues
   - Features distinguant alertes correctes vs incorrectes ?
   - Patterns marché (momentum, spread, volume profile) corrélés à direction correcte ?
   - Patterns wallet (âge, historique catégorie) corrélés ?
2. Construction `direction_alignment_features` : 3-5 features simples et interprétables (pas de ML boîte noire v1) issues du notebook
3. Intégration C2 : à chaque scan, calcul `direction_alignment_score` top-5 traders. Bonus/malus au score composite
4. Shadow mode continu : alertes émises avec nouveau score loggées, on mesure si precision s'améliore 2-4 sem suivantes
5. ADR documentant choix features et priors empiriques

**Critères de validation** :
- ≥ 50 alertes résolues pour calibration
- Features choisies interprétables (je peux expliquer en 1 phrase pourquoi chacune contribue)
- Précision C2 projetée s'améliore ≥ 10 points (de 40 → 50%, ou 50 → 60%)

**Decision gate M11 → M12** :
1. Features alignement stables ou risque overfit sur 50 points ? Test hold-out 20% ?
2. Ai-je résisté à sur-engineerer (XGBoost sur 50 points = overfit garanti) ?
3. Gain 10 points précision mesuré ou extrapolé ? Plan mesure explicite 4 sem suivantes ?
4. Re-ouvrir seuils C2 pour compenser filtre additionnel (sinon recall s'effondre) ?

---

### M12 — Polish, documentation, préparation live limité

**Objectif** : bot prêt pour live limité. Runbook complet, tous TODO résolus, revue sécurité.

**Livrables** :
1. `RUNBOOK.md` complet :
   - Redémarrage bot, kill switches, ajout wallet Tier A, restore backup, rollback
   - Que faire si : indexer down, LLM indisponible, disque plein, Telegram banni, Polymarket ban wallet
2. `README.md` setup from scratch reproducible
3. Tests end-to-end complets : injection trade Tier A → C1 → C3 → dashboard → alerte mobile
4. Fixups backlog `GATES.md` : tous items critiques résolus ou reportés v2 explicitement
5. Revue sécurité :
   - Permissions `.env` 600
   - Pas de secrets en logs ni Git (grep `find . -name '*.py' | xargs grep -iE 'api_key|secret|password'`)
   - Audit dépendances `pip-audit`
6. Décision **GO live limité** : critères §6 verts → go. Sinon extension shadow 2-4 sem documentée
7. Préparation live : `scripts/enable_live_limited.py` set caps ($50/trade, 1 trade max), rappelle règles #ops

**Critères de validation** :
- Runbook testé (je suis les procédures sans lire le code)
- Tests end-to-end passent
- Aucun secret clair Git (historique si possible)
- Heartbeat stable ≥ 7j consécutifs
- Revue `GATES.md` : synthèse exécutive 12 gates (1 page)

**Decision gate M12 → live limité** :

**Gate final du dev.**

1. Shadow mode depuis combien sem calendaires ? ≥ 4 sem ?
2. ≥ 15 alertes résolues shadow ? Si < 15, extension obligatoire
3. Precision C1 empirique : ≥ 40% sur sample ≥ 10 résolues ? Plancher dur
4. Precision C2 empirique : ≥ 25% sur sample ≥ 10 résolues ? Plancher dur
5. Shadow P&L simulé positif ? (Pas éliminatoire sur petit échantillon, mais à discuter)
6. Aucun crash non récupéré > 2h sur 4 dernières sem ?
7. Budget infra réel < 30 €/mois ?
8. Aucun CRITICAL C3 loupé parmi disputés shadow ?
9. Suis-je mentalement prêt à trader ? Honnêtement ? Si non, extension

Si tous critères ≥ 5 verts : GO live limité $30-50/trade.

**Escape valve méthodologique** (cf amendment 1) : si après **12 semaines calendaires de shadow et ≥ 30 alertes résolues**, les planchers de precision (C2 ≥ 25%, C1 ≥ 40%) ne sont toujours pas atteints, c'est un signal méthodologique fort. Trois options à trancher explicitement (**pas d'extension shadow par défaut**) :

1. **Ré-architecture C2 obligatoire** : intégration de l'ajustement 1 (alignement directionnel) en version sophistiquée (au-delà du `price_momentum` simple de M6 / M11), potentiellement news sentiment ou ML simple sur la base des données accumulées.
2. **Pivot scope** : abandonner C2 en v1, focus full sur C1 + C3 only, accepter le bot comme un assistant de copy-trading sharps + risk filter, sans détection insider. C1 est moins ambitieux mais beaucoup plus robuste méthodologiquement (seed-list manuelle vs détection statistique).
3. **Stop projet et capitaliser** : pivoter vers monétisation des assets accumulés (snapshot CLOB historique, wallet metrics enrichis, ground truth alertes labellisées) sous forme de dataset / API plutôt que de bot trading. Cf rapport 6 §7 pour les business models réalistes.

Décision documentée dans `GATES.md` avec ADR explicite. **Pas de continuation silencieuse en shadow** — le gate force une décision active à 12 semaines, parce que prolonger indéfiniment sans changement structurel revient à attendre que le hasard converge.

---

## 5. Récapitulatif critères de validation par composant

### 5.1 C1 Sharp Money Copy

**Fin M6 (entrée shadow)** :
- Polling 60s stable 15 Tier A ≥ 7j
- Dédup OK
- Format alerte complet
- Intégration C3 : 100% alertes C1 ont verdict non-placeholder

**Fin M12 (entrée live limité)** :
- ≥ 5 alertes C1 émises shadow
- ≥ 60% auraient été rentables (plancher 40%)
- Aucun trade Tier A > $500 raté (recall)

### 5.2 C2 Informed Trading Alert

**Fin M6 (MVP)** :
- Scan 5 min stable
- 8 features (les 7 prévues + `alignment_score`) sans NaN
- ≥ 1 alerte / 48h
- `alignment_score` rempli sur 100% des alertes C2

**Test non-régression 18 cas forensiques** (M6 ou M7) :
- Reconstituer features data archivée
- Cible recall ≥ 60% (conforme pilote)

**Fin M12** :
- ≥ 5 alertes C2 shadow
- Precision ≥ 40% (plancher 25%)
- Ajustements 1-4 intégrés (layer post-résolution obligatoire, temps-réel optionnel si M11 pas atteint)

### 5.3 C3 Resolution Risk Filter

**Fin M5** :
- `/risk` < 5s
- Cache : 2ème appel = 0 LLM
- Sur markets_disputed : 100% CRITICAL, accuracy ≥ 70%, 0 erreur 2 catégories
- Fallback rules-only OK

**Fin M12** :
- Tous marchés ayant alerté ont verdict C3
- Coût LLM < 3 €/mois
- 0 CRITICAL loupé shadow

### 5.4 Pipeline infrastructure

**Fin M12** :
- Uptime > 99% sur 2 dernières sem
- Backups quotidiens R2, restore testé
- Budget réel < 30 €/mois
- Snapshot CLOB : ≥ 30j sans trou
- DB < 5 GB

---

## 6. Stratégie de déploiement progressif

### 6.1 Phase backtest (phase C, déjà fait)

Notebook pilote Iran, E1-E6.

### 6.2 Phase dev MVP (M1-M6)

Alertes #ops (dry run) jusqu'à promotion #alerts M6. **Cap trading : 0**.

### 6.3 Phase shadow mode (démarre M6, min 4 sem calendaires)

Alertes #alerts. `operator_traded=false`. `shadow_pnl_simulated` calculé pour perf hypothétique.

**Durée minimale 4 sem calendaires** — pas milestones, temps calendaire pour résolutions.

**Routine opérationnelle pendant shadow** : décrite en détail dans la section "Comment se passe l'entrée en shadow mode concrètement" du milestone M6. En résumé : ~2-4h/semaine d'observation active (résumé quotidien + annotation des alertes au fil de l'eau + revue notebook hebdo dimanche). Shadow ≠ "le bot tourne tout seul, je reviens dans 4 semaines" — l'annotation manuelle des alertes est ce qui rend la phase exploitable a posteriori.

**Jalons de check intermédiaires** (engagement, pas optionnel) :
- **Sem 4** — check de santé (volume d'alertes), pas encore de gate dur sur précision
- **Sem 8** — check méthodologique : si < 15 alertes ou precision C2 < 25%, déclencher pré-réflexion escape valve M12
- **Sem 12** — escape valve formelle si critères toujours non atteints (cf amendment 1)

Cf protocole détaillé en R-O7 §8.3.

**Escape valve à 12 sem calendaires** (cf amendment 1 et gate M12) : si après 12 semaines de shadow et ≥ 30 alertes résolues les planchers de precision ne sont pas atteints, **pas d'extension par défaut**. Décision active obligatoire entre (a) ré-architecture C2, (b) pivot scope vers C1+C3 only, (c) stop projet et capitalisation des assets accumulés. Le détail des 3 options est dans le gate M12.

### 6.4 Phase live limité (après gate M12 validé)

Cap $30-50/trade, max 1 trade ouvert. Seulement alertes score max + C3 ≠ HIGH/CRITICAL.

**Durée minimale 4 sem calendaires**. Si 5 pertes consécutives : pause 48h, revue.

### 6.5 Phase live complet

Sizing Kelly fractionnel jusqu'à 3% bankroll. Critères : P&L positif 4 sem live limité + edge moyen > 3 cents/trade.

### 6.6 Décisions re-tuning continu

| Observation | Action |
|---|---|
| 0 alerte C1 / 2 sem | Investigation Tier A, refresh seed list |
| > 10 alertes C1 / sem | Raise `size_min` à $1000 |
| 0 alerte C2 / 2 sem | Loose seuils (majorité 3/4, time_to_event < 72h) |
| > 10 alertes C2 / sem | Strict (≥ 4/4, top5 > 0.8) |
| Precision C2 < 25% / 20 alertes | Re-investiguer features, ajouter filtre |
| C3 CRITICAL raté sur dispute réel | Post-mortem, raffiner prompt, ajouter few-shot |

---

## 7. Métriques de succès

### 7.1 Par composant

**C1** :
- Recall trades Tier A > $500 : ≥ 95%
- Precision : ≥ 60% cible, 40% plancher
- Latence alerte : < 2 min

**C2** :
- Recall backtest 18 cas : ≥ 60%
- Precision empirique : ≥ 40% cible, 25% plancher
- Faux positifs sharps : < 10% total

**C3** :
- Accuracy catégorielle markets_disputed : ≥ 70%
- Recall CRITICAL : 100%
- Coût mensuel : < 3 €
- Latence `/risk` : < 5s

### 7.2 Globales

**Court terme (3 mois post-live complet)** :
- Uptime > 99%
- ≥ 20 alertes actionnées
- P&L brut positif
- Budget < 40 €/mois
- < 5h/sem maintenance
- Aucun incident majeur (> $100 perte évitable)

**Moyen terme (6 mois)** :
- P&L net après PFU positif
- ROI annualisé 20-40%
- ≥ 3 alertes C2 haute conviction/mois
- Edge moyen > 5 cents/trade

**Long terme (12 mois)** :
- Snapshot CLOB : 1 an historique granulaire (moat établi)
- ≥ 100 alertes outcomes loggés
- P&L vs USDC yield passif : edge ≥ 10 points
- Décision v2 : leaderboard auto, anti-honeypot, auto-exec ciblé

### 7.3 Indicateurs santé opérationnelle

Dashboard Streamlit, page Ops :
- Uptime indexers (24h, 7j, 30j)
- Dernière alerte par composant
- Kill switches actifs
- Coût infra cumulé mois
- Coût LLM cumulé mois
- Taille DB + disque libre
- Dernière exécution chaque job batch

---

## 8. Risques identifiés et mitigations

### 8.1 Risques techniques

**R-T1 — APIs Polymarket changent**
- Mitigation : tests intégration hebdo, architecture modulaire, snapshot CLOB data de secours
- Plan B : fallback Dune + Goldsky
- Criticité : haute

**R-T2 — Rate limits non-documentés**
- Mitigation : backoff exponentiel M2, monitoring, circuit breaker M8
- Plan B : polling 60s → 120s ou batch 40 wallets
- Criticité : moyenne

**R-T3 — Polygon reorgs**
- Mitigation : attendre 2-3 blocks, job batch re-vérifie vs Goldsky
- Plan B : reverser alerte si reorg-out
- Criticité : basse

**R-T4 — DuckDB écriture concurrente**
- Mitigation : staging Parquet + compactor 5min
- Plan B : SQLite WAL hot path, DuckDB analytique
- Criticité : moyenne

**R-T5 — Perte données crash VPS**
- Mitigation : backups quotidiens R2, snapshot CLOB directement R2
- Plan B : restore R2, perte max 24h DuckDB, 0 perte snapshots
- Criticité : basse

### 8.2 Risques méthodologiques

**R-M1 — Overfitting 18 cas forensiques**
- Mitigation : pas grid search, priors rapports 3/4, validation train/test phase C, re-calibration post-shadow
- Plan B : retour seuils publics non tunés
- Criticité : haute

**R-M2 — Concept drift (insiders adaptent)**
- Mitigation : monitoring distributions features, re-calibration trimestrielle, outil privé
- Plan B : v2 features plus robustes
- Criticité : moyenne-haute

**R-M3 — Survivorship bias GT**
- Mitigation : ajustement 1 dual-layer M8 post-résolution + M11 temps-réel ; post 50+ alertes, GT non-biaisé
- Plan B : accepter v1 biaisée, documenter, ne pas sur-réagir aux flags avant post-résolution
- Criticité : haute (mitigation claire)

**R-M4 — Clustering Victor mal calibré (nouveau M10)**
- Mitigation : session 1 M10 = notebook calibration dédié avant prod
- Plan B : si config ne converge pas, skip clustering, C2 reste config M9 (71% recall pilote suffit v1)
- Criticité : moyenne

### 8.3 Risques opérationnels

**R-O1 — Burn-out side project**
- Mitigation : milestones sans timeline imposée, pause acceptable à tout moment, gates forcent digestion vs inertie
- Plan B : descope vers post-MVP toute brique non-critique shadow
- Criticité : moyenne (atténuée par format milestones)

**R-O2 — Perte capital live**
- Mitigation : shadow ≥ 4 sem, live limité ≥ 4 sem, cap 3% bankroll, circuit breaker 5 pertes
- Plan B : si perte > 20% capital / 30j, pause, post-mortem
- Criticité : moyenne

**R-O3 — Polymarket ban wallet**
- Mitigation : VPN résidentiel, pas de comportements sybil
- Plan B : nouveau wallet, bot sur APIs publiques (pas de VPN requis pour scraper)
- Criticité : moyenne

**R-O4 — Freeze Polymarket (hack, dispute)**
- Mitigation : self-custody Ledger dès 3000 €
- Plan B : hardware wallet, dispersion multi-wallets
- Criticité : moyenne

**R-O5 — Fiscalité mal maîtrisée**
- Mitigation : déclaration 3916-bis dès live limité, Koinly/Waltio, conseil si > 5000 €/an
- Plan B : sur-déclarer plutôt que sous
- Criticité : basse v1

**R-O6 — Data loss snapshot CLOB**
- Mitigation : heartbeat 6h, check quotidien, snapshot direct R2
- Plan B : aucun (irréparable — robustesse M1)
- Criticité : moyenne

**R-O7 — Shadow mode trop court pour valider (NOUVEAU)**
- Mitigation : 4 sem calendaires minimum, ≥ 15 alertes résolues. Règle dure
- Plan B : extension 2-4 sem sans discussion si critères non atteints en mode "presque OK". Si critères loin du compte à 12 sem, escape valve M12 (amendment 1) au lieu d'extension indéfinie

**Protocole de check intermédiaire** (engagement obligatoire, pas optionnel) :

Trois jalons calendaires comptés depuis la date de bascule en shadow (notée dans `GATES.md`) :

| Jalon | Critère | Action si critère non atteint |
|---|---|---|
| **Sem 4** | ≥ 5 alertes émises (tous composants confondus) | **Investigation obligatoire** : bug d'émission ? Heuristiques C2 trop strictes ? Marchés trop calmes (faible volatilité géopolitique) ? Issue documentée dans `GATES.md` section "Shadow check sem 4" + action corrective décidée (ex : loose seuils C2 d'un cran, ou vérifier que Tier A trade encore activement) |
| **Sem 8** | ≥ 15 alertes résolues ET precision C2 ≥ 25% (sur sample ≥ 5 résolues) | **Pré-réflexion escape valve** : pas encore d'action drastique, mais écrire dans `GATES.md` section "Pré-réflexion M12" un brouillon des 3 options de l'amendment 1 (ré-architecture C2 / pivot C1+C3 / stop projet). Identifier laquelle est la plus probable si la trajectoire ne s'inverse pas en sem 9-12. Pas de continuation silencieuse "on verra à 12" |
| **Sem 12** | ≥ 30 alertes résolues ET precision C2 ≥ 25% ET precision C1 ≥ 40% | **Escape valve M12 activée formellement** : décision active entre les 3 options de l'amendment 1, ADR documenté dans `GATES.md`. Pas d'extension shadow par défaut. La pré-réflexion sem 8 est désormais opérationnalisée |

*Pourquoi ces 3 jalons et pas un seul* :
- Sem 4 attrape les pannes silencieuses tôt (le bot ne crash pas mais émet 0 alerte = aussi inutile)
- Sem 8 donne une fenêtre de réflexion avant la décision dure (la pré-réflexion à sem 8 évite les décisions de sem 12 prises sous pression émotionnelle "j'y ai mis 3 mois je veux pas stopper")
- Sem 12 force la décision active, parce que l'expérience montre que sans contrainte forte, on prolonge ad infinitum en attendant que le hasard converge

- Criticité : moyenne

### 8.4 Risques externes

**R-E1 — Polymarket acquis / pivoté / shut EU**
- Mitigation : bot agnostique, portable Kalshi/Limitless
- Plan B : moat transférable
- Criticité : basse court terme, moyenne long terme

**R-E2 — Acquisition outil concurrent par Polymarket**
- Mitigation : outil privé, focus edge trading pas produit
- Plan B : si C2-style devient natif, pivot v2 vers autres edges
- Criticité : basse

**R-E3 — Publication heuristiques par tiers**
- Mitigation : monitoring concept drift, outil privé
- Plan B : v2 features plus robustes
- Criticité : moyenne

---

## 9. Annexes

### 9.1 Glossaire

- **CFS** : Common Funding Source (Victor 2020)
- **BSS** : Brier Skill Score
- **CLV** : Closing Line Value
- **FDR BH** : False Discovery Rate Benjamini-Hochberg
- **GT** : Ground Truth
- **HITL** : Human-in-the-loop
- **PFU** : Prélèvement Forfaitaire Unique (31.4% en 2026)
- **PSR/DSR** : Probabilistic / Deflated Sharpe Ratio

### 9.2 Template d'alerte Telegram (C1)

```
🎯 Sharp Money Alert (C1)

👤 Wallet : Domer (Tier A1)
📊 Marché : "Will <candidate> win <election>?"
💰 Trade : BUY YES
💵 Size : $1,250 @ 0.32
📈 Move : +2.1% en 15 min

⚖️ Resolution Risk : [LOW] 0.18
   └ Source reliable, aucun dispute historique

💡 Size suggéré : 45€ (2.3% bankroll, quarter-Kelly)

🔗 https://polymarket.com/event/...
⏱️ alert_id AL_2026_XX_XX_XXXX
```

### 9.3 Commandes Telegram disponibles v1

- `/status` — état indexers, dernière alerte, kill switches
- `/bankroll` — solde + update manuel
- `/risk <url_ou_slug>` — verdict C3 sur demande
- `/toggle <component> on|off`
- `/recent [component]` — 10 dernières alertes
- `/help`

### 9.4 Template `GATES.md`

À créer dès M1, remplir après chaque milestone.

```markdown
# Decision Gates log — Polymarket Bot

## Gate M1 — Fondations infra + snapshot CLOB

Date :
Sessions passées sur M1 :
Lignes de code ajoutées :

### Questions méthodologiques

1. Stratégie snapshot R2 tient-elle le volume réel ? — Réponse :
2. Échec snapshot sur 48h ? — Réponse :
3. Heartbeat bruit vs rassurance ? — Réponse :
4. ADR à figer ? — Réponse :

### Décisions prises
- 

### Backlog post-MVP
- 

### ADRs ajoutés
-

### GO/NO-GO M2 :

---

## Gate M2 — Indexers de base + seed list Tier A

[etc. pour chaque milestone]
```

---

## Annexe — Amendments post-review (v2.1)

Les 3 amendments suivants ont été ajoutés au plan v2 suite à review méthodologique. Ils ne modifient pas la structure des 12 milestones ni les decision gates existants — ils enrichissent les livrables et ajoutent une porte de sortie méthodologique au gate M12.

**Amendment 1 — Escape valve sur le gate M12**
Si après 12 sem calendaires de shadow et ≥ 30 alertes résolues les planchers de precision (C2 ≥ 25%, C1 ≥ 40%) ne sont pas atteints, décision explicite obligatoire entre 3 options : ré-architecture C2 sophistiquée / pivot scope vers C1+C3 only / stop projet et capitalisation des assets accumulés. Pas d'extension shadow par défaut.

*Sections impactées* : gate M12 (ajout du paragraphe escape valve), §6.3 Phase shadow mode (rappel de l'escape valve à 12 sem).

*Motivation* : le pilote phase C a donné precision = 50% sur le cas Iran (cas idéal documenté). Atteindre les planchers en "in the wild" peut être plus dur. Risque de boucle infinie d'extensions shadow si pas de point de décision forcé.

**Amendment 2 — Snapshot CLOB sur top-150 marchés**
Scope du snapshot CLOB ramené de top-500 à top-150 marchés actifs (sélectionnés sur `volume_24h > $50K`, refresh sélection toutes les 6h). Réduit le storage R2 par ~3, garde 90%+ du signal utile (le moat se joue sur les marchés liquides), reste dans R2 free tier 6-12 mois.

*Sections impactées* : §1.6 diagramme de flux, §3.1 note de bas de tableau, §3.4 stratégie snapshot CLOB (réécrite avec rationale, volume estimé, stratégie quand R2 sature), M1 livrables et critères de validation.

*Motivation* : top-500 produirait 4.4M snapshots/an et saturerait R2 free (10 GB) en quelques mois. Tracker les marchés < $50K de volume apporte une valeur marginale.

**Amendment 3 — Alignement directionnel minimal v0 dès M6**
Anticipation partielle de l'ajustement 4 (ex-M11) en M6 : calcul d'un signal `price_momentum_alignment` pour chaque alerte C2, **non-filtrant** (juste loggé en information visible et stocké dans `alerts.alignment_score`). Calibration empirique en M11 basée sur les données accumulées.

*Sections impactées* : §1.2 tableau d'intégration des ajustements (passage de dual-layer à tri-layer), §1.3 spec C2 (ajout 8ème feature), M6 livrables (nouveau livrable n°7), M6 critères de validation (8 features au lieu de 7), gate M6 (question 6 sur cohérence intuitive de l'`alignment_score`), §5.2 critères fin M6.

*Motivation* : le pilote phase C a démontré que sans alignement, precision C2 = 50%. Attendre M11 pour démarrer = accumulation de shadow data avec mauvaise precision = on ne peut pas distinguer "bug d'alignement" de "bug d'autres heuristiques". v0 minimal non-filtrant permet d'accumuler des données corrélées tôt sans bloquer le shadow mode.

*Limitation acceptée* : le `price_momentum` est une approximation grossière (le momentum est endogène — un contrariant informé peut bouger le marché lui-même). Une vraie détection nécessite news + sentiment + cross-marchés corrélés (M11 v1 calibré).

---

## 10. Sortie de phase B : conditions de succès

Phase B terminée quand :

1. Les 12 milestones validés avec gates verts ou descopés explicitement
2. Tous critères §5 verts
3. Shadow mode a tourné ≥ 4 sem calendaires avec ≥ 15 alertes résolues (ou escape valve M12 amendment 1 déclenchée et décision documentée)
4. Ce document à jour + `GATES.md` rempli

Puis :
- Live limité $30-50/trade ≥ 4 sem calendaires
- Live complet sizing Kelly si critères 6.5 atteints
- Après 3-6 mois live : réflexion v2 (leaderboard auto, ML alignment, anti-honeypot sophistiqué)

---

*Fin du document. Version 2.2 à lire en parallèle de `A_architecture_technique.md` et `C_synthese_pilote.md`. Mise à jour continue via ADRs et `GATES.md` en cours de dev. Le plan n'a pas de timeline calendaire — les milestones sont franchis à ta vitesse, avec gates méthodologiques entre chaque. Shadow mode démarre dès M6 en parallèle du dev M7-M12 pour accumuler data calendaire pendant le dev. v2.1 a intégré 3 amendments post-review (escape valve M12, snapshot CLOB top-150, alignement directionnel v0 dès M6). v2.2 ajoute 3 raffinements opérationnels : critère top-150 explicité dans M1, routine shadow mode consolidée (M6 + §6.3), protocole R-O7 avec 3 jalons (sem 4 / sem 8 / sem 12).*
