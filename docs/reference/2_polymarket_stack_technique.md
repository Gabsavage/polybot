# Polymarket — Stack technique et accès à la data

*Rapport technique, avril 2026. Les prix et limites évoluent, vérifier les sites officiels avant d'engager du budget.*

---

## 1. Architecture Polymarket

### Le stack en une phrase

Polymarket est un **order book hybride off-chain / on-chain settlement** construit sur **Polygon PoS**, utilisant le **Conditional Token Framework (CTF) de Gnosis** pour représenter les outcomes, et **UMA Optimistic Oracle** pour résoudre les marchés. Le collatéral est de l'**USDC** (natif sur Polygon depuis 2023, anciennement USDC.e bridged).

### Les couches

**1. Conditional Token Framework (CTF) — Gnosis**

Le CTF est le standard ERC-1155 qui permet de représenter des outcomes conditionnels comme tokens fongibles. Chaque marché binaire "X va-t-il arriver ?" crée deux positions :
- YES token (condition résolue à 1 si X arrive, 0 sinon)
- NO token (inverse)

La somme `YES + NO = 1 USDC` toujours, ce qui permet de mint/burn des paires complètes contre du collatéral. C'est le mécanisme qui garantit la cohérence des prix dans [0,1].

Contrat principal : `ConditionalTokens` sur Polygon à `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045`.

**2. CTFExchange — le contrat de Polymarket**

C'est le contrat qui gère le settlement des trades. Il ne fait PAS du matching — le matching se fait off-chain sur les serveurs de Polymarket. Le contrat vérifie les signatures EIP-712 des ordres, exécute les transferts de tokens CTF et d'USDC, et émet les events.

Adresse : `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` (NEG_RISK exchange, le principal depuis 2024).

Il existe aussi le "vanilla" CTF Exchange à `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` — attention, Polymarket a migré la plupart des marchés vers le **Neg Risk Adapter** qui permet des marchés multi-outcomes mutuellement exclusifs (élections à plusieurs candidats) tout en gardant la garantie "somme des prix = 1".

Adresse Neg Risk Adapter : `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296`.

**3. Order book off-chain**

Le CLOB (Central Limit Order Book) tourne sur l'infra Polymarket. Les ordres sont signés côté client (EIP-712), envoyés à l'API, matchés en mémoire, puis settlés on-chain par un operator privilégié. C'est ce qui permet d'avoir une UX proche d'un CEX (ordres limit, cancel gratuit, matching rapide) tout en gardant la custody non-custodiale des fonds.

Conséquence importante : **l'order book complet n'est PAS sur la chaîne**. Seuls les trades exécutés produisent des events on-chain. Pour avoir le carnet d'ordres, il faut passer par l'API CLOB.

**4. UMA Optimistic Oracle — résolution**

Quand un marché arrive à échéance, la question est posée à l'Optimistic Oracle d'UMA. Un proposer propose une réponse (YES/NO/50-50 pour invalide), bond un collatéral. Pendant une fenêtre de dispute (~2h généralement), n'importe qui peut disputer la réponse en bondant lui aussi. Si disputé, ça part en vote DVM (Data Verification Mechanism) des holders de UMA. Si non disputé, la réponse est validée et le `ConditionalTokens` peut `reportPayouts` qui permet aux holders de redeem leurs tokens YES/NO contre de l'USDC.

Contrat UMA Optimistic Oracle V2 sur Polygon : `0xeE3Afe347D5C74317041E2618C49534dAf887c24`.
Adapter UMA ↔ CTF côté Polymarket : `UmaCtfAdapter` à `0x6A9D222616C90FcA5754cd1333cFD9b7fb6a4F74` (v2) ou l'adapter Neg Risk à `0x2F5e3684cb1F318ec51b00Edba38d79Ac2c7c53C`.

### Events clés à indexer

Sur `CTFExchange` (les deux versions) :

