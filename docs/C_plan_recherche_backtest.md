# Phase C — Plan de recherche et backtest

*Document canonique. Supersède `docs/archive/C_plan_recherche_v1.md`. Cadrage validé le 18 avril 2026.*

*Allocation effort : **50 % C1** (Sharp Money Copy) · **35 % C2** (Informed Trading Alert) · **15 % C3** (Resolution Risk Filter). Scénario B hybride : plan écrit + notebook pilote. Budget : 2 semaines, ~30-40 h.*

---

## 1. Objectifs et decision gates

### 1.1 Ce qu'on valide

Avant d'investir 4-6 semaines de dev (phase D), on vérifie empiriquement sur données historiques que les trois composants auraient fonctionné. L'allocation 50/35/15 reflète un choix délibéré : C1 est le composant quotidien qui fait tourner le cashflow récurrent, et son test méthodologique (anti-honeypot + FDR BH + leaderboard sans seed) est plus délicat que le test direct de C2 sur les 18 cas forensiques.

### 1.2 Livrables de la phase C

1. **Ground truth formalisé** — `data/ground_truth/{cases.csv, wallets.csv, sharps_positive.csv, markets_disputed.csv}` + `enrichment_log.md`. Déjà constitués pour cases/wallets/sharps (14 adresses enrichies, 70 % complétude). `markets_disputed.csv` à créer en semaine 1.
2. **Le présent plan** — `docs/C_plan_recherche_backtest.md`.
3. **Notebook pilote** — `notebooks/pilot_iran_strikes.ipynb` : reconstitution du cluster Iran depuis données publiques, validation de la stack technique.

### 1.3 Decision gates

**Gate GO** — passer en phase D (dev) si les 6 critères suivants sont remplis :

| # | Critère | Composant | Seuil |
|---|---------|-----------|-------|
| G1 | Pipeline technique validé sur pilote Iran | Infra | Features reconstituées matchent rapport 3 qualitativement |
| G2 | Leaderboard FDR-BH retrouve sharps connus sans seed | C1 | ≥ 5/6 sharps individuels dans top 100 |
| G3 | ≥ 5 nouveaux sharps identifiés hors seed list | C1 | Investigation manuelle les qualifie "plausibly skilled" |
| G4 | C2 recall ≥ 60 % sur test set (cas post-juillet 2025) | C2 | Heuristiques Niveau A sans tuning sur test |
| G5 | C2 ne flag pas les sharps positifs (< 5 % trades flaggés) | C2 | Domer/Aenews2/Kickstand7 discriminés |
| G6 | C3 score correctement Zelensky suit + Ukraine minerals en HIGH/CRITICAL | C3 | Accord catégoriel ≥ 70 % sur markets_disputed |

**Gate AJUSTER** — si 4-5/6 validés : on identifie le composant faible, on ajuste les heuristiques, on re-évalue rapidement (1 semaine max) avant phase D.

**Gate PIVOTER** — si ≤ 3/6 validés :
- C1 irrécupérable (< 3 sharps dans top 100) → v1 avec seed list manuelle uniquement, pas de détection automatique Tier B/C.
- C2 irrécupérable (recall < 30 %) → v1 sans C2. On code C1 + C3, on réfléchit à C2 supervisé après 3-6 mois de labels accumulés.
- C3 LLM décevant (accord < 50 %) → rules-only + flag manuel opérateur.
- Aucun composant ne passe (improbable) → abandon honnête, pas de dev.

### 1.4 Stretch goals (hors budget de base)

- **Reconstitution cluster Théo** (4-6 h) : test d'ambiguïté sharp vs insider, le plus révélateur méthodologiquement. Attaqué en fin de semaine 2 si la stack est en place, sinon reporté phase D.
- **Reconstitution Maduro** (3-4 h) : 2e cas de validation C2 si le temps le permet.

---

## 2. Constitution des datasets

### 2.1 Scope temporel

| Fenêtre | Période | Usage |
|---------|---------|-------|
| **Principale** | 1er avril 2025 → 15 avril 2026 (12 mois glissants) | Backfill trades, métriques, leaderboard |
| **Ciblée Théo** (stretch) | 1er oct → 15 nov 2024 | Cluster 4 wallets connus + marchés présidentielle/swing states uniquement |
| **Ciblée UMA disputes** | 1er mars → 15 juillet 2025 | Zelensky suit + Ukraine minerals (events UMA spécifiques) |

### 2.2 Sources de données — endpoints précis

**Dune Analytics (free tier, 2 500 credits/mois)**

Tables décodées à utiliser :
```sql
-- Trades Vanilla CTF Exchange
polymarket_polygon.ctfexchange_evt_orderfilled

-- Trades Neg Risk CTF Exchange
polymarket_polygon.negriskctfexchange_evt_orderfilled

-- Résolutions CTF
gnosis_polygon.conditionaltokens_evt_conditionresolution

-- Redemptions
gnosis_polygon.conditionaltokens_evt_payoutredemption

-- Transferts ERC-1155
gnosis_polygon.conditionaltokens_evt_transfersingle
```

Queries SQL à écrire (les plus coûteuses en credits) :

```sql
-- Q1 : tous les trades > $5K sur 12 mois, deux exchanges
-- Estimation : ~2M rows, ~800 credits
SELECT evt_block_time, evt_tx_hash, evt_index,
       maker, taker,
       makerAssetId, takerAssetId,
       CAST(makerAmountFilled AS DECIMAL(38,0)) / 1e6 AS maker_usd,
       CAST(takerAmountFilled AS DECIMAL(38,0)) / 1e6 AS taker_usd,
       fee, 'vanilla' AS exchange
FROM polymarket_polygon.ctfexchange_evt_orderfilled
WHERE evt_block_time >= TIMESTAMP '2025-04-01'
  AND CAST(makerAmountFilled AS DECIMAL(38,0)) / 1e6 >= 5000

UNION ALL

SELECT evt_block_time, evt_tx_hash, evt_index,
       maker, taker,
       makerAssetId, takerAssetId,
       CAST(makerAmountFilled AS DECIMAL(38,0)) / 1e6,
       CAST(takerAmountFilled AS DECIMAL(38,0)) / 1e6,
       fee, 'neg_risk'
FROM polymarket_polygon.negriskctfexchange_evt_orderfilled
WHERE evt_block_time >= TIMESTAMP '2025-04-01'
  AND CAST(makerAmountFilled AS DECIMAL(38,0)) / 1e6 >= 5000;

-- Q2 : tous les trades des wallets ground truth (18 cas + sharps)
-- ~500K rows, ~400 credits
-- WHERE maker IN (<28 adresses wallets.csv>) OR taker IN (...)

-- Q3 : résolutions 12 mois
-- ~30-50K rows, ~200 credits
SELECT conditionId, oracle, questionId, outcomeSlotCount,
       payoutNumerators, evt_block_time
FROM gnosis_polygon.conditionaltokens_evt_conditionresolution
WHERE evt_block_time >= TIMESTAMP '2025-04-01';

-- Q4 : ProxyCreation events (factories Polymarket)
-- Via Alchemy RPC plutôt que Dune (économise credits)
```

