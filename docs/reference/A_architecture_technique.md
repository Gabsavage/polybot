# Phase A — Architecture technique du Polymarket Bot

*Document de référence pour la phase de développement. Destiné à être versionné dans les project files. Toute décision prise ici est révisable, mais toute révision doit être explicite (ADR — Architecture Decision Record — à ajouter en fin de doc).*

*Version 1.0 — avril 2026.*

---

## 0. TL;DR de l'architecture

Trois composants de signal (Sharp Money Copy, Informed Trading Alert, Resolution Risk Filter) qui consomment une couche d'ingestion commune (indexers CLOB + on-chain + metadata), persistent dans une stack locale DuckDB + Parquet hébergée sur un VPS Hetzner, et émettent vers un bot Telegram privé. Rien de tout ça n'exécute de trade ; tout est signal + sizing recommandé à destination de l'opérateur humain.

Le système tourne en **trois régimes** :
- **Temps quasi-réel** (polling 60s) pour les trades des wallets trackés et la détection d'anomalies sur marchés chauds.
- **Batch périodique** (hourly, daily, weekly) pour le backfill, le re-scoring des wallets, la constitution des leaderboards, la résolution et les métriques de perf.
- **À la demande** (commandes Telegram) pour le Resolution Risk sur un marché ciblé, le `/bankroll`, les requêtes d'investigation.

Budget cible < 30 €/mois, atteignable avec : VPS Hetzner CX22 (~5 €) + Dune Plus (49 $, optionnel mais fortement conseillé en phase de bootstrap) + Anthropic API Haiku (estimé < 3 €/mois) + RPC Alchemy free tier. Goldsky free et CLOB/Gamma/Data APIs gratuits.

---

## 1. Schéma d'architecture global

### 1.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SOURCES EXTERNES                                  │
│  Gamma API   CLOB API   Data API   Goldsky   Dune   Alchemy RPC   UMA   │
└─────┬─────────┬──────────┬──────────┬─────────┬────────┬───────────┬────┘
      │         │          │          │         │        │           │
      ▼         ▼          ▼          ▼         ▼        ▼           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   COUCHE INGESTION (indexers)                            │
│                                                                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────┐  │
│  │ markets_idx  │ │ trades_idx   │ │ wallets_idx  │ │ resolutions_idx│ │
│  │ (Gamma,15min)│ │ (CLOB,60s)   │ │ (Goldsky,1h) │ │ (UMA,hourly)   │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └───────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│           STOCKAGE — DuckDB (hot) + Parquet (cold, partitionné)          │
│                                                                          │
│   markets / trades / wallets / positions / resolutions / prices_1m       │
│   tracked_wallets / alerts / alert_outcomes / resolution_risk_cache      │
│   proxy_eoa_map / wallet_metrics / bankroll_state                        │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│ C1 Sharp Money  │  │ C2 Informed     │  │ C3 Resolution Risk  │
│ Copy            │  │ Trading Alert   │  │ Filter              │
│                 │  │                 │  │                     │
│ Poll 60s des    │  │ Scan 5min des   │  │ LLM à la création   │
│ trades des      │  │ marchés chauds  │  │ marché (cache) +    │
│ wallets trackés │  │ pour heuristics │  │ rules-based au run  │
│ anti-honeypot   │  │ Tier 1          │  │                     │
└────────┬────────┘  └────────┬────────┘  └─────────┬───────────┘
         │                    │                     │
         └────────────────────┼─────────────────────┘
                              ▼
              ┌────────────────────────────┐
              │  ORCHESTRATEUR / GARDE-FOUS│
              │  rate limits, kill switch, │
              │  dédup, sizing, logging    │
              └───────────────┬────────────┘
                              ▼
              ┌────────────────────────────┐
              │      BOT TELEGRAM          │
              │ #alerts #risk #ops #errors │
              └────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                   JOBS BATCH (cron / APScheduler)                        │
│  backfill_historical / rescore_wallets / resolve_alerts / backup /       │
│  report_daily / cleanup / dune_sync                                      │
└─────────────────────────────────────────────────────────────────────────┘

                    ┌────────────────────────────┐
                    │  DASHBOARD PERF (Streamlit)│
                    │  local, port forwardé      │
                    └────────────────────────────┘
```

### 1.2 Ce qui tourne en continu vs à la demande

**Processus persistants (daemon)** :
- `orchestrator` — le process principal, gère l'event loop, dispatch les jobs, applique les garde-fous.
- `telegram_bot` — bot python-telegram-bot en polling, reçoit les commandes, émet les alertes.
- `indexer_trades_clob` — poll les trades des wallets trackés toutes les 60s.
- `indexer_markets_hot` — scan les marchés chauds toutes les 5 min pour C2.

**Jobs batch planifiés (APScheduler ou cron)** :
- Toutes les 15 min : `sync_markets_gamma` (metadata nouveaux marchés + update prix/volume/liquidité).
- Toutes les heures : `sync_wallets_activity_goldsky`, `sync_resolutions_uma`, `compute_rolling_metrics`.
- Tous les jours : `rescore_wallet_leaderboard`, `resolve_pending_alerts`, `backup_duckdb`, `cleanup_old_snapshots`, `report_daily_perf`.
- Toutes les semaines : `rescore_all_wallets_deep`, `fdr_bh_correction_refresh`, `anti_honeypot_review`.

**À la demande** :
- `/risk <url_ou_slug>` — appel direct au composant 3.
- `/bankroll <montant>` — update du bankroll.
- `/perf [periode]` — génère un résumé de perf à partir de la table `alert_outcomes`.
- `/toggle <component>` — kill switch (voir §7).
- `/status` — santé globale (derniers polls OK, nombre d'alertes 24h, erreurs).

### 1.3 Flux de données typiques

**Flux "Sharp Money Copy"** — latence cible < 2 min du trade à l'alerte :

```
Sharp wallet place un trade on-chain
        ↓ (propagation réseau, matching CLOB, inclusion bloc Polygon ~5-30s)
Trade visible dans CLOB API /data/trades?user=... et events on-chain
        ↓ (polling 60s)
indexer_trades_clob détecte le trade, insère dans `trades`
        ↓ (trigger applicatif)
C1 lit le trade, vérifie filtres (size min, liquidité, anti-honeypot flag)
        ↓
calcule sizing recommandé (Kelly × force × liquidité)
        ↓
appelle C3.get_risk(market_id) — lit le cache, combine avec rules dynamiques
        ↓
dédup via hash (wallet, market, side, 5min-bucket)
        ↓
émet sur Telegram #alerts, logge dans `alerts`
```

**Flux "Informed Trading Alert"** — latence cible < 5 min :

```
Scan 5 min : identifier marchés "chauds" (volume 1h > seuil, prix bouge > Xbps)
        ↓
Pour chaque marché chaud, calculer features Tier 1 :
  - fresh wallets concentration (wallets < 7j)
  - shared CEX deposit address overlap
  - niche market flag (volume cumul, catégorie)
  - proximité event (resolution date - now)
  - concentration top-5 holders
        ↓