```
OrderFilled(
  bytes32 indexed orderHash,
  address indexed maker,
  address indexed taker,
  uint256 makerAssetId,
  uint256 takerAssetId,
  uint256 makerAmountFilled,
  uint256 takerAmountFilled,
  uint256 fee
)

OrderCancelled(bytes32 indexed orderHash)

OrdersMatched(
  bytes32 indexed takerOrderHash,
  address indexed takerOrderMaker,
  uint256 makerAssetId,
  uint256 takerAssetId,
  uint256 makerAmountFilled,
  uint256 takerAmountFilled
)
```

Sur `ConditionalTokens` :

```
ConditionPreparation(bytes32 indexed conditionId, address indexed oracle, bytes32 indexed questionId, uint256 outcomeSlotCount)
ConditionResolution(bytes32 indexed conditionId, address indexed oracle, bytes32 indexed questionId, uint256 outcomeSlotCount, uint256[] payoutNumerators)
PositionSplit / PositionsMerge / PayoutRedemption
TransferSingle / TransferBatch (ERC-1155)
```

Pour reconstituer l'historique complet d'un marché, il faut croiser :
- Les events `OrderFilled` (trades)
- L'API CLOB (order book state, jamais on-chain)
- Les events CTF (minting/burning/redemption)
- L'API Gamma (metadata : question, catégorie, dates)

---

## 2. API officielle Polymarket

Polymarket expose **trois APIs** distinctes, chacune avec son domaine :

### API Gamma — `https://gamma-api.polymarket.com`

C'est l'API **metadata**. Pas d'auth nécessaire pour la lecture. C'est par là qu'on récupère la liste des marchés, leurs questions, leurs catégories, tags, dates de résolution, etc.

Endpoints principaux :

```
GET /markets              # Liste paginée des marchés
GET /markets/{id}         # Détail d'un marché
GET /events               # Événements (groupes de marchés liés)
GET /events/{id}          # Détail
GET /tags                 # Taxonomie
GET /series               # Séries récurrentes (ex: "Fed rate decision")
```

Exemple concret :

```bash
curl 'https://gamma-api.polymarket.com/markets?limit=10&active=true&order=volume24hr&ascending=false'
```

Paramètres utiles : `closed`, `active`, `archived`, `liquidity_min`, `volume_min`, `start_date_min`, `tag_id`, `order`, `ascending`, `limit`, `offset`.

**Rate limits** : pas officiellement documentés, mais empiriquement ça tient ~100 req/min sans souci. Au-delà, 429. Pas de clé API nécessaire pour le read.

**Ce qui est dans Gamma** : metadata riche, question text, description, outcomes, prix actuel, volume cumul, liquidité actuelle, resolution source, dates.

**Ce qui n'est PAS dans Gamma** : historique des prix, order book, trades individuels, positions utilisateurs.

### API CLOB — `https://clob.polymarket.com`

C'est l'API du **Central Limit Order Book**. Lecture du book : pas d'auth. Pour poster/annuler des ordres : auth obligatoire avec une clé API L1 (signature wallet EIP-712) + clé L2 (API key/secret générés).

Endpoints lecture :

```
GET /markets                      # Marchés tradables
GET /book?token_id=<erc1155_id>   # Order book complet pour un token
GET /price?token_id=...&side=buy  # Meilleur prix
GET /midpoint?token_id=...        # Midpoint
GET /spread?token_id=...
GET /prices-history?market=<condition_id>&interval=1m&fidelity=...
GET /trades?market=...            # Trades récents (public)
```

Endpoints authentifiés (trading) :

```
POST /order                       # Créer un ordre signé
DELETE /order/{id}
GET /data/orders                  # Ses ordres
GET /data/trades                  # Ses trades
GET /data/positions
```

**Auth flow** : on signe un message EIP-712 avec son wallet pour dériver une API key (via `py-clob-client` ou `@polymarket/clob-client`). Ensuite chaque requête est signée HMAC avec le secret dérivé.

```python
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

host = "https://clob.polymarket.com"
key = "0x..."  # clé privée du wallet
chain_id = POLYGON
client = ClobClient(host, key=key, chain_id=chain_id)

# Génération des credentials API (une fois)
api_creds = client.create_or_derive_api_creds()
client.set_api_creds(api_creds)

# Usage
book = client.get_order_book(token_id="71321045679252212594626385...")
print(book.bids, book.asks)
```