**Estimation conso Dune free tier** : Q1 (~800) + Q2 (~400) + Q3 (~200) + marge queries ad-hoc (~600) = **~2 000 / 2 500 credits**. Ça passe, mais serré. **Plan B** : si on dépasse, split Q1 par trimestre (4 queries plus petites) ou bascule sur Flipside free. **Plan C** : Dune Plus 49 $ pour 1 mois ponctuel.

**Goldsky subgraphs (gratuit, ~50 req/s)**

Subgraphs Polymarket publics :
- `polymarket-matic/activity-polygon/prod` — FilledOrder, activity
- `polymarket-matic/positions-subgraph/prod` — positions CTF, balances
- `polymarket-matic/pnl-subgraph/prod` — PnL pré-calculé (cross-check)

```graphql
# Exemple : trades d'un wallet sur un marché spécifique
query WalletTrades($wallet: Bytes!, $market: Bytes!, $first: Int!, $skip: Int!) {
  filledOrders(
    where: { maker: $wallet, market: $market }
    orderBy: timestamp
    orderDirection: asc
    first: $first
    skip: $skip
  ) {
    id
    transactionHash
    timestamp
    maker
    taker
    makerAssetId
    takerAssetId
    makerAmountFilled
    takerAmountFilled
    fee
  }
}
```

Usage principal : compléter Dune pour les requêtes par wallet (plus granulaire, pas de limite de credits). Cross-check Dune vs Goldsky sur un échantillon pour vérifier la cohérence.

**API CLOB Polymarket (gratuit, ~100 req/10s)**

```
GET https://clob.polymarket.com/prices-history?market=<condition_id>&interval=1h&fidelity=60
GET https://clob.polymarket.com/book?token_id=<erc1155_id>
GET https://clob.polymarket.com/trades?market=<condition_id>
```

Usage : historique des prix (OHLC) pour les marchés ground truth, snapshots book pour mesurer liquidité. Auth Level 0 (read-only, pas de clé).

```python
from py_clob_client.client import ClobClient
client = ClobClient("https://clob.polymarket.com")  # L0 read-only
book = client.get_order_book(token_id)
```

Rate limit : 100 req/10s. Pour backfill prix 1 000 marchés → ~3-6 h avec sleep 0.1s entre requêtes.

**API Gamma Polymarket (gratuit, ~100 req/min)**

```
GET https://gamma-api.polymarket.com/markets?limit=500&offset=0&active=true
GET https://gamma-api.polymarket.com/events/<event_id>
```

Usage : metadata marchés (question, catégorie, negRisk, resolution_source, dates). Bulk export : paginer `/markets?limit=500&offset=...`, ~30 pages pour tout récupérer.

**Alchemy RPC Polygon (free tier, 300M CU)**

Usage : `eth_getLogs` pour `ProxyCreation` events des deux factories Polymarket + events UMA Optimistic Oracle V2.

```python
# ProxyCreation events — Safe Proxy Factory
logs = w3.eth.get_logs({
    "fromBlock": start_block,
    "toBlock": end_block,
    "address": "0xaacFeEa03eB1561C4e67d661e40682Bd20E3541b",
    "topics": ["0x4f51faf6c4561ff95f067657e43439f0f856d97c04d9ec9070a6199ad418e235"]
})
```

Chunks de 10 000 blocs pour éviter les timeout. Estimation : ~500K events sur la période → ~1-2 h.

### 2.3 Pipeline de stockage

```
Sources externes         Extract                  Transform              Load
─────────────────        ─────────                ──────────             ────
Dune (free SQL)    ──▶  CSV export manuel    ──▶  polars DataFrames ──▶  Parquet partitionné
Goldsky (GraphQL)  ──▶  httpx pagination     ──▶  polars lazy      ──▶  par mois dans
CLOB API           ──▶  httpx async batch    ──▶  JSON → polars    ──▶  data/raw/<table>/
Gamma API          ──▶  httpx pagination     ──▶  JSON → polars    ──▶  year=YYYY/month=MM/
Alchemy RPC        ──▶  eth_getLogs batch    ──▶  decode ABI       ──▶  *.parquet
```

```python
# Pattern d'écriture Parquet partitionné avec polars
import polars as pl

df = pl.read_parquet("data/raw/trades/*.parquet")
# Analyse avec DuckDB SQL sur Parquet directement :
import duckdb
con = duckdb.connect()
result = con.execute("""
    SELECT maker, COUNT(*) AS n, SUM(maker_usd) AS vol
    FROM read_parquet('data/raw/trades/**/*.parquet', hive_partitioning=true)
    WHERE maker_usd >= 5000
    GROUP BY maker
    ORDER BY vol DESC
    LIMIT 100
""").pl()
```

Tout tourne en local (laptop). Pas de VPS en phase C.

### 2.4 Volumes et temps de backfill estimés

| Dataset | Volume | Source | Temps machine | Temps dev |
|---------|--------|--------|---------------|-----------|
| Trades > $5K 12 mois | ~2M rows | Dune Q1 | 30 min | 1 h |
| Trades wallets ground truth | ~500K rows | Dune Q2 | 15 min | 1 h |
| Résolutions 12 mois | ~40K rows | Dune Q3 | 10 min | 30 min |
| Metadata marchés | ~50K rows | Gamma API paginé | 1 h | 30 min |
| ProxyCreation events | ~500K events | Alchemy RPC | 1-2 h | 1 h |
| Prix OHLC top 500 marchés | ~500K points | CLOB /prices-history | 3 h | 1 h |
| UMA résolutions/disputes | ~5K events | Alchemy RPC | 30 min | 30 min |
| Trades cluster Iran (7 wallets) | ~5K trades | Goldsky GraphQL | 10 min | 30 min |

**Total** : ~8 h machine (background) + ~6 h dev humain.

### 2.5 Gotchas techniques — procédures

**(G1) USDC.e vs USDC native**

Migration août 2023. Notre fenêtre principale (avril 2025+) est post-migration → USDC native seul (`0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359`). Pour le stretch Théo (oct-nov 2024), **vérification obligatoire** :