Score composite (pondération à calibrer, cf §3.C2)
        ↓
Si score > seuil ET pas d'alerte émise sur ce marché dans les dernières 6h
        ↓
appelle C3, enrichit, émet #alerts avec tag [INFORMED]
```

**Flux "Resolution Risk" à la demande** :

```
/risk https://polymarket.com/event/... reçu
        ↓
résout slug → condition_id via Gamma
        ↓
lit cache resolution_risk_cache (LLM score déjà calculé ?)
        ↓ (si miss)
appelle Claude Haiku avec question + description + resolution source
        ↓
calcule rules dynamiques (historique disputes UMA catégorie, liquidité, fenêtre)
        ↓
score composite + verdict textuel
        ↓
répond dans le thread Telegram d'origine
```

### 1.4 Principe de cohabitation des régimes

Point d'attention : le daemon temps-réel et les jobs batch partagent la même DB DuckDB. DuckDB n'est pas optimisé pour l'écriture concurrente multi-process. **Règle** : un seul process écrit à la fois. Les indexers poussent dans des tables staging (fichiers Parquet horodatés dans `/data/staging/`), et un process `compactor` les merge dans DuckDB toutes les 5 min dans une transaction. Les lectures des composants se font sur DuckDB en mode read-only attach. Alternative si ça coince : passer sur SQLite + WAL pour la hot path, garder DuckDB pour l'analytique — voir §9 questions ouvertes.

---

## 2. Sous-systèmes détaillés

### 2.A Couche ingestion / indexers

Quatre indexers, responsabilités distinctes, fréquences distinctes.

**2.A.1 `indexer_markets_gamma`** — metadata des marchés

- **Source** : Gamma API `https://gamma-api.polymarket.com/markets`
- **Fréquence** : toutes les 15 min pour les actifs, toutes les 6h pour la re-vérification des closed/archived.
- **Pagination** : `limit=500&offset=...`, politesse rate limit (sleep 500ms entre pages).
- **Volume** : ~10-15k marchés actifs, ~50k cumul. Full sync initial ~30 min, incrémental ~2 min.
- **Stockage** : table `markets`. Upsert sur `condition_id` (clé primaire). Horodatage `last_synced_at`.
- **Signal de nouveauté** : si un marché apparaît avec `condition_id` jamais vu → trigger pour C3 (LLM scoring preemptif).

**2.A.2 `indexer_trades_clob`** — trades des wallets trackés

- **Source** : CLOB `/data/trades?user=<address>` + CLOB `/trades?market=<condition_id>` pour compléter.
- **Fréquence** : 60s, polling par batches de wallets (group by 20 wallets pour ménager le rate limit).
- **Scope** : wallets dans `tracked_wallets` avec `active=true` ET marchés dans `markets_hot` (volume 1h > seuil).
- **Dédup** : trade identifié par `tx_hash + log_index` (clé primaire composite).
- **Stockage** : table `trades`. Insert-only, jamais d'update.
- **Backoff** : sur 429, backoff exponentiel 2s → 4s → 8s → cap 60s. Après 3 échecs successifs, raise en #errors.

**2.A.3 `indexer_onchain_goldsky`** — activité on-chain large

- **Source** : Goldsky subgraph `polymarket-matic/activity-polygon/prod` (GraphQL).
- **Fréquence** : toutes les heures (pour enrichir en dehors des wallets trackés, sert au re-scoring).
- **Usage** : récupérer les `FilledOrder` et `Position` sur une fenêtre glissante (dernière heure), insert dans `trades_all` (table séparée, plus large mais moins fraîche).
- **Rate limit** : Goldsky free ~50 req/s, on reste très en-deçà.
- **Fallback** : si Goldsky down, on pull Dune en mode standalone (`dune_sync` job).

**2.A.4 `indexer_resolutions_uma`** — résolutions et disputes

- **Source** : events UMA Optimistic Oracle V2 sur Polygon via RPC Alchemy, + endpoint UMA GraphQL pour enrichissement.
- **Fréquence** : toutes les heures.
- **Scope** : `ProposePrice`, `DisputePrice`, `Settle` events sur l'adapter Polymarket.
- **Stockage** : table `resolutions` avec statut (proposed, disputed, settled), timestamps, payouts.
- **Trigger** : quand `Settle` arrive sur un marché qui a produit des alertes → déclencher `resolve_alerts` pour ce marché (mise à jour `alert_outcomes`).

**2.A.5 `indexer_proxy_factory`** — mapping proxy↔EOA (dédié, important)