**Rate limits CLOB** : documenté à ~100 req/10s en lecture, plus restrictif en écriture (ordres). Burst acceptés mais ban temporaire si abus.

**Prices history** : endpoint très utile, retourne les prix OHLC en time series. `interval` ∈ {1m, 1h, 6h, 1d, 1w, max}, `fidelity` contrôle la densité des points.

### API "Data" — `https://data-api.polymarket.com`

Plus récente, expose des endpoints analytiques :

```
GET /holders?market=<condition_id>       # Top holders par position
GET /positions?user=<address>            # Positions d'un wallet
GET /trades?user=<address>               # Trades d'un wallet
GET /value?user=<address>                # PnL / valeur portefeuille
GET /activity                            # Activity feed global
```

Pas d'auth requise pour la plupart, rate limits similaires à Gamma.

### Récap de ce qui demande quoi

| Besoin | API | Auth |
|---|---|---|
| Liste marchés, metadata | Gamma | Non |
| Prix actuels | CLOB ou Gamma | Non |
| Historique prix (chart) | CLOB `/prices-history` | Non |
| Order book L2 | CLOB `/book` | Non |
| Trades publics | CLOB `/trades` | Non |
| Positions d'un wallet | Data API ou on-chain | Non |
| Placer/annuler des ordres | CLOB | **Oui** (L1+L2) |
| Voir ses propres ordres | CLOB `/data/orders` | Oui |

---

## 3. Subgraph Goldsky / The Graph

Polymarket a historiquement eu un subgraph sur le réseau hébergé de The Graph, puis migré vers **Goldsky** quand le hosted service de The Graph a été décommissionné en 2024.

**Subgraphs Polymarket sur Goldsky** (publics, gratuits en lecture modérée) :

- `polymarket-matic/activity-polygon/prod` — trades, orders, user activity
- `polymarket-matic/orderbook-subgraph/prod` — orders filled/cancelled
- `polymarket-matic/positions-subgraph/prod` — positions CTF, splits, merges, redemptions
- `polymarket-matic/pnl-subgraph/prod` — PnL calculé

Les endpoints ont la forme :

```
https://api.goldsky.com/api/public/project_<id>/subgraphs/<name>/<version>/gn
```

Le project ID public de Polymarket est visible dans leur doc / dans les repos open source (cherche "goldsky.com" dans leur GitHub).

**Entités indexées typiques** :

```graphql
type FilledOrder @entity {
  id: ID!                         # txHash + logIndex
  transactionHash: Bytes!
  timestamp: BigInt!
  maker: Bytes!
  taker: Bytes!
  makerAssetId: BigInt!
  takerAssetId: BigInt!
  makerAmountFilled: BigInt!
  takerAmountFilled: BigInt!
  fee: BigInt!
  market: Market
}

type Market @entity {
  id: ID!                         # conditionId
  questionId: Bytes!
  outcomeSlotCount: Int!
  resolved: Boolean!
  payouts: [BigInt!]
  oracle: Bytes!
  filledOrders: [FilledOrder!] @derivedFrom(field: "market")
}

type Position @entity {
  id: ID!                         # user-tokenId
  user: Bytes!
  tokenId: BigInt!
  balance: BigInt!
  conditionId: Bytes!
  outcomeIndex: Int!
}
```

**Exemple de requête** — les 10 plus gros trades des dernières 24h sur un marché donné :

```graphql
query TopTrades($conditionId: Bytes!, $since: BigInt!) {
  filledOrders(
    where: { market: $conditionId, timestamp_gte: $since }
    orderBy: makerAmountFilled
    orderDirection: desc
    first: 10
  ) {
    id
    timestamp
    maker
    taker
    makerAmountFilled
    takerAmountFilled
    transactionHash
  }
}
```

**Coût** : Goldsky expose des endpoints publics gratuits en lecture, avec rate limit raisonnable (~50 req/s). Pour des besoins sérieux (indexer en continu, pas de rate limit, subgraphs custom), Goldsky propose des plans payants à partir de **~50 $/mois** (Starter) et ~500 $/mois (Growth). Le réseau décentralisé de The Graph fonctionne en pay-per-query avec GRT, mais aucun des subgraphs Polymarket officiels n'y est publié à ma connaissance — c'est full Goldsky.