```sql
-- Check : quel % des trades Théo sont en USDC.e ?
SELECT
  CASE WHEN takerAssetId LIKE '0x2791%' THEN 'usdc_e' ELSE 'usdc_native' END AS token,
  COUNT(*) AS n
FROM polymarket_polygon.ctfexchange_evt_orderfilled
WHERE evt_block_time BETWEEN '2024-10-01' AND '2024-11-15'
  AND maker IN ('0x1f2dd6d473f3e824cd2f8a89d9c69fb96f6ad0cf', ...)
GROUP BY 1;
```

Si USDC.e > 5 % → inclure les deux dans le backfill Théo.

**(G2) Neg Risk vs Vanilla CTF Exchange**

Deux contrats, deux tables Dune. Les marchés multi-outcomes (présidentielle, Nobel, Next Pope) sont sur Neg Risk. Le champ `negRisk: true/false` dans Gamma API discrimine. **Règle** : requêter systématiquement les deux tables et UNION ALL, colonne `exchange` pour tracer l'origine.

Token IDs ERC-1155 différents entre les deux exchanges pour le même marché. Le `condition_id` (de Gamma) est le lien commun.

**(G3) Proxy↔EOA mapping**

Critique. Sans ce mapping, on double-compte les users uniques. Deux factories :

| Auth | Factory | Adresse |
|------|---------|---------|
| MetaMask/EOA | Safe Proxy Factory | `0xaacFeEa03eB1561C4e67d661e40682Bd20E3541b` |
| Magic/email | Polymarket Proxy Factory | `0xaB45c5A4B0c941a2F231C04C3f49182e1A254052` |

Pour Magic wallets : `proxyAddress = getCreate2Address(factory, keccak256(abi.encode(eoa)), initCodeHash)` — déterministe. Pour Safe : lire l'event `ProxyCreation` + `getOwners()`.

**Action phase C** : construire la table `proxy_eoa_map` via `eth_getLogs` sur les deux factories. C'est un **prérequis** avant toute métrique per-user.

**(G4) Finalité Polygon**

Pour du backfill historique (fenêtre > 12 mois), les reorgs sont résolus. Non-bloquant en phase C. **Note pour phase D** : attendre 64 blocs (~2 min) avant d'écrire un trade en base.

**(G5) Rate limits CLOB**

~100 req/10s en lecture. Pour un backfill prix de 500 marchés :
```python
import asyncio, httpx
async def fetch_prices(condition_ids: list[str]):
    async with httpx.AsyncClient() as c:
        for cid in condition_ids:
            resp = await c.get(f"https://clob.polymarket.com/prices-history?market={cid}&interval=1h")
            # process
            await asyncio.sleep(0.12)  # ~8 req/s, safe margin
```

**(G6) Dune free tier — stratégie de découpage**

2 500 credits/mois. Les queries lourdes (full scan 12 mois) consomment ~500-800 credits chacune. Stratégie :
- Découper par trimestre si une query dépasse le timeout (30 min free tier)
- Exporter en CSV depuis l'UI (gratuit, pas de coût API)
- Réserver ~500 credits pour les queries ad-hoc pendant l'analyse
- Si bloqué : Flipside Crypto free tier comme fallback (tables Polygon similaires)

---

## 3. Protocole backtest C1 — Sharp Money Copy (50 % effort, ~15-20 h)

### 3.1 Vue d'ensemble C1

Le composant C1 doit identifier des wallets genuinely skilled pour copier leurs trades. Le test méthodologique est le plus délicat : il faut prouver qu'on peut constituer un leaderboard fiable sans seed list, avec correction du multiple testing, et filtrer les honeypots.

### E1 — Leaderboard FDR-BH sans seed list

**Question** : un leaderboard basé sur BSS/edge/CLV post-FDR-BH identifie-t-il correctement les sharps connus (Domer, Aenews2, Kickstand7, gopfan2, HolyMoses7, Beachboy4) dans le top sans les chercher ?

**Données nécessaires** :
- Tous les trades `OrderFilled` sur 12 mois (Dune Q1+Q2, ~2.5M rows)
- Résolutions des marchés (Dune Q3)
- Table `proxy_eoa_map` pour agréger par user réel
- Metadata marchés Gamma (catégorie, negRisk)

**Méthode** :

```python
# Pseudo-code leaderboard FDR-BH

# 1. Reconstruire PnL trade-par-trade (flux nets USDC)
for wallet in all_wallets:
    for trade in wallet.trades:
        # edge_i = s_i * (outcome_i - p_entry_i)
        # s_i = +1 pour BUY YES, -1 pour BUY NO
        edge = side * (resolution - entry_price)
        trades_edges.append(edge)

# 2. Filtrer wallets avec N suffisant
eligible = [w for w in wallets if
    w.n_trades_resolved >= 100 and
    w.n_markets_distinct >= 20 and
    w.n_categories >= 3 and
    w.hhi_markets < 0.20]

# 3. Pour chaque wallet éligible, t-stat sur edge réalisé
for w in eligible:
    t_stat = mean(w.edges) * sqrt(len(w.edges)) / std(w.edges)
    p_value = 1 - t_distribution.cdf(t_stat, df=len(w.edges)-1)  # one-sided

# 4. FDR Benjamini-Hochberg à q = 0.10
from scipy.stats import false_discovery_control
rejected = false_discovery_control(p_values, method='bh', alpha=0.10)

# 5. Trier les rejetés par t-stat décroissant = leaderboard final
```

**Métriques calculées par wallet** :

| Métrique | Formule | Seuil min tracking |
|----------|---------|-------------------|
| Edge post-résolution | $\bar{e} = \frac{1}{N}\sum s_i(o_i - p_i)$ | > 3 cents/trade |
| CLV | $\text{CLV}_i = p_{close,T-1h} - p_{entry}$ | > 2 cents/trade |
| Brier Skill Score (BSS) | $1 - \text{BS}_{wallet}/\text{BS}_{market}$ | > 0.05 |
| Log score | $-\frac{1}{N}\sum[o_i\log p_i + (1-o_i)\log(1-p_i)]$ | < baseline |
| t-stat edge | $\bar{e}\sqrt{N}/\sigma_e$ | > 2.0 pre-FDR |

**Critère de succès** : ≥ 5 des 6 sharps individuels (Domer `0x9d84...`, Aenews2 `0x44c1...`, Kickstand7 `0xd1ac...`, gopfan2 `0xf2f6...`, HolyMoses7 `0xa4b3...`, Beachboy4 `0xc2e7...`) apparaissent dans le top 100 du leaderboard FDR-BH **sans les avoir injectés en seed list**.

**Temps estimé** : 6-8 h (la plus grosse expérience de la phase C).