- **Source** : events `ProxyCreation` des factories Polymarket (Gnosis Safe Proxy Factory + factory Polymarket custom).
- **Fréquence** : toutes les heures, incrémental.
- **Logique** : pour chaque `ProxyCreation`, on capture le proxy address + le creator EOA. On joint ensuite avec les events de première tx du proxy (souvent un transfer USDC depuis l'EOA) pour confirmer le lien.
- **Stockage** : table `proxy_eoa_map`. Clé : `proxy_address`. Valeurs : `eoa_address`, `confidence_score`, `method` ("direct_factory", "deposit_address_shared", "manual").
- **Attention** : certains wallets sont des proxies de proxies, ou des multisigs. Garder la chaîne complète, pas juste EOA racine.

### 2.B Composant 1 — Sharp Money Copy

**Objectif** : émettre une alerte quand un wallet réputé skillful place un trade significatif, pour permettre à l'opérateur humain de copier.

**2.B.1 Sélection des wallets trackés (bootstrap C hybride)**

Trois tiers dans `tracked_wallets` :

- **Tier A — Seed list manuelle** : wallets identifiés à partir du rapport 3 (cas forensiques) + leaderboards publics Dune (`@rchen8/polymarket`, `@polymarketanalytics`). Validés manuellement. ~20-50 wallets max en v1. Champ `source = 'seed_manual'`.
- **Tier B — Promoted via backfill** : wallets qui sortent du backfill 6-12 mois avec métriques compliant FDR BH. Champ `source = 'backfill_q1'`.
- **Tier C — Candidats en observation** : wallets qui montrent des patterns prometteurs mais pas encore suffisamment de data. Leurs trades sont trackés mais pas alertés (dry run), pour accumuler statistiques.

Chaque wallet a :
- `tier` (A/B/C), `active` (bool), `added_at`, `last_reviewed_at`
- `honeypot_flag` (bool) — détecté par anti-honeypot (§2.B.4)
- `tier_a_confidence` (0-1), `backtested_edge`, `backtested_clv`

**2.B.2 Métriques de skill (calculées en batch weekly)**

Implémentées progressivement. V1 = Tier 1 du rapport 4, strict minimum :

| Métrique | Formule | Seuil minimum pour tracking |
|---|---|---|
| Edge post-résolution | $(\text{prix entrée} - \text{outcome}) \times \text{size}$, moyenne signed | > 3 cents/trade |
| Closing Line Value (CLV) | $\text{prix entrée} - \text{prix juste avant résolution}$ | > 2 cents/trade |
| Brier Score Skill (BSS) | $1 - \text{Brier}_{wallet} / \text{Brier}_{baseline}$ | > 0.05 |
| Sharpe trades (approx) | $\bar{r} / \sigma_r$ sur trades normalisés | > 1.0 |
| Nb trades (échantillon) | count | > 50 |
| PSR (Probabilistic Sharpe Ratio) | Bailey-López de Prado | > 0.95 |

**Toutes ces métriques sont recalculées avec correction Benjamini-Hochberg FDR sur l'univers complet des wallets** — sans ça, le leaderboard est du bruit. Cf rapport 4 §9.5 point 2.

**2.B.3 Seuils de signal**

Une alerte C1 est émise quand, pour un trade capturé d'un wallet Tier A ou B :
- Size USD ≥ 500$ (filtrable par wallet — certains sharps tradent plus petit)
- Liquidité marché ≥ 5000$ (sinon on n'arrive pas à copier sans mover le prix)
- Wallet non-flagué honeypot
- Pas d'alerte sur (wallet, market, side) dans les 30 dernières min (dédup)
- Score composite wallet × conviction_trade × liquidity_ok > seuil calibré

`conviction_trade` = combine size relatif au pattern historique du wallet (z-score MAD cf rapport 4 §2.1), prix d'entrée vs midpoint (meilleur si buy low / sell high), timing vs événements publics connus.

**2.B.4 Anti-honeypot**

C'est le filtre critique du composant 1. Un "faux sharp" construit un track record visible pour attirer des copieurs, puis drainer via un trade contre ses propres followers. Détection :

- **Signe 1 — Volume anormal vs position size** : le wallet affiche un gros PnL mais chaque trade gagnant est petit (< 500$) puis soudain une grosse position (> 5000$) sur un marché illiquide. Ratio position/median_historique > 10x = flag.
- **Signe 2 — Catégories jackpot** : concentration des gains sur marchés à très faible probabilité résolus au sens du wallet (longshots). Suspicious si > 70% du PnL vient de trades à p_entrée < 0.15 qui ont hit.
- **Signe 3 — Pattern de funding corrélé** : le wallet est funded via une CEX deposit address partagée avec N autres wallets aux comportements similaires. Cluster détecté via méthode Victor 2020 (déposit-address-reuse).
- **Signe 4 — Tenue de marché sur propres positions** : le wallet est à la fois maker et taker sur le même marché (wash-trading-like). SCC sur graphe wallet-trade-wallet.
- **Signe 5 — Absence de CLV** : Edge post-résolution positif MAIS CLV proche de zéro ou négatif = trader qui gagne sur les longshots sans discovery d'information pré-résolution = pattern suspect.

Chaque signe contribue à un `honeypot_score` [0,1]. Si > 0.4 → `honeypot_flag = true`, wallet sorti du tracking Tier A/B. Review manuelle hebdomadaire des wallets 0.2 < score < 0.4.

**2.B.5 Sizing recommandé** (commun C1 et C2)

Formule :

```
size_usd = min(
    bankroll * max_single_trade_pct,           # cap dur, ex 3%
    quarter_kelly(edge_estimé, odds) * bankroll,
    liquidity_market * 0.05                     # ne pas bouffer + de 5% de la liquidité
)
```

`edge_estimé` vient des métriques backtestées du wallet pour C1, d'une heuristique pour C2 (conservateur).
`quarter_kelly` = 0.25 × Kelly classique, par défaut.
`max_single_trade_pct` = 3% bankroll par défaut, configurable via commande.

Le bot n'exécute jamais, il affiche dans l'alerte : `"Size suggéré : 45€ (2.3% bankroll, quarter-Kelly)"`.

### 2.C Composant 2 — Informed Trading Alert

**Objectif** : détecter les patterns d'insider trading en temps quasi-réel, signal rare (0-5/semaine cible).

**2.C.1 Features calculées sur chaque marché chaud**

Scan toutes les 5 min sur `markets_hot` (filtre : volume 1h > 1000$ OU mouvement prix > 300 bps en 1h OU proximité résolution < 72h).

Pour chaque marché :

| Feature | Définition | Source data |
|---|---|---|
| `fresh_wallet_concentration` | % volume 1h provenant de wallets créés < 7j | `trades_all` + `wallets` |
| `shared_cex_deposit_ratio` | Parmi les top-5 traders 1h, % qui partagent une deposit address CEX | `proxy_eoa_map` + funding trace |
| `niche_market_flag` | `true` si volume cumul < 50k$ ET catégorie ≠ election/crypto mainstream | `markets` |
| `time_to_event` | Delta heures entre now et resolution_date | `markets` |
| `top5_concentration` | HHI sur top-5 traders 1h | `trades_all` |
| `price_momentum_1h` | $|\log(p_t/p_{t-1h})|$ normalisé par volatilité historique | `prices_1m` |
| `volume_zscore_robust` | $(V_{1h} - \text{median}_{30d}) / (1.4826 \cdot \text{MAD}_{30d})$ | `prices_1m` aggregated |
| `order_book_imbalance` | $(V^B - V^S) / (V^B + V^S)$ sur snapshot actuel | CLOB `/book` |

**2.C.2 Score composite**

Deux modes :

- **V1 — règles** : si `fresh_wallet_concentration > 0.5` ET `top5_concentration > 0.7` ET `time_to_event < 48h` ET (`niche_market_flag` OU `shared_cex_deposit_ratio > 0.3`) → ALERT. Rationnel : c'est la signature Tier 1 du rapport 4 et brief 3.
- **V2 (à calibrer après 1-2 mois de data)** : logistic regression sur les features, labels supervisés = alertes passées × outcome résolution. Pas en v1.

**2.C.3 Seuils de déclenchement**

- Max 1 alerte C2 par marché par 6h fenêtre (dédup strict).
- Max 3 alertes C2 par jour global (soft cap, au-delà on passe en "digest" dans #ops).
- Pas d'alerte C2 sur marchés avec liquidité < 2000$ (trop facile à manipuler avec peu, trop risqué à trader).

**2.C.4 Payload de l'alerte**

Voir §2.E.3.

### 2.D Composant 3 — Resolution Risk Filter

**Objectif** : scorer le risque qu'un marché soit disputé, mal résolu, ou ambigu. Appelé systématiquement en enrichissement des alertes C1/C2, et à la demande via `/risk`.

**2.D.1 Architecture hybride : LLM caché + rules dynamiques**

Deux étages combinés au moment du scoring.

**Étage 1 — LLM semantic ambiguity (cache permanent)** :
- Appelé UNE FOIS par marché au moment où `indexer_markets_gamma` détecte un nouveau `condition_id`.
- Modèle : Claude Haiku (`claude-haiku-4-5-20251001`). Choix motivé par ratio coût/qualité sur tâche de classification sémantique simple.
- Prompt structuré : question + description + resolution source + outcomes → output JSON `{ambiguity_score: 0-1, reasons: [], red_flags: []}`.
- Stocké dans `resolution_risk_cache` avec `market_id`, `llm_score`, `llm_reasons`, `llm_model_version`, `computed_at`.
- Re-évalué si la question est éditée (rare mais arrive — cf rapport 2 §7).

**Étage 2 — Rules dynamiques (calculées au moment de l'alerte)** :
- `dispute_rate_category` : historique de disputes UMA sur la catégorie du marché (ex : "politics" a 5% de dispute vs "crypto prices" 0.5%).
- `liquidity_dispute_window` : USDC mobilisable pour disputer si besoin (~25k USDC bond). Si liquidité marché < 10x bond → risque de dispute opportuniste faible mais risque de fail sur resolution faible aussi.
- `oracle_source_reliability` : la `resolution_source` est-elle une URL qui existe et est fiable (Reuters, AP, official gov) vs un compte Twitter ?
- `time_sensitivity` : fenêtre de dispute UMA (~2h typiquement) vs horaire de résolution (nuit US = moins de monitors actifs).
- `related_markets_resolved_cleanly` : si des marchés similaires dans la même série ont déjà été résolus sans dispute.

**2.D.2 Score composite**

```
risk_score = 0.5 * llm_score + 0.3 * rules_dynamic_score + 0.2 * oracle_reliability_score
```

Pondération à calibrer avec retour d'expérience.

Verdict textuel :
- `[LOW]` risk_score < 0.25
- `[MEDIUM]` 0.25-0.50
- `[HIGH]` 0.50-0.75
- `[CRITICAL]` > 0.75 + flag spécial dans l'alerte

**2.D.3 Coût LLM estimé**

Hypothèses : ~15k nouveaux marchés/an, prompt ~500 tokens input / 200 tokens output.

- Haiku pricing (avril 2026 — à vérifier) : ~1$/MTok input, ~5$/MTok output.
- Coût par marché : (500 × 1 + 200 × 5) / 1M = **0.0015 $/marché**.
- Mensuel : 15000 / 12 × 0.0015 ≈ **0.002 $/mois sur les nouveaux**. Négligeable.

Plus le recalcul annuel des top-500 marchés suivis = 500 × 0.0015 = 0.75$ par an.

**Budget total LLM : < 1$/mois**. Safe margin × 3 pour absorber des appels `/risk` manuels.

**2.D.4 Commande `/risk <url_ou_slug>`**

Parse l'URL ou le slug, résout en `condition_id`, appelle le pipeline complet (cache + rules), répond dans le thread d'origine en < 5s.

### 2.E Bot Telegram

**2.E.1 Canaux (chats privés ou groupe avec topics)**

Option retenue : **un seul groupe privé avec topics** (feature Telegram qui permet des sous-canaux dans un groupe). Plus simple à maintenir qu'un bot multi-chats.

Topics :
- `#alerts` — alertes C1 et C2, tag `[SHARP]` ou `[INFORMED]` dans le texte
- `#risk` — réponses aux commandes `/risk`
- `#ops` — status, perf daily, digest des signaux faibles
- `#errors` — erreurs applicatives, warnings, kill switch activations

**2.E.2 Commandes**

| Commande | Fonction |
|---|---|
| `/risk <url_ou_slug>` | Appelle C3 |
| `/bankroll <montant>` | Update bankroll (persiste en DB) |
| `/bankroll` | Affiche le bankroll courant |
| `/perf [7d\|30d\|all]` | Résumé des perfs des alertes émises |
| `/status` | Santé : derniers polls, erreurs 24h, nb alertes 24h, kill switches actifs |
| `/toggle <c1\|c2\|c3\|all> <on\|off>` | Kill switch (voir §7) |
| `/wallets [tier]` | Liste les wallets trackés (debug / review) |
| `/investigate <wallet>` | Dump des métriques d'un wallet (debug) |
| `/help` | Liste commandes |

**2.E.3 Structure type d'une alerte C1**

```
🟢 [SHARP] 0xab12…cd34 (Tier A, conf 0.82)
Marché : "Will Fed cut rates in June 2026?"
Side : YES @ 0.67 (midpoint 0.665)
Size wallet : 3,200 USDC
Liquidité : 18k USDC

📊 Wallet stats (90j) :
  Edge +4.2c/trade · CLV +3.1c · Brier Skill +0.08
  N=82 trades · PSR 0.97

💡 Size suggéré : 52€ (2.6% bankroll, quarter-Kelly)

⚖️ Resolution Risk : [LOW] 0.18
   └ Fed rate is unambiguous, official source

🔗 https://polymarket.com/event/...
⏱️ 2min ago · alert_id AL_2026_04_17_0042
```

**2.E.4 Structure type d'une alerte C2**

```
🔴 [INFORMED] Signal haute conviction
Marché : "Will X happen before May 1?"
Prix : 0.12 → 0.34 (1h, +183%)
Volume 1h : 12,500 USDC (z-score 4.8)

🧬 Pattern :
  • 73% du volume provient de 4 wallets créés < 3j
  • 3/4 partagent une deposit address CEX
  • Marché niche (volume cumul 28k)
  • 28h avant résolution

⚖️ Resolution Risk : [MEDIUM] 0.42
   └ Official source unclear, dispute possible

💡 Size suggéré : 18€ (conservateur, 0.9% bankroll)

🔗 https://polymarket.com/event/...
⏱️ alert_id AL_2026_04_17_0043
```

**2.E.5 Structure type d'une réponse `/risk`**

```
⚖️ Resolution Risk Analysis
Marché : "Will [candidate] win [election]?"

Score global : [HIGH] 0.62

LLM semantic ambiguity : 0.55
  • Question ne précise pas le mode de scrutin
  • Resolution source = compte Twitter officiel

Rules dynamiques :
  • Catégorie "politics" : 5.2% dispute rate historique
  • Liquidité 45k USDC, bond 25k : dispute opportuniste possible
  • 3 marchés similaires série ont été disputés en 2024-2025

🚩 Red flags : 2
```

### 2.F Orchestrateur et garde-fous (voir §7 pour détails)

Process central qui :
- Lance et supervise les indexers (auto-restart sur crash via `supervisord` ou `systemd`).
- Schedule les jobs batch via APScheduler.
- Applique les kill switches (lecture flag en DB à chaque dispatch).
- Applique les rate limits hard (compteurs par composant).
- Logge toutes les actions dans `audit_log`.

---

## 3. Modèle de données

### 3.1 Vue d'ensemble

DuckDB en hot storage (fichier `/data/pm.duckdb`), Parquet partitionné en cold storage (`/data/parquet/<table>/<YYYY-MM>/`). Règle : données > 90 jours migrent en Parquet cold, queries analytiques via DuckDB ATTACH.

### 3.2 Tables principales

**`markets`** — metadata marchés, source Gamma
```
condition_id           VARCHAR PRIMARY KEY
question_id            VARCHAR
question_text          TEXT
description            TEXT
category               VARCHAR
tags                   VARCHAR[]
outcomes               VARCHAR[]  -- typiquement ["YES","NO"]
neg_risk               BOOLEAN
resolution_source      TEXT
resolution_date        TIMESTAMP
created_at             TIMESTAMP
closed_at              TIMESTAMP
volume_cumulative_usd  DECIMAL(18,2)
liquidity_usd          DECIMAL(18,2)
status                 VARCHAR  -- active, closed, resolved, archived
last_synced_at         TIMESTAMP
```

**`trades`** — trades capturés temps réel (wallets trackés + marchés chauds)
```
tx_hash                VARCHAR
log_index              INTEGER
PRIMARY KEY (tx_hash, log_index)
block_number           BIGINT
block_timestamp        TIMESTAMP
condition_id           VARCHAR REFERENCES markets
token_id               VARCHAR  -- ERC-1155 id (YES ou NO)
outcome_index          INTEGER
maker                  VARCHAR
taker                  VARCHAR
side                   VARCHAR  -- buy, sell
price                  DECIMAL(6,4)  -- in [0,1]
size_tokens            DECIMAL(18,6)
size_usd               DECIMAL(18,2)
fee                    DECIMAL(18,6)
exchange               VARCHAR  -- vanilla, neg_risk
```

**`trades_all`** — trades large scope (backfill Goldsky/Dune), même schéma que `trades` mais moins frais, plus large. Partitionné en Parquet par mois.

**`wallets`** — wallets observés (pas forcément trackés)
```
address                VARCHAR PRIMARY KEY
first_seen_at          TIMESTAMP
last_active_at         TIMESTAMP
total_trades           INTEGER
total_volume_usd       DECIMAL(18,2)
is_proxy               BOOLEAN
resolved_eoa           VARCHAR  -- si proxy, EOA racine
cluster_id             VARCHAR  -- si clusterisé Victor 2020
```

**`tracked_wallets`** — sous-ensemble des wallets qu'on suit activement
```
address                VARCHAR PRIMARY KEY
tier                   VARCHAR  -- A, B, C
active                 BOOLEAN
source                 VARCHAR  -- seed_manual, backfill_q1, etc
added_at               TIMESTAMP
last_reviewed_at       TIMESTAMP
honeypot_flag          BOOLEAN
honeypot_score         DECIMAL(3,2)
tier_a_confidence      DECIMAL(3,2)
notes                  TEXT
```

**`wallet_metrics`** — métriques calculées en batch
```
address                VARCHAR
window                 VARCHAR  -- 30d, 90d, 180d, all
computed_at            TIMESTAMP
PRIMARY KEY (address, window, computed_at)
n_trades               INTEGER
edge_per_trade         DECIMAL(6,4)
clv_per_trade          DECIMAL(6,4)
brier_score            DECIMAL(5,4)
brier_skill_score      DECIMAL(5,4)
sharpe_trades          DECIMAL(5,3)
psr                    DECIMAL(4,3)
dsr                    DECIMAL(4,3)
fdr_bh_adjusted_pvalue DECIMAL(6,5)
total_pnl_usd          DECIMAL(18,2)
```

**`proxy_eoa_map`** — mapping critique pour métriques per-user
```
proxy_address          VARCHAR PRIMARY KEY
eoa_address            VARCHAR
confidence_score       DECIMAL(3,2)
method                 VARCHAR  -- direct_factory, deposit_address_shared, manual
computed_at            TIMESTAMP
```

**`positions`** — positions courantes reconstruites
```
address                VARCHAR
token_id               VARCHAR
PRIMARY KEY (address, token_id)
balance                DECIMAL(18,6)
avg_cost               DECIMAL(6,4)
realized_pnl_usd       DECIMAL(18,2)
unrealized_pnl_usd     DECIMAL(18,2)
last_updated_at        TIMESTAMP
```

**`resolutions`** — résolutions UMA
```
condition_id           VARCHAR PRIMARY KEY
question_id            VARCHAR
proposed_at            TIMESTAMP
proposed_answer        VARCHAR  -- YES, NO, 50-50
proposer               VARCHAR
disputed               BOOLEAN
dispute_count          INTEGER
settled_at             TIMESTAMP
final_answer           VARCHAR
payouts                DECIMAL(4,2)[]  -- ex [1.0, 0.0]
```

**`prices_1m`** — prix midpoint par minute sur les marchés trackés
```
condition_id           VARCHAR
token_id               VARCHAR
minute                 TIMESTAMP
PRIMARY KEY (condition_id, token_id, minute)
price_open             DECIMAL(6,4)
price_high             DECIMAL(6,4)
price_low              DECIMAL(6,4)
price_close            DECIMAL(6,4)
volume_usd             DECIMAL(18,2)
best_bid               DECIMAL(6,4)
best_ask               DECIMAL(6,4)
```

Partitionnée par mois en Parquet dès création (table volumineuse).

**`markets_hot`** — vue matérialisée des marchés chauds (rafraîchie toutes les 5 min)
```
condition_id           VARCHAR PRIMARY KEY
volume_1h_usd          DECIMAL(18,2)
price_move_1h_bps      INTEGER
time_to_resolution_h   DECIMAL(8,1)
hot_score              DECIMAL(5,2)
updated_at             TIMESTAMP
```

**`resolution_risk_cache`** — scores LLM mis en cache
```
condition_id           VARCHAR PRIMARY KEY
llm_score              DECIMAL(3,2)
llm_reasons            TEXT[]
llm_red_flags          TEXT[]
llm_model_version      VARCHAR
computed_at            TIMESTAMP
```

**`alerts`** — log de toutes les alertes émises
```
alert_id               VARCHAR PRIMARY KEY  -- AL_YYYY_MM_DD_NNNN
component              VARCHAR  -- C1, C2, C3
emitted_at             TIMESTAMP
condition_id           VARCHAR REFERENCES markets
token_id               VARCHAR
side                   VARCHAR
price_at_alert         DECIMAL(6,4)
size_recommended_usd   DECIMAL(18,2)
bankroll_snapshot      DECIMAL(18,2)
signal_source          VARCHAR  -- address pour C1, heuristic_id pour C2
features               JSON  -- snapshot des features qui ont déclenché
resolution_risk_score  DECIMAL(3,2)
resolution_risk_label  VARCHAR
telegram_message_id    VARCHAR
```

**`alert_outcomes`** — résultats a posteriori des alertes
```
alert_id               VARCHAR PRIMARY KEY REFERENCES alerts
resolved_at            TIMESTAMP
final_outcome          VARCHAR  -- YES, NO, 50-50, pending
hypothetical_pnl_pct   DECIMAL(6,4)  -- si on avait suivi
clv_bps                INTEGER
brier_contribution     DECIMAL(5,4)
notes                  TEXT
```

**`bankroll_state`** — update via `/bankroll`
```
updated_at             TIMESTAMP PRIMARY KEY
amount_eur             DECIMAL(18,2)
note                   TEXT
```

**`kill_switches`** — état des garde-fous
```
component              VARCHAR PRIMARY KEY  -- c1, c2, c3, all, indexer_trades, etc
state                  VARCHAR  -- on, off
set_at                 TIMESTAMP
reason                 TEXT
```

**`audit_log`** — événements système
```
log_id                 BIGINT PRIMARY KEY AUTO_INCREMENT
timestamp              TIMESTAMP
level                  VARCHAR  -- INFO, WARN, ERROR
component              VARCHAR
event                  VARCHAR
details                JSON
```

**`rate_limit_counters`** — compteurs par heure par composant (rolling)
```
component              VARCHAR
hour_bucket            TIMESTAMP
PRIMARY KEY (component, hour_bucket)
count                  INTEGER
```

### 3.3 Volumétrie estimée (v1, régime de croisière)

| Table | Volume estimé à 6 mois |
|---|---|
| markets | ~40k rows |
| trades (hot) | ~1-5M rows |
| trades_all (Parquet) | ~30-100M rows |
| prices_1m | ~10M rows/mois |
| wallets | ~500k rows |
| tracked_wallets | ~200 rows |
| wallet_metrics | ~2k rows/semaine de recompute |
| alerts | ~1-3k rows |
| proxy_eoa_map | ~200k rows |

Disque : ~20-50 Go à 6 mois, compatible VPS CX22 (40 Go SSD).

### 3.4 Relations clés

Simplifié :

```
markets ─────< trades >───── wallets
   │                            │
   │                            ├──< tracked_wallets (subset)
   │                            │
   │                            └── proxy_eoa_map (address → eoa)
   │
   ├──< prices_1m
   ├──< resolutions
   └──< alerts ─── alert_outcomes
             │
             └── resolution_risk_cache
```

---

## 4. Stack technique précise

### 4.1 Infrastructure

| Composant | Choix | Coût mensuel |
|---|---|---|
| VPS | Hetzner CX22 (2 vCPU, 4 GB RAM, 40 GB NVMe, Nuremberg) | ~5 € |
| OS | Ubuntu 24.04 LTS | 0 € |
| Reverse proxy | Caddy (auto HTTPS pour dashboard Streamlit) | 0 € |
| Process supervision | systemd (ou supervisord si besoin de plus souple) | 0 € |
| Backups | rclone vers Hetzner Storage Box ou Backblaze B2 | ~1 € |

### 4.2 Services externes

| Service | Usage | Plan | Coût |
|---|---|---|---|
| Gamma API Polymarket | Metadata marchés | Public, gratuit | 0 € |
| CLOB API Polymarket | Order book, trades, prix history | Public (lecture), gratuit | 0 € |
| Data API Polymarket | Positions, holders | Public, gratuit | 0 € |
| Goldsky subgraph Polymarket | Activity, positions, pnl | Public free tier | 0 € |
| Dune Analytics | Backfill historique SQL, analyses ad-hoc | Plus 49 $/mois | ~45 € |
| Alchemy RPC Polygon | Events on-chain (UMA, factories) | Free tier 300M CU | 0 € |
| Anthropic API (Claude Haiku) | Scoring ambiguité marchés | pay-per-use | < 1 € |
| Telegram Bot API | Alertes | Gratuit | 0 € |

**Total budget** : ~52 €/mois si on prend Dune Plus, ~6 €/mois sans. 

Décision : démarrer **sans Dune Plus** (use free tier + backfill progressif via Goldsky + Alchemy direct) et upgrade si le backfill devient bloquant. Ça respecte la contrainte < 30 €/mois du brief.

Alternative discutée en §9 : Flipside free pour remplacer Dune en backfill one-shot.

### 4.3 Bibliothèques Python

**Core** (Python 3.12) :
- `python-telegram-bot` — bot Telegram
- `httpx` — client HTTP async (Gamma, CLOB, Data API)
- `py-clob-client` — SDK officiel Polymarket (si on veut passer des ordres auth plus tard ; en v1 juste pour auth signatures si on en a besoin)
- `gql` + `aiohttp` — client GraphQL Goldsky
- `web3.py` — interaction RPC Polygon (events décodés UMA, factory)
- `apscheduler` — scheduler jobs batch
- `pydantic` v2 — validation des données ingérées
- `tenacity` — retry logic avec backoff

**Data** :
- `duckdb` — DB principale
- `polars` — DataFrames (préféré à pandas pour perf et stabilité schéma)
- `pyarrow` — Parquet I/O
- `numpy`, `scipy.stats` — calculs statistiques (FDR BH, MAD z-score, Brier)

**ML/Stats** (progressif, pas tout en v1) :
- `scikit-learn` — IsolationForest, logistic regression pour C2 v2
- `statsmodels` — tests FDR BH explicites, event studies

**LLM** :
- `anthropic` — SDK Claude pour C3

**Observabilité** :
- `loguru` — logging structuré
- `streamlit` — dashboard local de perf (accédé via SSH tunnel ou Caddy reverse proxy)

**Tests** :
- `pytest`, `pytest-asyncio`
- `freezegun` — mocker le temps dans les tests
- `vcrpy` — mocker les APIs externes

### 4.4 Structure du repo (pressenti)

```
polymarket-bot/
├── src/
│   ├── indexers/
│   │   ├── markets_gamma.py
│   │   ├── trades_clob.py
│   │   ├── onchain_goldsky.py
│   │   ├── resolutions_uma.py
│   │   └── proxy_factory.py
│   ├── components/
│   │   ├── c1_sharp_money.py
│   │   ├── c1_anti_honeypot.py
│   │   ├── c2_informed_trading.py
│   │   └── c3_resolution_risk.py
│   ├── scoring/
│   │   ├── wallet_metrics.py
│   │   ├── fdr_correction.py
│   │   ├── sizing.py
│   │   └── clv_brier.py
│   ├── telegram/
│   │   ├── bot.py
│   │   ├── commands.py
│   │   └── formatters.py
│   ├── orchestrator/
│   │   ├── main.py
│   │   ├── kill_switch.py
│   │   ├── rate_limiter.py
│   │   └── scheduler.py
│   ├── storage/
│   │   ├── db.py  -- DuckDB connection mgmt
│   │   ├── models.py  -- pydantic schemas
│   │   ├── parquet_compactor.py
│   │   └── backup.py
│   └── dashboard/
│       └── streamlit_app.py
├── jobs/
│   ├── backfill_historical.py
│   ├── rescore_wallets.py
│   ├── resolve_alerts.py
│   └── report_daily.py
├── tests/
├── scripts/
│   ├── seed_tracked_wallets.py
│   └── one_shot_backtest.py
├── config/
│   ├── default.yaml
│   └── secrets.env.example
├── deploy/
│   ├── systemd/
│   └── caddyfile
├── pyproject.toml
└── README.md
```

---

## 5. Gestion des états et persistance

### 5.1 Dédup des alertes

Problème : sans dédup, on spam le canal à chaque re-sync d'un trade déjà vu, ou chaque scan 5min qui re-détecte la même anomalie.

**Règle de dédup à 3 niveaux** :

1. **Niveau technique** : clé `(tx_hash, log_index)` sur trades → insert-only, contrainte DB empêche réinsertion.
2. **Niveau applicatif C1** : hash logique `sha256(wallet + market + side + floor(timestamp/300))` → bucket 5 min. Si ce hash existe dans `alerts` des dernières 30 min → skip.
3. **Niveau applicatif C2** : clé `(condition_id, floor(timestamp/3600*6))` → 1 alerte par marché par 6h max.

`alerts.alert_id` = `AL_YYYY_MM_DD_NNNN` séquentiel quotidien (reset à minuit UTC).

### 5.2 Reprise après crash

Chaque indexer persiste son `last_synced_cursor` dans une table `indexer_state` :

```
indexer_name           VARCHAR PRIMARY KEY
last_cursor            VARCHAR  -- block_number, timestamp, ou offset selon l'indexer
last_success_at        TIMESTAMP
consecutive_failures   INTEGER
```

Au redémarrage, chaque indexer lit son cursor et reprend depuis ce point. Pour les indexers qui pollent une window glissante (CLOB trades), on retrigger une fenêtre de recouvrement de 2× l'intervalle pour être safe (ex : polling 60s → on pull la fenêtre des 120 dernières secondes). Dédup gère les doublons.

**Cas critique : reorgs Polygon**. Si on indexe on-chain à la block height courante, un reorg peut invalider des events. **Règle** : tous les indexers on-chain attendent **64 blocs de confirmation** (~2 min) avant d'écrire définitivement. Pour les events trading rapides, on accepte ce lag de 2 min. Alternative plus safe mais plus lente : attendre le checkpoint Heimdall (~30 min) pour les events critiques de résolution.

### 5.3 Backups

Deux niveaux :

- **Quotidien** : snapshot DuckDB (`EXPORT DATABASE`) + tarball des fichiers Parquet récents → upload rclone vers Hetzner Storage Box. Rétention 30 jours rolling.
- **Hebdomadaire** : snapshot complet incluant Parquet cold storage → rétention 1 an.

Jamais de backup des secrets ni de l'historique Telegram (non nécessaire, tout est en DB).

**Script de restore** testé au moins une fois après mise en prod (checklist §6).

### 5.4 État du bankroll

Persisté dans `bankroll_state`, mise à jour exclusivement via `/bankroll`. Le bot ne calcule jamais le bankroll lui-même (il ne sait pas quelles alertes ont été effectivement tradées). C'est à l'opérateur de le tenir à jour après chaque session de trade.

Alerte automatique dans `#ops` si `bankroll_state.updated_at > 14 jours` → "Bankroll pas mis à jour depuis 14j, les sizings recommandés peuvent être faux."

### 5.5 Schema migration

Utiliser un système simple de migrations versionnées : dossier `migrations/NNN_description.sql`, exécutées en ordre au démarrage si version en DB < version du code. Pas besoin d'Alembic pour ça, un petit loader custom suffit.

---

## 6. Observabilité et opérabilité

### 6.1 Logging

Trois niveaux de logs :

- **Structured logs** via loguru, écrits en JSONL dans `/var/log/pm-bot/`. Rotation daily, rétention 14 jours compressé.
- **Audit log** dans DuckDB (table `audit_log`) : tout événement métier (alerte émise, kill switch activé, wallet ajouté/flaggé, bankroll updaté).
- **Canal Telegram `#errors`** : pour tout log niveau ERROR et WARN critique, push dans Telegram pour visibilité immédiate.

### 6.2 Health checks et status

Commande `/status` affiche :
- Indexers : dernier cycle réussi, latence moyenne, nb erreurs 24h
- Composants : nb alertes 24h / limite, kill switch on/off
- DB : taille, dernière compaction, dernier backup
- LLM : quota estimé, dernier appel
- Uptime du process

Endpoint HTTP optionnel `GET /health` exposé localement (pour heartbeat externe type UptimeRobot si souhaité plus tard).

### 6.3 Dashboard de perf (Streamlit)

Single page app locale, accessible via `ssh -L 8501:localhost:8501 vps` ou reverse proxy Caddy avec basic auth.

Sections :
- **Overview** : nb alertes émises 7d/30d, hit rate par composant, CLV moyen, Brier skill score
- **Alertes** : table filtrable/searchable, drill-down par alerte
- **Wallets trackés** : leaderboard, métriques FDR-adjustées, distribution honeypot scores
- **Marchés chauds actuels** : scan live
- **Budget LLM** : coût mensuel running, extrapolation

Pas de sophistication graphique nécessaire, c'est de l'instrumentation, pas un produit.

---

## 7. Kill switch et garde-fous (ton point 7)

Traité comme un sous-système à part entière, pas comme des flags éparpillés.

### 7.1 Kill switches manuels

Via commande Telegram `/toggle <target> <on|off> [reason]` :

| Target | Effet |
|---|---|
| `c1` | Stop émission alertes C1 (indexer continue) |
| `c2` | Stop émission alertes C2 (scan continue) |
| `c3` | Stop scoring LLM (rules seul continue) |
| `indexer_<name>` | Stop un indexer spécifique |
| `all_alerts` | Mute général des alertes (indexers tournent) |
| `all` | Full freeze (orchestrateur suspend tout dispatch) |

État persisté dans `kill_switches`, lu à chaque dispatch (overhead : une query DuckDB sur table minuscule, cache en mémoire 10s).

Activation d'un switch → message dans `#ops` : "Kill switch C1 activé. Raison : [texte]. Activé à HH:MM."

Désactivation explicite requise via `/toggle c1 on`. Pas de timer auto.

### 7.2 Rate limits hard

Compteurs dans `rate_limit_counters`, vérifiés avant chaque émission d'alerte.

Limites par défaut :

| Composant | Max/heure | Max/jour | Action au dépassement |
|---|---|---|---|
| C1 alertes | 10 | 40 | Digest dans #ops, alertes suspendues jusqu'à next hour |
| C2 alertes | 2 | 5 | Idem |
| C3 commandes `/risk` | 20 | 100 | Rate limit message dans le thread |
| LLM calls Haiku | 50 | 200 | Dégradation gracieuse en rules-only, warn dans #errors |

Ces limites sont configurables via config file. Philosophy : si on dépasse, c'est soit un bug, soit un pattern de marché exceptionnel — dans les deux cas, un humain doit regarder avant de continuer à envoyer.

### 7.3 Circuit breakers automatiques

Déclenchement automatique d'un kill switch sans intervention humaine dans les cas suivants :

| Trigger | Action auto |
|---|---|
| Indexer en échec > 10 min consécutives | `indexer_<name>` OFF + alerte #errors |
| > 5 erreurs 500 consécutives sur une API externe | Backoff 5 min, puis OFF si persiste |
| Dérive horaire > 30s (clock skew) | Warn, pause des indexers time-sensitive |
| Taille DB > 80% du disque | Alerte #errors, pause backfill jobs |
| Coût LLM cumulé mois > seuil config (ex 5€) | C3 LLM OFF, rules-only, warn |

### 7.4 Graceful degradation

Chaque composant est conçu pour **fonctionner en mode dégradé** si une dépendance manque :

- C1 sans Goldsky : tourne avec juste CLOB direct (moins d'enrichissement, mais le core fonctionne).
- C3 sans LLM : tourne avec rules dynamiques seules, flag `llm_unavailable=true` dans l'alerte.
- Pas de dashboard : bot fonctionne quand même.
- Pas de backup : warn dans #errors, mais pas de blocage.

Philosophie : le bot doit toujours pouvoir émettre les alertes critiques même si la moitié du stack est cassée. Mieux vaut une alerte dégradée qu'une alerte manquée.

### 7.5 Logs d'audit dédiés

Table `audit_log` conserve trace de :
- Chaque activation/désactivation de kill switch (qui, quand, raison)
- Chaque modification de seuil/config
- Chaque ajout/suppression de wallet tracké
- Chaque flag honeypot appliqué

Rétention : 1 an minimum. Permet post-mortem en cas de décision regrettable (ex : "pourquoi j'avais désactivé C2 le 12 mars ?").

---

## 8. Planning de livraison (indicatif, 4-6 semaines)

Non contractuel, juste pour avoir une séquence d'implémentation cohérente.

**Semaine 1** — Fondations
- Setup VPS, repo, CI léger (lint + tests)
- DB schema + migrations
- Indexer `markets_gamma` + `proxy_factory` en dry run
- Bot Telegram squelette (`/status`, `/help`, `/bankroll`)

**Semaine 2** — Ingestion
- Indexers `trades_clob`, `onchain_goldsky`, `resolutions_uma`
- Seed list manuelle des wallets Tier A (à partir rapport 3 + leaderboards publics)
- Backfill 30j initial (`scripts/backfill_historical.py`)

**Semaine 3** — Composant 1
- `c1_sharp_money` basic (sans anti-honeypot complet)
- Scoring wallets v0 (edge, CLV, N trades)
- Format alerte + dédup + sizing
- Mise en dry run : alertes émises dans `#ops` pas `#alerts` pendant 1 semaine

**Semaine 4** — Composant 3 + Anti-honeypot
- C3 rules-based
- LLM scoring en batch sur marchés existants
- Anti-honeypot signes 1-3 du §2.B.4
- Promotion C1 de dry run vers `#alerts` après revue manuelle

**Semaine 5** — Composant 2
- `c2_informed_trading` features + règles v1
- `markets_hot` materialized view
- Tests sur backfill des 18 cas forensiques du rapport 3

**Semaine 6** — Observabilité, kill switches, polish
- Dashboard Streamlit
- Kill switches complet + circuit breakers
- FDR BH systématique sur `rescore_wallets`
- Backups + restore test
- Documentation README + runbook ops

**Après v1** — Itérations :
- Backfill 12 mois complet
- Promotion Tier C → B en continu
- Anti-honeypot signes 4-5
- Éventuellement C2 v2 supervisé
- Éventuellement migration bankroll auto-tracking via API CLOB authentifiée

---

## 9. Questions ouvertes et décisions à trancher

Points non tranchés qui nécessitent input ou qui sont à revisiter en cours de dev.

### 9.1 Cohabitation DuckDB en écriture concurrente

DuckDB single-writer. En v1 on a décidé : indexers écrivent dans staging Parquet + compactor merge toutes les 5min. À valider en charge. Plan B si ça coince : SQLite WAL pour hot path (trades, alerts), DuckDB pour analytique pure sur Parquet. Décision reportée à la fin semaine 2 après tests.

### 9.2 Dune Plus ou pas en v1

Décision préliminaire : non, on démarre sans. Mais si le backfill via Goldsky s'avère trop lent ou bute sur des limites, on upgrade. Réévaluation fin semaine 2.

### 9.3 Constitution exacte de la seed list Tier A

Non fait dans ce doc volontairement (cf échange préparatoire). Livrable préparatoire séparé avant semaine 2. Source : rapport 3 (cas forensiques) + leaderboards Dune publics + cross-check manuel sur Polymarket UI.

### 9.4 Quarter-Kelly : bon facteur ?

Quarter-Kelly (0.25× Kelly) par défaut. Mais l'estimation d'edge a du bruit : en pratique, half-Kelly d'un edge over-estimé peut ruiner. On pourrait démarrer à one-eighth-Kelly (conservateur) et relâcher après 2-3 mois de track record du bot. À discuter.

### 9.5 Sizing relatif à la liquidité du marché

Le plafond 5% de la liquidité est arbitraire. Sur Polymarket, l'order book est souvent thin en profondeur. Il faudrait tester : pour un trade de 50€ sur un marché avec 5k$ de liquidité, est-ce qu'on mange vraiment 1% de slippage ou plus ? À mesurer empiriquement en semaine 3.

### 9.6 Gestion des marchés multi-outcomes (Neg Risk)

Les marchés d'élection à N candidats ont une contrainte "somme des prix = 1" qui complique l'interprétation des mouvements. Un shift de 5% sur un outcome impacte mécaniquement les autres. À clarifier comment C2 gère ça : on track par outcome (comme aujourd'hui) ou par événement agrégé ?

### 9.7 Définition opérationnelle de "marché niche"

En §2.C.1 j'ai mis "volume cumul < 50k$ ET catégorie ≠ mainstream". Le seuil 50k est arbitraire. À calibrer sur la distribution empirique des volumes observés après 2-3 semaines d'ingestion.

### 9.8 VPN et accès CLOB

Le brief dit "exécution manuelle via VPN". Question : les APIs CLOB (lecture) sont-elles geo-bloquées pour la France, ou juste la UI web ? Si les APIs sont accessibles, le VPS Hetzner (Allemagne) n'a pas de problème en read. Si elles sont bloquées, il faut passer par un VPN sortant → complexité ops +++. À vérifier empiriquement en semaine 1.

### 9.9 Gestion des clés et secrets

Pour l'instant : pas de clés privées nécessaires en v1 (pas d'exécution auto). Les seules secrets : Telegram bot token, Anthropic API key, éventuellement Alchemy API key. Stockés en `.env` avec permissions 600 sur le VPS, chargés via `pydantic-settings`. Pas besoin de vault.

Pour v2 (exécution auto envisagée), revoir complètement : wallet hot séparé, clé chiffrée, signing isolé.

### 9.10 Frontière exacte LLM / rules dans C3

Le split 50/30/20 (LLM / rules dynamiques / oracle reliability) est une première intuition. À calibrer après 1-2 mois de données : sur les marchés qui ont effectivement été disputés ou mal résolus, quelle composante avait le pouvoir prédictif le plus fort ? Re-pondérer sur cette base.

---

## 10. Architecture Decision Records (ADR)

Tous les ADRs du projet sont maintenant centralisés dans `docs/ADRs/`. Voir `docs/ADRs/README.md` pour l'index complet.

ADRs historiques phase A : ADR-008 à ADR-011 (migrés de la version 1.0 de ce document).

---

*Fin du document. Prochaine phase (B) : implémentation concrète, en commençant par la semaine 1 du planning §8. Ce doc devient `A_architecture_technique.md` dans les project files.*