---

## 4. Dune Analytics

Dune est probablement **le moyen le plus ROI-positif** d'explorer la data Polymarket sans rien builder.

### Tables disponibles

Dune a des tables décodées automatiquement pour Polygon. Les principales pour Polymarket :

- `polymarket_polygon.ctfexchange_evt_orderfilled` — trades
- `polymarket_polygon.ctfexchange_evt_ordercancelled`
- `polymarket_polygon.ctfexchange_evt_ordersmatched`
- `polymarket_polygon.negriskctfexchange_evt_*` — même chose pour le neg risk
- `gnosis_polygon.conditionaltokens_evt_conditionresolution`
- `gnosis_polygon.conditionaltokens_evt_payoutredemption`
- `gnosis_polygon.conditionaltokens_evt_transfersingle` / `transferbatch`

Il existe aussi des tables curées par la communauté, notamment de `@rchen8` et `@polymarketanalytics` :

- `dune.polymarketanalytics.result_*` — datasets enrichis avec metadata des marchés
- `query_xxxxxx` matérialisées en views publiques

Pour retrouver metadata des marchés (question text, catégorie), il faut soit joindre avec une table custom (upload CSV depuis Gamma), soit utiliser les tables communautaires qui ont déjà fait le travail.

### Qualité et fraîcheur