**Risques** :
- Beachboy4 risque de ne pas passer le filtre `n_categories >= 3` (sports exclusif) → comportement attendu du filtre, documenter.
- Si < 5 000 wallets passent le filtre `N >= 100`, la correction FDR est moins puissante → abaisser à `N >= 50` et documenter.
- Si les tables Dune ne couvrent pas proprement les deux exchanges → fallback Goldsky pour cross-check.

---

### E2 — Identifier N nouveaux sharps hors seed list

**Question** : le leaderboard C1 fait-il émerger des wallets intéressants qu'on n'aurait jamais trouvés autrement ?

**Données nécessaires** : leaderboard E1 + pages profil Polymarket pour investigation manuelle.

**Méthode** :
1. Prendre le top 50 du leaderboard E1 hors wallets déjà dans `sharps_positive.csv`.
2. Pour chaque wallet, investigation manuelle (~5 min/wallet) : page `polymarket.com/profile/<address>`, pattern trades (diversification, timing, sizing), recherche username sur X.
3. Classifier : "plausibly skilled" / "market maker-arbitrageur" / "one-hit wonder" / "suspect honeypot".

**Métriques** :
- Nb wallets "plausibly skilled" parmi top 50 hors seed
- BSS moyen du top 20 vs BSS moyen du percentile 80-100 (ratio attendu > 3x)

**Critère de succès** : ≥ 5 wallets "plausibly skilled" émergent → Tier B se constituera naturellement en phase D.

**Temps estimé** : 3-4 h.

**Risques** : biais de confirmation dans la classification manuelle. Mitigation : documenter les critères de classification *avant* de regarder les wallets.

---

### E3 — Anti-honeypot : détection faux-sharps

**Question** : peut-on détecter des patterns honeypot avant qu'un faux-sharp ne piège des copieurs ?

**Données nécessaires** : leaderboard E1 + historique trades complet des wallets suspects.

**Méthode** :

```python
# Pseudo-code scoring anti-honeypot

def honeypot_score(wallet):
    score = 0.0

    # Signe 1 — Faible variance de PnL (trop régulier = suspect)
    # Un trader réel a des drawdowns ; un honeypot construit une courbe lisse
    pnl_series = wallet.cumulative_pnl_by_trade()
    if pnl_series.std() / pnl_series.mean() < 0.3:  # CV anormalement bas
        score += 0.20

    # Signe 2 — Ratio favoris vs outsiders
    # Si > 70% du PnL vient de longshots (p_entry < 0.15) qui ont hit
    longshot_pnl = sum(e for e in edges if entry_price < 0.15 and edge > 0)
    if longshot_pnl / total_pnl > 0.70:
        score += 0.25

    # Signe 3 — Volume burst (trades petits puis soudain gros)
    sizes = wallet.trade_sizes()
    recent_max = sizes[-10:].max()
    historical_median = sizes[:-10].median()
    if recent_max / historical_median > 10:
        score += 0.20

    # Signe 4 — Funding corrélé (shared CEX deposit avec N autres)
    if wallet.shared_deposit_cluster_size > 3:
        score += 0.15

    # Signe 5 — CLV proche de zéro malgré PnL positif
    # Edge post-résolution > 0 mais CLV ≈ 0 = pas de price discovery
    if wallet.edge_per_trade > 0.03 and abs(wallet.clv_per_trade) < 0.005:
        score += 0.20

    return min(score, 1.0)
```

Test sur 3 personas synthétiques injectées en DuckDB :
- **Persona A (jackpot hunter)** : 80 % trades petits gagnants sur longshots, 20 % gros trades illiquides
- **Persona B (track record farmer)** : 200 trades gagnants constants < $300, puis 1 grosse position inverse
- **Persona C (wash-trading sybil)** : 2 wallets self-matched sur 20 marchés thin

Validation croisée : les 6 sharps connus doivent obtenir `honeypot_score < 0.20`.

**Critère de succès** : 3/3 personas flaggés (> 0.40) + 0 faux positif parmi les 6 sharps.

**Temps estimé** : 3-4 h.

**Risques** : valeur épistémique limitée (cas synthétiques, pas de ground truth réelle). C'est un sanity check, pas une validation forte. Le monitoring in-vivo en phase D sera plus informatif.

---

### E4 — Filtre anti-MM et anti-arbitrageur

**Question** : les market makers professionnels (Wintermute-like) et les arbitrageurs sont-ils correctement exclus du leaderboard C1 ?

**Données nécessaires** : leaderboard E1 + trades détaillés des wallets top 200.

**Méthode** :

```python
# Net-to-gross ratio : MM < 0.10, directionnel > 0.80
net_to_gross = abs(sum(signed_notional)) / sum(abs(notional))

# Ratio maker/taker : MM > 0.70 côté maker
maker_ratio = n_trades_as_maker / n_trades_total

# Symétrie positions : MM hedgé, insider directionnel
position_skew = abs(net_yes - net_no) / (net_yes + net_no)
```

**Critère de succès** : aucun wallet avec `net_to_gross < 0.15` ET `maker_ratio > 0.60` dans le top 50 du leaderboard. Si présents, ajouter le filtre en preprocessing.

**Temps estimé** : 2-3 h.

---

### E5 — Test de cohérence : retrouver les sharps sans les chercher

**Question** : si on part d'un univers vierge (aucune connaissance des noms/usernames), le leaderboard E1 converge-t-il vers les mêmes personnes ?

**Données nécessaires** : leaderboard E1 final.

**Méthode** : vérifier la correspondance entre les adresses du leaderboard top 100 et les adresses de `sharps_positive.csv`. Calculer le rank de chaque sharp connu. Tracer la courbe de précision@k pour k=10,20,50,100.

**Critère de succès** : Domer dans le top 20. ≥ 4 sharps dans le top 50. Courbe precision@k monotone décroissante (pas de "trou" suspect).

**Temps estimé** : 1-2 h (dépend du résultat E1).

---

## 4. Protocole backtest C2 — Informed Trading Alert (35 % effort, ~10-14 h)

### 4.1 Split train/test temporel

Coupure au **1er juillet 2025**. Les heuristiques sont évaluées sur train, appliquées sans modification sur test.

**Train (événements avant juillet 2025)** — 6 cas :

| case_id | Nom | Date event | Adresses connues |
|---------|-----|------------|-----------------|
| 1 | French Whale Théo | Nov 2024 | 4 (+ 7 Chainalysis non publiées) |
| 5 | Biden pardons | Déc 2024-Jan 2025 | 0 (masquées NPR) |
| 7 | Conclave Pope Leo XIV | Mai 2025 | 0 |
| 13 | Pope Francis decease | Avr 2025 | 1 (syncope — sharp, pas insider) |
| 14 | Sethi derivative manipulation | Sep 2024 | 0 |
| 17 | UMA oracle manipulation | Mar-Jul 2025 | 0 |