- **Fraîcheur** : latence de ~5-15 minutes après la finalité Polygon. Correct pour de l'analyse, pas pour du trading temps réel.
- **Qualité** : très fiable sur les events on-chain. **Ne contient PAS les ordres non-exécutés** (qui n'existent pas on-chain).
- **Trous historiques** : attention à la migration USDC.e → USDC native (août 2023) et à l'arrivée du Neg Risk Exchange (2024). Certaines tables ne couvrent que l'un ou l'autre.

### Pricing

- **Free** : 2500 credits/mois, queries privées limitées, exports CSV limités, Dune API inaccessible. Suffisant pour explorer.
- **Plus (~49 $/mois)** : 25k credits, queries privées illimitées, API access basique.
- **Analyst (~349 $/mois)** : 250k credits, API généreuse, materialized views.

Pour du batch d'analyses quotidien, le plan Plus suffit largement. Pour du pipeline en prod qui pull via API, viser Analyst.

### Dashboards de référence

Quelques dashboards Polymarket notables à aller voir avant de réinventer la roue :

- `dune.com/rchen8/polymarket` (Richard Chen — un des plus suivis)
- `dune.com/polymarketanalytics/*` (équipe communautaire)
- `dune.com/21co/polymarket` (21.co)

Chercher "polymarket" dans la recherche Dune remonte ~50+ dashboards, beaucoup sont forkables.

### Exemple de query

Volume quotidien par marché sur les 30 derniers jours :

```sql
SELECT 
    date_trunc('day', evt_block_time) AS day,
    makerAssetId AS token_id,
    SUM(CAST(makerAmountFilled AS DECIMAL) + CAST(takerAmountFilled AS DECIMAL)) / 1e6 / 2 AS volume_usdc
FROM polymarket_polygon.ctfexchange_evt_orderfilled
WHERE evt_block_time >= NOW() - INTERVAL '30' DAY
GROUP BY 1, 2
ORDER BY day DESC, volume_usdc DESC
```

(Le `/2` parce que le volume est compté côté maker ET taker, on divise pour ne pas double-compter. Les amounts sont en 6 décimales pour l'USDC et équivalent pour les tokens CTF prix × quantité.)

---

## 5. Alternatives data providers

### Allium

Data warehouse enterprise orienté crypto. Couverture Polygon complète, tables décodées Polymarket disponibles. Pricing **pas public, sur devis**, typiquement **à partir de 1-2k $/mois** pour un plan sérieux. Overkill pour un projet solo, pertinent si tu bosses en équipe / fonds. Qualité data excellente, SLA sérieux, support actif.

### Flipside Crypto

Équivalent-concurrent de Dune, SQL-first. Tables Polygon décodées, Polymarket couvert. **Free tier généreux** : accès à l'essentiel en SQL, API limitée mais utilisable. Plans payants à partir de ~50 $/mois pour plus de quotas. Qualité data correcte mais moins de dashboards communautaires Polymarket vs Dune — tu seras souvent le premier à construire.

### Footprint Analytics

Plus orienté dashboards no-code et visualisation. Couverture Polymarket existe mais moins profonde que Dune/Flipside. Free tier utilisable, plans payants ~40-300 $/mois. Pas le meilleur choix pour des besoins techniques avancés.

### The Graph (réseau décentralisé)

Les subgraphs Polymarket ne sont pas (encore) publiés dessus, ils sont sur Goldsky. Si tu veux consommer via The Graph décentralisé, il faudrait soit déployer ton propre subgraph soit attendre une migration. Pricing : pay-per-query en GRT, très bon marché à petite échelle (~0.0001 $/query). Non-applicable en pratique pour Polymarket aujourd'hui.

### Covalent / GoldRush

Unified API REST pour blockchain data, couvre Polygon. Endpoints pour transactions, tokens, events décodés. **Free tier 100k credits** (suffit pour tester), plans à partir de ~50 $/mois. Pas de couverture Polymarket "native" — tu dois décoder les events toi-même en pointant vers les adresses des contrats. Utile comme couche d'abstraction si tu ne veux pas gérer un RPC direct.

### Bitquery

API GraphQL sur data blockchain multi-chaînes. Couverture Polygon solide, queries sur events et transactions. Plus ~49 $/mois, Enterprise sur devis. Bonne alternative à Covalent, interface GraphQL plus agréable pour certains usages. Pas de tables Polymarket spécifiques — même logique que Covalent, tu pointes sur les contrats.

### Récap comparatif

| Provider | Couverture PM | Pricing | Qualité | Pour quoi |
|---|---|---|---|---|
| **Dune** | Excellente (tables décodées + communauté) | Free / 49 $ / 349 $ | Très bonne | SQL analytique, dashboards |
| **Flipside** | Bonne | Free / ~50 $+ | Bonne | Alternative SQL à Dune |
| **Goldsky** | Native (subgraphs officiels) | Free read / 50 $+ | Excellente | GraphQL, temps quasi-réel |
| **Allium** | Excellente | ~1k+ $ | Excellente | Équipes / fonds |
| **Footprint** | Moyenne | Free / 40-300 $ | Correcte | Dashboards no-code |
| **Covalent** | Indirecte | Free / 50 $+ | Bonne | REST abstraction |
| **Bitquery** | Indirecte | 49 $+ | Bonne | GraphQL multi-chain |

---

## 6. Self-hosted et RPC Polygon

### Options RPC managés (simples)

**Alchemy**
- Free tier : 300M compute units/mois (~10-20M requêtes RPC simples). Suffit pour indexer Polymarket à petite échelle si tu es efficace.
- Growth : 49 $/mois, 1.5B CU.
- Scale : 289 $/mois, illimité pratique.
- Qualité : archive node inclus gratuit, excellente couverture Polygon, WebSockets stables.

**QuickNode**
- Pas de vrai free tier (trial limité 7j).
- Discover : 10 $/mois, ~80M requests/mois, un seul endpoint.
- Build : 49 $/mois, 200M requests, archive data.
- Accelerate : 299 $/mois.
- Qualité : très bonne, mais pricing moins généreux qu'Alchemy côté free.

**Infura (ConsenSys)**
- Free : 3M requests/jour. Pas d'archive sur Polygon en free.
- Developer : 50 $/mois, 6M/jour, archive inclus.
- Team : 225 $/mois.
- Qualité : fiable mais Polygon est moins priorisé que Ethereum chez eux.

**Ankr**
- Free tier : endpoint public rate-limité (30 req/s environ). OK pour dev, pas pour prod.
- Premium : pay-as-you-go, ~10 $ de base, très compétitif. Archive disponible.
- Qualité : correct mais plus variable que Alchemy/QuickNode.

**Chainstack, BlockPI, Tatum** : alternatives budget, ~10-30 $/mois pour des niveaux d'usage modérés.

### Self-hosted full node Polygon

Running un node Polygon soi-même :

- **Bor (execution) + Heimdall (consensus)** : les deux clients officiels.
- **Erigon** : alternative plus efficace pour archive node, très utilisé en prod.
- **Full snapshot sync** : ~2-3 To de disque pour archive node (décembre 2025 estimé, ça ne fait que grossir).
- **Full node (pruned)** : ~500 Go-1 To.

Coût infra réaliste :
- Bare metal dédié (Hetzner AX101 ou équivalent) : ~90-150 €/mois pour 2 To NVMe, 64 Go RAM. **C'est le sweet spot coût/perf pour un archive node.**
- AWS/GCP : **hors de prix pour de l'archive**, compter 500-1500 $/mois facile à cause du stockage I/O.
- Ops overhead : non-négligeable. Sync initial 1-2 semaines, maintenance régulière, monitoring.

**Verdict self-hosted** : vaut le coup uniquement si tu fais du gros volume RPC (>1B requests/mois) ou si tu as des besoins spécifiques (traces custom, indexing proprio). Sinon Alchemy Growth à 49 $ bat tout en ratio coût/tranquillité.

### Ordres de grandeur par niveau d'usage

| Usage | Solution recommandée | Coût |
|---|---|---|
| Dev / exploration | Alchemy free | 0 € |
| Indexer 1-2 marchés en live | Alchemy free + Goldsky free | 0 € |
| App analytics solo, 100-1000 users | Alchemy Growth + Dune Plus | ~100 €/mois |
| App en prod, trading | Alchemy Scale + Dune Analyst + backup provider | ~700 €/mois |
| Hedge fund, full archive | Self-hosted Erigon + Allium | 2-5k €/mois |

---

## 7. Données off-chain : où elles vivent

Ce qu'il faut savoir, c'est que **une bonne partie de la data "intéressante" de Polymarket n'est pas on-chain**.

### Historique des prix (chart OHLC)

- **Source primaire** : API CLOB `/prices-history`. Polymarket le sert gratuitement.
- **Alternative** : reconstruire à partir des `OrderFilled` events on-chain. Ça donne les trades executés mais pas le midpoint / meilleur bid ask à un instant t.
- **Bulk export** : pas d'endpoint officiel pour dump l'historique complet d'un coup. Il faut paginer sur `/prices-history` par marché et par période. Empiriquement ~60 marchés/min sans se faire rate-limiter.

### Order book history (carnet d'ordres dans le temps)

- **Jamais on-chain**. L'order book vit sur les serveurs Polymarket et n'est pas historisé publiquement.
- **Snapshots temps réel** : API CLOB `/book` — donne l'état instantané.
- **Historique** : si tu en veux, il faut **le construire toi-même** en snapshotant le book à intervalle régulier. C'est une dépendance importante pour de la microstructure analysis.
- Personne ne revend cette data publiquement à ma connaissance (ni Kaiko, ni Amberdata) — tu es ton propre data provider.

### Volumes et liquidité

- Volume cumul et 24h dans Gamma API (calculé par Polymarket).
- Volume granulaire reconstituable depuis les events on-chain via Dune ou Goldsky.
- TVL / liquidité : dispo dans Gamma, aussi calculable en sommant les positions LP (mais attention, Polymarket fait du market making hybride, une partie de la liquidité vient de leur propre market maker).

### Metadata des marchés

- Questions, descriptions, catégories, tags, resolution sources, dates : **tout dans Gamma API**.
- Exportable en bulk en paginant `/markets?limit=500&offset=...`. Aucune limite dure, juste la politesse rate limit.
- Attention : les questions peuvent être éditées après création (rare mais arrive). Garder un timestamp de scraping.

### Résolutions et disputes UMA

- Events UMA sur Polygon à indexer (voir section 1 pour adresses).
- UMA expose aussi un GraphQL public : `https://api.thegraph.com/subgraphs/name/umaprotocol/polygon-optimistic-oracle-v2` (ou équivalent Goldsky si migré).
- Pour les disputes : ça devient vite fastidieux, UMA a un historique complexe.

---

## 8. Setup recommandés par budget

### Budget zéro (0 €/mois)

**Stack** :
- **Gamma API** (direct, non authentifié) pour metadata marchés
- **CLOB API** (direct, non authentifié) pour order book et prix history
- **Goldsky subgraphs publics** pour queries GraphQL historiques
- **Dune free tier** (2500 credits) pour SQL ad-hoc
- **Alchemy free** pour RPC si besoin de lire on-chain direct
- Stockage local : SQLite ou DuckDB sur un Parquet

**Limitations** :
- Rate limits sur tout
- Pas de pipeline continu sérieux (Dune API inaccessible en free)
- Snapshots d'order book manuels, pas de scheduler
- 429 fréquents si tu multi-threades mal

**Analyses possibles** :
- Exploration, prototypage, notebooks
- Analyses historiques one-shot
- Dashboards statiques mis à jour à la main
- Backtests sur data téléchargée une fois

**Recommandé pour** : découverte, POC, recherche académique solo.

### Budget frugal (20-50 €/mois)

**Stack** :
- **Dune Plus** (49 $/mois) — l'investissement le plus rentable. Queries privées illimitées, API basique, exports CSV.
- **Alchemy free** pour complément RPC
- **Goldsky free** pour GraphQL temps quasi-réel
- **VPS petit** (Hetzner CX22, ~5 €/mois) pour un cron qui snapshot l'order book et stocke en Parquet

**Limitations** :
- Toujours dépendant des rate limits API Polymarket
- Dune Plus limite à 25k credits, attention aux queries lourdes
- Pas d'archive node maison

**Analyses possibles** :
- Tout le SQL analytique sérieux sur trades/positions
- Pipeline de scraping order book custom (data qui n'existe nulle part ailleurs, valeur réelle)
- Dashboards auto-refresh
- Monitoring custom (alertes prix, liquidité)

**Recommandé pour** : dev solo construisant un produit, trader qui veut de l'analytics custom.

### Budget confort (100-300 €/mois)

**Stack** :
- **Dune Analyst** (349 $/mois — ou Plus à 49 $ si tu peux t'en sortir) — API sérieuse, materialized views
- **Alchemy Growth** (49 $/mois) — RPC confortable avec archive
- **Goldsky** plan Starter (~50 $/mois) si subgraph custom ou besoin de zéro rate limit
- **VPS robuste** (Hetzner AX41 dédié, ~40 €/mois) pour les jobs d'indexing custom
- Optionnel : **QuickNode ou backup RPC** pour failover

**Limitations** :
- Coût qui monte vite si on empile. Arbitrer : si tu fais beaucoup de SQL, Dune Analyst ; si tu fais beaucoup d'indexing custom temps réel, Goldsky payant ; rarement les deux.
- Toujours pas d'archive node Polygon maison (~150 €/mois de plus).

**Analyses possibles** :
- Quasi tout : pipelines prod, trading semi-auto, analytics avancées
- Dashboards publics, API dérivée pour d'autres users
- Backtests haute fréquence, ML sur features complexes

**Recommandé pour** : équipe de 2-5 personnes, produit lancé, fonds small-cap.

---

## 9. Gotchas techniques

### Finalité Polygon et reorgs

Polygon PoS a une finalité probabiliste, pas déterministe immédiate. **Checkpoints Heimdall vers Ethereum ~toutes les 30 min** — c'est là que tu as la "vraie" finalité. Avant ça, des reorgs sont techniquement possibles.

- **En pratique** : reorgs profonds (>10 blocs) sont rares mais pas inexistants (il y en a eu plusieurs en 2023-2024).
- **Pour indexer** : attendre au moins 64 blocs (~2 min) avant de considérer un event comme définitif pour de l'analytics. Pour du trading actif, attendre le checkpoint (~30 min) est plus safe.
- **Dune, Goldsky, Alchemy** gèrent ça pour toi — ils rejouent les reorgs. Mais si tu indexes toi-même, il faut écouter les reorgs (via WebSocket `newHeads` avec vérification) ou accepter une fenêtre de lag.

### USDC.e vs USDC natif

- **Avant août 2023** : Polymarket utilisait USDC.e (bridged from Ethereum, adresse `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`).
- **Depuis** : migration progressive vers USDC natif Polygon (Circle CCTP, adresse `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359`).
- **Conséquence** : beaucoup de queries qui agrègent "volume USDC Polymarket" ratent la moitié de l'histoire si elles ne prennent qu'une des deux adresses. Vérifier toujours.

### Prix UI vs prix on-chain

L'UI Polymarket affiche le **midpoint** du carnet (best bid + best ask) / 2, arrondi au cent. Les trades s'exécutent au prix du book, qui peut différer du midpoint de quelques bps à quelques pourcents selon la liquidité. Pour du backtest, utiliser les prix de trades réels (events `OrderFilled`) pas les midpoints. Pour un "prix affiché", reconstruire le midpoint depuis le book snapshot.

### Neg Risk vs Vanilla CTF Exchange

Deux exchanges coexistent :
- Vanilla CTFExchange : marchés binaires indépendants
- NegRiskCTFExchange : marchés multi-outcomes avec contrainte "somme = 1" (élections, etc.)

Les **token IDs diffèrent** entre les deux (mêmes semantics YES/NO mais IDs ERC-1155 différents). Si tu indexes, il faut couvrir les deux séparément et savoir à quelle famille appartient un marché. Gamma API indique ça via `negRisk: true/false` dans la réponse market.

### Problèmes historiques d'indexation

- **Migration Hosted Service → Goldsky** (2024) : certains subgraphs ont eu des trous. Vérifier la continuité sur la période T4 2023 / T1 2024.
- **Changement de schéma v1 → v2 des contrats** : les premiers marchés Polymarket (2020-2021) utilisaient un contrat différent (matic-markets). Pas couverts par les subgraphs actuels. Pour de l'histoire ancienne, soit on accepte la perte, soit on indexe soi-même les vieux contrats.
- **Delta entre trade `OrderFilled` et réception ERC-1155** : parfois sur la même tx mais pas toujours le même log index, attention aux joins.

### Rate limiting des APIs Polymarket

Pas de doc officielle publiée, mais empiriquement :
- Gamma : ~100 req/min tient. Au-delà : 429 progressifs.
- CLOB lecture : ~100 req/10s, burst acceptés.
- CLOB écriture (ordres) : beaucoup plus strict, dépend du wallet.
- Data API : similaire à Gamma.

Toujours mettre du backoff exponentiel + rotation d'IP si besoin de scrape fort. Pas de "clé API" payante qui augmenterait les limits côté Polymarket — ils n'offrent pas ce service commercial.

### Fees

- Fees de trading Polymarket : **actuellement 0% frontend** pour la plupart des marchés, mais le contrat supporte des fees non-nuls côté maker et taker. Toujours lire le champ `fee` dans `OrderFilled` au cas où.
- Gas Polygon : négligeable (~0.01 $ par trade), mais à budget si tu settles beaucoup d'ordres en tant que market maker.

### Positions "dormant" après résolution

Après résolution d'un marché, les holders doivent **manuellement appeler `redeemPositions`** pour récupérer leur USDC. Beaucoup oublient. Conséquence : les balances CTF "brutes" ne reflètent pas la valeur réelle du portefeuille si tu ne checkes pas le statut résolu. Toujours joindre avec `ConditionResolution` events + flag "redeemed" dans tes queries.

---

## Ressources utiles

- Docs officielles : `docs.polymarket.com`
- GitHub Polymarket : `github.com/Polymarket` — clients SDK, contrats, exemples
- `py-clob-client` : SDK Python officiel
- `@polymarket/clob-client` : SDK TypeScript officiel
- Goldsky docs : `docs.goldsky.com`
- UMA docs Optimistic Oracle : `docs.uma.xyz`
- Dune tables : chercher `polymarket_polygon` dans le schema browser

Pour une stack qui démarre sérieusement demain matin, je suggérerais : **Dune Plus + Alchemy free + Goldsky free + un petit VPS pour snapshot l'order book**. Ça coûte ~50 €/mois, couvre 90% des use cases d'analyse, et laisse la porte ouverte au scale-up quand tu sais précisément ce qui te manque.