**Test (événements après juillet 2025)** — 11 cas :

| case_id | Nom | Date event | Adresses connues |
|---------|-----|------------|-----------------|
| 2 | Iran strikes | Fév 2026 | 7 (cluster complet) |
| 3 | Maduro capture | Jan 2026 | 2 (+1 manquante) |
| 4 | Axiom/ZachXBT | Fév 2026 | 2 (+3 partielles) |
| 6 | Nobel Peace Prize | Oct 2025 | 1 (dirtycup) |
| 8 | Super Bowl halftime | Fév 2026 | 1 |
| 9 | AlphaRaccoon Google | Déc 2025 | 0 (tronquée) |
| 10 | Spotify Wrapped | Déc 2025 | 0 |
| 11 | Ricosuave Israel | Jun 2025+ | 1 |
| 12 | Taylor Swift engagement | Août 2025 | 1 (romanticpaul) |
| 15 | XRP a4385 | Jan 2026 | 1 |
| 18 | AI markets OpenAI | Déc 2025 | 0 |

**Cas exclus du scoring C2** : cas 16 (wash trading systémique — filtre de preprocessing, pas un cas informé), cas 13 (sharp money actuariel, pas insider).

**Observation importante** : le train set a **peu d'adresses connues** (surtout Théo). C'est une limite assumée. On utilise le train principalement pour vérifier que les seuils publiés du rapport 3 sont dans le bon ordre de grandeur. Le vrai test se fait sur le test set (Iran, Maduro, Axiom, Nobel) où on a les adresses.

### E6 — Notebook pilote Iran strikes (partagé avec validation pipeline)

Voir §6 (Specs du notebook pilote) pour le détail complet. En résumé :

**Question** : peut-on reconstituer le cluster Iran (7 wallets) depuis données publiques et le flagger avec les heuristiques Niveau A ?

**Critère de succès C2** : ≥ 5/7 wallets Iran flaggés par l'heuristique `fresh_wallet AND concentration > 0.90 AND time_to_event < 48h AND (niche OR shared_cex)`.

**Temps estimé** : 6-8 h (le plus gros bloc de la phase C, partagé entre validation pipeline et C2).

---

### E7 — Calibration heuristiques C2 Niveau A

**Question** : les seuils du rapport 3 (wallet_age < 30j, concentration > 0.90, time_to_event < 48h) sont-ils correctement calibrés sur nos données ?

**Données nécessaires** :
- Features calculées en runtime sur les wallets des cas train (adresses connues)
- Échantillon témoin : tous les trades > $5K dans une fenêtre de 30 jours **avant** chaque event date du train set, sur le même marché

**Méthode** :
1. Pour chaque wallet ground truth du train set, calculer les 5 features C2 Niveau A.
2. Pour chaque cas, constituer un échantillon témoin : tous les wallets ayant tradé > $5K sur ce marché dans les 30 jours pré-event.
3. Tracer les distributions de chaque feature (cas connus vs témoins).
4. Identifier les seuils par Youden's J = max(TPR - FPR).
5. Comparer seuils obtenus vs seuils publiés rapport 3.

**Les 5 features C2 Niveau A** (calculées en runtime, pas hardcodées en CSV) :

```python
def compute_c2_features(wallet_address, market_condition_id, event_date):
    # 1. wallet_age_days
    proxy_creation_ts = proxy_eoa_map[wallet_address].created_at
    first_trade_ts = trades.filter(maker=wallet).min("timestamp")
    wallet_age = (first_trade_ts - proxy_creation_ts).days

    # 2. concentration_ratio
    volume_this_outcome = trades.filter(maker=wallet, market=market).sum("usd")
    volume_total = trades.filter(maker=wallet).sum("usd")
    concentration = volume_this_outcome / volume_total

    # 3. time_to_event_hours
    last_trade_ts = trades.filter(maker=wallet, market=market).max("timestamp")
    time_to_event = (event_date - last_trade_ts).total_seconds() / 3600

    # 4. shared_cex_deposit (Victor 2020 heuristic)
    # Remonter les transferts USDC entrants, identifier deposit addresses communes
    funding_sources = trace_funding(wallet_address, depth=2)
    shared = find_shared_deposit_addresses(funding_sources, known_cex_hot_wallets)

    # 5. niche_market_flag
    market_volume = markets[market_condition_id].volume_cumulative_usd
    niche = market_volume < 50_000

    return {wallet_age, concentration, time_to_event, shared, niche}
```

**Critère de succès** : les seuils publiés sont dans l'ordre de grandeur correct (écart < 30 % par rapport aux seuils Youden). On ne modifie les seuils que si l'évidence est forte ET stable (bootstrap N=1000).

**Temps estimé** : 2-3 h.

**Risques** : train set pauvre en adresses connues (surtout Théo, qui est ambigu). Si train set insuffisant, on documente et on reporte la calibration fine sur le test set en mode exploratoire (pas de tuning, juste observation).

---

### E8 — Test C2 sur test set + base rate faux positifs

**Question** : le C2 calibré retrouve-t-il les cas du test set, et avec quelle precision estimée ?

**Données nécessaires** :
- Tous les trades > $5K sur la fenêtre test (juillet 2025 → avril 2026), tous marchés > $100K volume cumulé
- Les 11 cas du test set avec adresses connues
- Estimation : 50-150K trades éligibles

**Méthode** :
1. Appliquer l'heuristique Niveau A (seuils rapport 3, non modifiés sur test) sur tous les trades éligibles.
2. Pour chaque flag, annoter : matche-t-il un wallet de `wallets.csv` test set ?
3. Pour les 50 flags les mieux scorés non-matchés : annotation manuelle rapide (wallet profitable sur event à catalyseur public identifiable ? recherche rapide X, Reuters).
4. Calculer :
   - **Recall** = cas retrouvés / cas test set avec adresses connues
   - **Precision borne basse** = flags matchant cas connus / total flags
   - **Precision borne haute** = (matchs cas connus + matchs wallets profitables post-event) / total flags
   - **Taux de flag** = total flags / total trades éligibles (base rate)

**Critère de succès** :
- Recall ≥ 60 % (≥ 6/10 cas avec adresses connues retrouvés)
- Precision borne haute ≥ 20 %
- Pas de flag Domer/Aenews2/Kickstand7 dans les top 50 flags

**Temps estimé** : 2-3 h.

**Risques** :
- Les cas sans adresse connue (AlphaRaccoon, Spotify, OpenAI) ne contribuent pas au recall → recall maximal théorique = 7/10 avec les adresses qu'on a. Ajuster le seuil en conséquence.
- Base rate trop élevé (> 5 % des trades flaggés) → heuristique trop loose, strict-er les seuils.

---

### E9 — Test discriminant C2 sur sharps positifs

**Question** : les sharps connus sont-ils flaggés par C2 ? Idéalement non.

**Données nécessaires** : trades > $5K des 6 sharps sur la fenêtre test.

**Méthode** :
1. Pour chaque sharp, récupérer leurs trades > $5K sur la fenêtre test.
2. Appliquer l'heuristique C2. Compter le % de trades flaggés.
3. Comparer le score composite moyen sharps vs insiders test set.

**Résultat attendu** :
- Domer : wallet_age > 4 ans, 9 500+ trades, diversifié → 0 flags attendus
- Beachboy4 : potentiellement flaggé sur son gros jour sports si marché thin → cas intéressant à documenter

**Critère de succès** : < 5 % des trades sharps flaggés, score composite sharps << insiders. Si > 20 % → ajouter filtre `wallet_age > 180d AND distinct_markets > 50 → exempt sauf 4+ signaux forts simultanés`.

**Temps estimé** : 1-2 h.

---

## 5. Protocole backtest C3 — Resolution Risk Filter (15 % effort, ~4-6 h)

### E10 — Construction `markets_disputed.csv`

**Question** : quels marchés historiques ont été disputés ou ambigus, et quel score attendons-nous ?

**Données nécessaires** : rapport 3 (cas 17 UMA oracle, cas documentés de disputes), UMA subgraph pour disputes historiques.

**Méthode** : extraction manuelle des cas du rapport 3 + recherche rapide UMA events.

**Schéma** :
```
market_id, market_question, dispute_date, dispute_outcome,
ambiguity_category, liquidity_at_dispute_usd, notes, source_urls
```

`ambiguity_category` ∈ {`ancillary_data`, `definitional`, `source_failure`, `oracle_attack`}

**Cas à inclure** (minimum 5-8) :

| Marché | Catégorie | Score attendu |
|--------|-----------|--------------|
| Zelensky suit NATO Summit ($237M) | definitional | CRITICAL |
| Ukraine mineral deal ($7M) | oracle_attack | CRITICAL |
| TikTok ban US ($120M) | definitional | HIGH |
| Pope Francis step down / remain | ancillary_data | MEDIUM |
| Présidentielle US 2024 (contrôle) | — | LOW |
| Bitcoin ATH > $X (contrôle) | — | LOW |
| Super Bowl winner (contrôle) | — | LOW |

**Critère de succès** : fichier CSV complet, ≥ 5 cas disputés + ≥ 3 contrôles.

**Temps estimé** : 1 h.

---

### E11 — LLM scoring ambiguïté (Claude Haiku)

**Question** : Claude Haiku avec un prompt structuré score-t-il correctement les marchés disputés vs non-disputés ?

**Données nécessaires** : `markets_disputed.csv` + metadata Gamma (question, description, resolution_source, outcomes).

**Méthode** :

```python
import anthropic

client = anthropic.Anthropic()

def score_ambiguity(market: dict) -> dict:
    prompt = f"""Analyze this prediction market for resolution ambiguity risk.

Market question: {market['question']}
Description: {market['description']}
Resolution source: {market['resolution_source']}
Outcomes: {market['outcomes']}

Rate the ambiguity risk on a scale of 0.0 to 1.0 where:
- 0.0 = completely unambiguous, single correct resolution
- 1.0 = fundamentally unresolvable or manipulable

Return JSON: {{"ambiguity_score": float, "reasons": [str], "red_flags": [str]}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(response.content[0].text)
```

Combiner avec rules dynamiques :

```python
def resolution_risk(market, llm_score):
    # Rules dynamiques
    dispute_rate = historical_dispute_rate_by_category(market['category'])
    oracle_reliable = is_reliable_source(market['resolution_source'])  # Reuters/AP = 1.0, Twitter = 0.3

    rules_score = 0.5 * dispute_rate / 0.10 + 0.5 * (1 - oracle_reliable)
    rules_score = min(rules_score, 1.0)

    # Composite
    risk = 0.50 * llm_score + 0.30 * rules_score + 0.20 * (1 - oracle_reliable)

    label = "LOW" if risk < 0.25 else "MEDIUM" if risk < 0.50 else "HIGH" if risk < 0.75 else "CRITICAL"
    return risk, label
```

**Métriques** :
- Accord catégoriel : score LLM+rules vs `expected_risk_score` dans CSV
- Matrice de confusion 4×4 (LOW/MED/HIGH/CRIT)
- Erreurs critiques : LOW classé CRITICAL ou inverse (inacceptable)

**Critère de succès** : accord catégoriel ≥ 70 %. 100 % des cas CRITICAL (Zelensky, Ukraine minerals) correctement classés. 0 erreur à 2+ catégories d'écart.

**Coût estimé Haiku** : 8 marchés × ~700 tokens × pricing Haiku ≈ **$0.01**. Négligeable.

**Temps estimé** : 2-3 h (itération prompt incluse).

**Risques** : le prompt initial peut sous-performer. Mitigation : 2-3 itérations de prompt avec few-shot examples si accord < 60 %.

---

### E12 — Calibration pondérations C3

**Question** : la pondération 50/30/20 (LLM/rules/oracle) est-elle correcte ?

**Données nécessaires** : scores E11 décomposés par composante.

**Méthode** : pour chaque marché, tracer quelle composante (LLM, rules, oracle) était la plus discriminante pour les cas correctement classés vs incorrects. Si une composante domine systématiquement, ajuster les poids.

**Critère de succès** : poids ajustés documentés. Pas de composante avec poids < 0.10 (sinon autant la supprimer).

**Temps estimé** : 1 h.

---

## 6. Specs du notebook pilote

### 6.1 Cas pilote : Iran strikes (cluster Bubblemaps)

**Pourquoi Iran et pas Maduro** :
- Cluster complet : 7 adresses récupérées (6 cluster + Magamyman), dont 3 avec profil 404 (signature de suppression post-exposure)
- Timing pré-event net : Magamyman trade 71 min avant annonce publique
- Fresh wallet signature confirmée : Dicedicedice, Neodbs, Planktonbets tous joined 17-27 fév 2026
- Shared CEX deposit (Binance) documenté entre nothingeverhappens911 et cluster Skoobidoobnj
- Volume significatif : ~$1.5M profit combiné
- Fallback Maduro si problème d'accès data Iran

### 6.2 Objectif démonstratif

Le notebook doit prouver qu'on peut :

1. **Ingérer** les trades d'un marché spécifique depuis Goldsky/Dune dans DuckDB+polars
2. **Calculer** les 5 features Niveau A en runtime pour chaque wallet
3. **Flagger** les wallets suspects sans connaître la liste
4. **Mesurer** le taux de faux positifs sur échantillon témoin (tous les traders du même marché qui n'ont pas été flaggés)
5. **Comparer** les résultats avec le ground truth (wallets.csv)

### 6.3 Structure du notebook

```
notebooks/pilot_iran_strikes.ipynb

Cellule 1 — Setup
  - imports, connexion DuckDB, chargement ground truth CSVs

Cellule 2 — Ingestion
  - Récupérer condition_id du marché "US strikes Iran Feb 28" via Gamma API
  - Pull tous les OrderFilled sur ce marché via Goldsky subgraph
  - Pull ProxyCreation events pour les wallets traders
  - Stocker en Parquet local

Cellule 3 — Exploration
  - Stats descriptives : nb traders, distribution tailles, timeline des trades
  - Identifier les top 20 traders par volume
  - Visualiser la timeline prix vs volume

Cellule 4 — Feature engineering C2
  - Pour chaque trader : wallet_age, concentration, time_to_event, niche_flag
  - Pour shared_cex_deposit : tracer les 2 premiers hops de funding via Alchemy RPC

Cellule 5 — Flagging
  - Appliquer heuristique Niveau A (seuils rapport 3)
  - Produire un tableau : wallet | features | flagged | ground_truth_match

Cellule 6 — Évaluation
  - Recall : combien des 7 wallets ground truth sont flaggés ?
  - Faux positifs : combien de wallets non-ground-truth sont flaggés ?
  - Distribution des scores : flaggés ground truth vs flaggés non-ground-truth

Cellule 7 — Verdict
  - Tableau récap
  - Décision : la stack tient ? les seuils tiennent ?
  - Points à ajuster pour la phase D
```

### 6.4 Décisions à prendre après le pilote

| Question | Si oui | Si non |
|----------|--------|--------|
| La stack DuckDB+polars+Goldsky tient en local ? | Continuer sur cette stack en phase D | Migrer vers MotherDuck ($25/mo) ou ClickHouse Cloud |
| Les seuils Niveau A flagguent ≥ 5/7 wallets Iran ? | Valider les seuils, passer aux tests C1 | Revoir les seuils ou ajouter des features |
| Le taux de faux positifs est < 10 % ? | Seuils acceptables pour v1 | Strict-er les seuils ou ajouter des filtres (anti-MM, wallet age) |
| Le backfill Goldsky couvre la période sans trou ? | Goldsky = source primaire | Basculer sur Dune pour les données historiques |

### 6.5 Temps estimé : 6-8 h

Répartition :
- Ingestion + plomberie : 2-3 h
- Feature engineering : 2 h
- Flagging + évaluation : 1-2 h
- Documentation + verdict : 1 h

---

## 7. Risques et gotchas techniques

### 7.1 Matrice de risques

| # | Risque | Probabilité | Impact | Mitigation |
|---|--------|-------------|--------|------------|
| R1 | Dune free tier bloque le backfill 12 mois (timeout ou credits) | Moyenne | Élevé | Découper par trimestre. Plan B : Flipside free. Plan C : Dune Plus 49 $ ponctuel 1 mois |
| R2 | Goldsky subgraph trou sur la période Iran (fév 2026) | Faible | Moyen | Cross-check Dune sur échantillon. Si trous > 2 % : Dune seul pour cette période |
| R3 | Overfitting sur N=18 cas | Élevée | Élevé | Split temporel strict. Seuils publiés comme priors. Pas de grid search. Documentation honnête |
| R4 | C2 flag Théo et sharps → discriminabilité faible | Haute | Moyen | **Attendu et documenté.** L'architecture assume : C2 + C3 + humain en loop. Pas un bug |
| R5 | Adresses manquantes limitent le recall C2 | Certaine | Moyen | Recall max théorique ~7/11 sur test set. On accepte et on ajuste le seuil |
| R6 | Anti-honeypot non testable sur cas réels | Certaine | Faible | Cas synthétiques (E3). Monitoring in-vivo en phase D |
| R7 | Concept drift post-exposure | Certaine | Faible | Hors scope phase C. Point à traiter en phase D ops |
| R8 | DuckDB + polars rame sur 2.5M trades en local | Faible | Moyen | polars lazy + scan_parquet gère des centaines de millions de rows. Si problème : DuckDB direct sur Parquet sans charger en RAM |

### 7.2 Gotchas techniques détaillés

**(G1) USDC.e vs USDC native (migration août 2023)**

| Période | Token USDC | Adresse |
|---------|-----------|---------|
| Avant août 2023 | USDC.e (bridged) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |
| Après août 2023 | USDC native (Circle CCTP) | `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359` |

Notre fenêtre principale (avril 2025+) est entièrement post-migration. Pour le stretch Théo (oct-nov 2024), la migration était "progressive" → vérifier avec la query SQL du §2.5.

**(G2) Neg Risk vs Vanilla CTF Exchange**

| Exchange | Contrat | Usage |
|----------|---------|-------|
| Vanilla CTFExchange | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` | Marchés binaires indépendants |
| NegRisk CTFExchange | Même adresse, via Neg Risk Adapter `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296` | Multi-outcomes (élections, Next Pope, Nobel) |

Les **token IDs ERC-1155 diffèrent** entre les deux pour le même outcome. Le `condition_id` (Gamma) est le dénominateur commun. Toujours joindre via `condition_id`, jamais via `token_id` seul.

**(G3) Dune free tier : 2 500 credits**

| Query type | Credits estimés | Fréquence phase C |
|-----------|----------------|-------------------|
| Full scan 12 mois trades | ~800 | 1-2 fois |
| Scan wallets ground truth | ~400 | 1 fois |
| Résolutions 12 mois | ~200 | 1 fois |
| Queries ad-hoc | ~100 chacune | 5-6 fois |

**Total estimé** : ~2 000 credits. Marge de 500 pour itérations. Si dépassement → export CSV UI (gratuit, unlimited) comme fallback.

**(G4) Rate limits CLOB**

~100 req/10s. Pour un batch de 500 marchés :
- Sleep 0.12s entre requêtes = ~8 req/s = safe
- Backoff exponentiel sur 429 : 2s → 4s → 8s → cap 60s
- Après 3 échecs consécutifs : abandon de la batch, alert dans le notebook

**(G5) Reorgs Polygon**

Non-bloquant en phase C (données historiques). **Règle phase D** : attendre 64 blocs (~2 min) avant de considérer un event final. Pour events UMA critiques (résolutions), attendre checkpoint Heimdall (~30 min).

**(G6) Proxy↔EOA mapping : ProxyCreation events**

Deux sources d'events, deux méthodes de résolution :

```python
# Safe Proxy Factory — event ProxyCreation(address proxy)
# L'owner est lisible via getOwners() call sur le proxy
SAFE_FACTORY = "0xaacFeEa03eB1561C4e67d661e40682Bd20E3541b"
SAFE_TOPIC = "0x4f51faf6c4561ff95f067657e43439f0f856d97c04d9ec9070a6199ad418e235"

# Polymarket Proxy Factory — déterministe CREATE2
# proxy = getCreate2Address(factory, keccak256(abi.encode(eoa)), initCodeHash)
PM_FACTORY = "0xaB45c5A4B0c941a2F231C04C3f49182e1A254052"
```

**Attention** : certains wallets ont plusieurs proxies (MetaMask + Magic avec EOA différents). Le clustering Victor deposit-address-reuse est le seul moyen de les relier. Ce mapping est un **prérequis** avant E1 (leaderboard).

---

## 8. Planning semaine par semaine

### Semaine 1 (~15-20 h) — Ground truth + ingestion + pilote début

| Jour | Tâche | Exp. | Temps |
|------|-------|------|-------|
| 1 | Créer `markets_disputed.csv` (5-8 cas + contrôles) | E10 | 1 h |
| 1-2 | Scripts d'ingestion : Dune export, Goldsky pagination, Alchemy ProxyCreation | Setup | 3-4 h |
| 2-3 | Backfill : trades > $5K 12 mois + trades wallets ground truth + résolutions | Setup | 3 h dev (8 h machine background) |
| 3-4 | Construire `proxy_eoa_map` pour les wallets actifs | Setup | 2 h |
| 4-5 | **Notebook pilote Iran** : ingestion + exploration + features | E6 | 4-5 h |

**Gate 1 (fin semaine 1)** : données ingérées, proxy_eoa_map construit, pilote Iran en cours.

### Semaine 2 (~15-20 h) — Pilote fin + C1 + C2 + C3

| Jour | Tâche | Exp. | Temps |
|------|-------|------|-------|
| 1 | **Pilote Iran** : flagging + évaluation + verdict | E6 | 2-3 h |
| 1-2 | Leaderboard FDR-BH sans seed list | E1 | 6-8 h |
| 2-3 | Identifier nouveaux sharps + anti-honeypot + anti-MM | E2,E3,E4 | 4-5 h |
| 3 | Cohérence sharps connus dans leaderboard | E5 | 1 h |
| 4 | Test C2 sur test set + base rate + discriminant sharps | E7,E8,E9 | 3-4 h |
| 4-5 | LLM scoring C3 + calibration | E11,E12 | 2-3 h |
| 5 | Gate 2 : revue des résultats, décision GO/AJUSTER/PIVOTER | — | 1 h |

**Stretch (si temps)** : Théo (4-6 h), Maduro (3-4 h).

---

## 9. Récap des expériences

| # | Expérience | Composant | Question | Données | Critère de succès | Temps |
|---|-----------|-----------|----------|---------|-------------------|-------|
| E1 | Leaderboard FDR-BH | C1 | Retrouve-t-on les sharps connus sans seed ? | Dune Q1+Q2+Q3, proxy_eoa_map | ≥ 5/6 sharps dans top 100 | 6-8 h |
| E2 | Nouveaux sharps | C1 | Le leaderboard fait-il émerger des inconnus ? | Leaderboard E1 + profils PM | ≥ 5 wallets "plausibly skilled" | 3-4 h |
| E3 | Anti-honeypot | C1 | Détecte-t-on des patterns honeypot ? | 3 personas synthétiques + sharps | 3/3 flaggés, 0 FP sur 6 sharps | 3-4 h |
| E4 | Anti-MM/arb | C1 | Les MMs sont-ils exclus du leaderboard ? | net-to-gross + maker_ratio | 0 MM dans top 50 | 2-3 h |
| E5 | Cohérence | C1 | Domer dans top 20 sans le chercher ? | Leaderboard E1 | Domer top 20, ≥ 4 sharps top 50 | 1-2 h |
| E6 | Pilote Iran | C2+Infra | Reconstituer cluster + flagger | Goldsky, Dune, Alchemy | ≥ 5/7 wallets flaggés, FP < 10% | 6-8 h |
| E7 | Calibration C2 | C2 | Seuils publiés OK ? | Features train set + témoins | Écart < 30 % vs Youden | 2-3 h |
| E8 | Test C2 test set | C2 | Recall + precision bornée | Trades > $5K test set | Recall ≥ 60 %, precision haute ≥ 20 % | 2-3 h |
| E9 | Discriminant sharps | C2 | Sharps non flaggés ? | Trades sharps test set | < 5 % trades flaggés | 1-2 h |
| E10 | markets_disputed.csv | C3 | Ground truth disputes | Rapport 3, UMA events | ≥ 5 disputés + ≥ 3 contrôles | 1 h |
| E11 | LLM scoring | C3 | Haiku score correctement ? | markets_disputed + Gamma | Accord ≥ 70 %, CRITICAL 100 % | 2-3 h |
| E12 | Calibration C3 | C3 | Poids 50/30/20 OK ? | Scores E11 décomposés | Pas de composante < 0.10 | 1 h |

**Total** : 32-46 h. Budget de base 30-40 h couvre E1-E12 hors stretch goals.

---

## 10. Références

- `docs/reference/0_project_brief.md` — cadrage global, allocation budget, contraintes
- `docs/reference/A_architecture_technique.md` — architecture cible §2.B (C1), §2.C (C2), §2.D (C3)
- `docs/reference/3 - informed trading and sharp money.md` — 18 cas forensiques, patterns Niveau A/B/C, seuils empiriques
- `docs/reference/4_wallet_clustering.md` — FDR BH §4.3, métriques skill §4.2, Victor deposit-address-reuse §3.2, matrice priorisation §9
- `docs/reference/2_polymarket_stack_technique.md` — APIs CLOB/Gamma/Goldsky/Dune, gotchas §9
- `data/ground_truth/cases.csv` — 18 cas, enrichi via API Polymarket
- `data/ground_truth/wallets.csv` — 31 wallets, 22 avec adresse (71 %)
- `data/ground_truth/sharps_positive.csv` — 9 sharps, 6 avec adresse (67 %)
- `data/ground_truth/enrichment_log.md` — log des lookups API

*Fin du document. Passage en phase D conditionné au Gate 2 (§1.3).*
