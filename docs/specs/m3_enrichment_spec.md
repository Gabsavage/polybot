# M3 Enrichment Layer — Spec technique

## Objectif

Construire la couche d'enrichissement critique pour que les composants
de scoring (C1, C2, C3) produisent des metriques per-user correctes et
exploitent les resolutions de marche.

M3 livre 4 composants independants :
1. `indexer_proxy_factory` — mapping proxy->EOA (moat technique critique)
2. `indexer_resolutions_uma` — suivi des resolutions/disputes UMA
3. `indexer_onchain_goldsky` — activite on-chain large (enrichissement)
4. Job `populate_volume_1h` — remplissage de la colonne `volume_1h`
   des snapshots CLOB (ADR-006)

## Milestone

M3 — Enrichissement minimal

## Dependances

- M1 : VPS, DuckDB schema, R2 storage, systemd timers
- M2 : `markets`, `trades`, `tracked_wallets` (populees)

---

## 1. `indexer_proxy_factory`

### Objectif

Mapper chaque proxy wallet Polymarket vers son EOA proprietaire, pour
consolider les metriques per-user et eviter les phantom wallets (ADR-011).

### Source de donnees

**Events on-chain Polygon** via Alchemy RPC :

1. **Gnosis Safe Proxy Factory** (generique, utilise par plein de dApps) :
   - Contract : `0xa6b71e26c5e0845f74c812102ca7114b6a896ab2`
   - Event : `ProxyCreation(address proxy, address singleton)`

2. **Polymarket Proxy Factory** (custom) :
   - Contract : a confirmer via Gamma API ou docs Polymarket
   - Event : similaire, `ProxyCreated(address proxy, address owner)`

**Methode** : `eth_getLogs` via Alchemy, filtrage par topic de l'event,
batch de 2000 blocks par call.

### Frequence

- **Backfill initial** : scan depuis le deployment (fin 2020) jusqu'a
  maintenant. ~100K+ proxies attendus. Estimation : ~5-10M de blocks a
  scanner sur Polygon. Avec batch de 2000 blocks, c'est ~3000 calls RPC.
  Alchemy free tier : 300M CU/mois, chaque eth_getLogs = ~500 CU, total
  ~1.5M CU = 0.5% du quota. Safe.
- **Incremental** : toutes les heures, scan uniquement les nouveaux blocks
  depuis le dernier run. ~1800 blocks/heure sur Polygon.

### Logique de mapping

Pour chaque `ProxyCreation` event :

1. Capturer `proxy_address` (l'output du factory) et `creator_eoa` (le
   caller de la transaction, visible via `getTransaction`)
2. Enregistrer dans `proxy_eoa_map` :
```sql
INSERT INTO proxy_eoa_map (proxy_address, eoa_address, confidence,
    method, first_seen_block, first_seen_ts, factory_contract)
VALUES (...)
ON CONFLICT (proxy_address) DO NOTHING;
```

3. **Confidence score** :
   - `1.0` : mapping direct via `ProxyCreation` event (methode canonique)
   - `0.8` : mapping via premiere tx du proxy (fallback si ProxyCreation
     manque, ex fork historique)
   - `0.5` : mapping via heuristique (shared deposit address, etc.) —
     reporte en M7

### Schema DB

Table `proxy_eoa_map` (migration M3) :
```sql
CREATE TABLE proxy_eoa_map (
    proxy_address VARCHAR PRIMARY KEY,
    eoa_address VARCHAR NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    method VARCHAR CHECK (method IN ('direct_factory', 'first_tx', 'heuristic', 'manual')),
    first_seen_block BIGINT,
    first_seen_ts TIMESTAMP,
    factory_contract VARCHAR,
    ingested_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_proxy_eoa ON proxy_eoa_map (eoa_address);
```

### Criteres de succes M3

- `COUNT(proxy_eoa_map) >= 100 000` apres backfill
- Test unitaire : pour les 15 wallets Tier A, chercher leur EOA dans
  `proxy_eoa_map` — au moins 13/15 doivent matcher (certains proxies
  plus anciens peuvent avoir ete crees hors factories, acceptable)
- Pas de doublon `proxy_address` (PK garantit)

### Edge cases

- **Proxies de proxies** : certains wallets creent un proxy qui lui-meme
  cree un proxy. Pour v1 on garde uniquement le mapping direct, on ne
  suit pas la chaine complete. A revisiter en M7.
- **Multisigs Gnosis** : proxy avec multiple owners. On capture
  uniquement le createur (caller de la tx), les autres owners ne sont
  pas dans notre mapping. Acceptable pour v1 car rare sur Polymarket.
- **Proxies crees hors factories** : certains wallets anciens (2020-2021)
  peuvent avoir ete crees via un mecanisme custom. Plan B : heuristique
  "first USDC deposit from EOA" en M7.

### Configuration

```python
class ProxyFactoryIndexerSettings(BaseSettings):
    gnosis_safe_factory: str = "0xa6b71e26c5e0845f74c812102ca7114b6a896ab2"
    polymarket_proxy_factory: str = "<a confirmer>"
    batch_size_blocks: int = 2000
    poll_interval_seconds: int = 3600  # 1 heure
    backfill_start_block: int = 11000000  # ~debut 2020 Polygon
```

---

## 2. `indexer_resolutions_uma`

### Objectif

Suivre les resolutions de marches Polymarket via UMA Optimistic Oracle,
detecter les disputes, et trigger la resolution des alertes passees
quand un marche se settle.

### Source de donnees

**Events on-chain** via Alchemy RPC, contrats UMA :
- Optimistic Oracle V2 : `0xeE3Afe347D5C74317041E2618C49534dAf887c24`
- UmaCtfAdapter v2 : `0x6A9D222616C90FcA5754cd1333cFD9b7fb6a4F74`
- Neg Risk adapter : `0x2F5e3684cb1F318ec51b00Edba38d79Ac2c7c53C`

**Events a capturer** :
- `ProposePrice(bytes32 identifier, uint256 timestamp, bytes ancillaryData, int256 proposedPrice, address proposer)`
- `DisputePrice(bytes32 identifier, uint256 timestamp, bytes ancillaryData, address disputer)`
- `Settle(bytes32 identifier, uint256 timestamp, bytes ancillaryData, int256 price, bool disputed)`

### Frequence

Polling toutes les heures via `eth_getLogs`, scan des nouveaux blocks
depuis le dernier run.

### Logique

Pour chaque event :
1. Parser `ancillaryData` pour extraire le `question_id` Polymarket
   (format : `questionID:0x<hex>, ...`)
2. Joindre avec `markets` via le `question_id` pour retrouver le
   `condition_id`
3. Upsert dans `resolutions` :

```sql
CREATE TABLE resolutions (
    condition_id VARCHAR PRIMARY KEY,
    question_id VARCHAR,
    proposed_at TIMESTAMP,
    proposed_price DECIMAL(18,6),  -- 1e18 = YES, 0 = NO, 5e17 = 50-50
    proposer VARCHAR,
    disputed BOOLEAN DEFAULT FALSE,
    dispute_count INTEGER DEFAULT 0,
    settled_at TIMESTAMP,
    final_price DECIMAL(18,6),
    settled_outcome VARCHAR  -- 'YES', 'NO', 'INVALID'
);
```

4. Si `Settle` event recu :
   - Trigger `resolve_alerts(condition_id)` job (en M6 via `log_alert_outcomes`)
   - Marquer `outcome_known = TRUE` dans `alerts` pour ce market
   - Calculer `was_direction_correct` pour chaque alerte affectee

### Criteres de succes M3

- `COUNT(resolutions) >= 100` apres 48h (Polymarket resout ~50-100
  marches par jour)
- Test : 1 marche resolu recemment doit avoir son entree avec
  `settled_outcome` correct
- Pas de doublon `condition_id` (PK)

### Edge cases

- **Disputes multiples** : un marche peut etre dispute, re-propose,
  re-dispute. On incremente `dispute_count`, on garde le dernier
  `proposed_price`, on ne finalise qu'au dernier `Settle`.
- **Neg Risk vs Vanilla** : les 2 adapters envoient leurs events sur
  le meme Optimistic Oracle. On capture via le `identifier` (keccak de
  l'event Polymarket) sans se soucier de quel adapter.
- **Markets INVALID** : `proposedPrice == 5e17` (0.5e18) signifie
  "invalid question". Payout YES = 0.5, NO = 0.5. Logger specifiquement.

### Configuration

```python
class ResolutionsIndexerSettings(BaseSettings):
    oracle_contract: str = "0xeE3Afe347D5C74317041E2618C49534dAf887c24"
    uma_adapter_v2: str = "0x6A9D222616C90FcA5754cd1333cFD9b7fb6a4F74"
    neg_risk_adapter: str = "0x2F5e3684cb1F318ec51b00Edba38d79Ac2c7c53C"
    poll_interval_seconds: int = 3600
```

---

## 3. `indexer_onchain_goldsky`

### Objectif

Enrichir `trades_all` avec l'activite on-chain large (pas limite aux
wallets Tier A). Utilise pour re-scoring periodique et detection de
nouveaux profils interessants (M7).

### Source de donnees

**Subgraph Goldsky Polymarket** :
`https://api.goldsky.com/api/public/project_...polymarket-matic-activity-polygon-prod/subgraph`

Query GraphQL paginee pour les entites `FilledOrder` et `Position` sur
la derniere heure glissante.

### Frequence

Toutes les heures (vs 60s pour `indexer_trades_dataapi` qui est temps
reel). Goldsky free tier : ~50 req/s, pas de souci sur frequence horaire.

### Logique

1. Query Goldsky : `FilledOrder(where: {timestamp_gte: now - 1h})`,
   pagination par 100
2. Mapping des champs Goldsky vers notre schema `trades_all`
3. Insert avec dedup (reuse la logique M2 via `transactionHash`)

### Schema DB

Table `trades_all` (migration M3) — similaire a `trades` mais moins
fraiche et plus large :
```sql
CREATE TABLE trades_all (
    transaction_hash VARCHAR PRIMARY KEY,
    proxy_wallet VARCHAR,
    eoa_address VARCHAR,  -- enrichi via proxy_eoa_map
    condition_id VARCHAR,
    side VARCHAR,
    size_usd DECIMAL(18,2),
    price DECIMAL(6,4),
    timestamp_ts TIMESTAMP,
    source VARCHAR DEFAULT 'goldsky',  -- 'goldsky' ou 'dataapi'
    ingested_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trades_all_wallet_time ON trades_all (proxy_wallet, timestamp_ts DESC);
CREATE INDEX idx_trades_all_market_time ON trades_all (condition_id, timestamp_ts DESC);
```

### Fallback

Si Goldsky down > 1h, fallback sur Dune (job `dune_sync` standalone,
pull via SQL Dune) pour combler le trou.

### Criteres de succes M3

- Apres 24h : `COUNT(trades_all) WHERE source='goldsky' >= 10000`
- Test end-to-end : un wallet Tier A doit avoir ses trades a la fois
  dans `trades` (temps reel) et `trades_all` (horaire). Joinable via
  `transaction_hash`.

### Edge cases

- **Trade duplique** : si Goldsky rattrape un trade deja capture via
  Data API, on detecte via `transaction_hash` PK. Laisse le premier
  arrive (probablement Data API).
- **Trous historiques Goldsky** : mentionne dans le plan technique,
  subgraph peut avoir des gaps T4 2023 / T1 2024. Documenter dans
  ADR si rencontre, fallback Dune sync one-shot.

### Configuration

```python
class GoldskyIndexerSettings(BaseSettings):
    subgraph_url: str = "https://api.goldsky.com/..."
    poll_interval_seconds: int = 3600
    lookback_window_seconds: int = 3900  # 65 min pour eviter les
                                         # misses en bord de fenetre
    batch_size: int = 100
```

---

## 4. Job `populate_volume_1h`

### Objectif

Remplir la colonne `volume_1h` des snapshots CLOB (Parquet R2),
actuellement NULL depuis M1 (ADR-006).

### Source de donnees

Agregation des trades dans `trades_all` (populee par `indexer_onchain_goldsky`) :

```sql
SELECT
    condition_id,
    asset_id,
    SUM(size_usd) AS volume_1h
FROM trades_all
WHERE timestamp_ts >= snapshot_ts - INTERVAL 1 HOUR
  AND timestamp_ts < snapshot_ts
GROUP BY condition_id, asset_id;
```

### Frequence

Toutes les heures, en post-processing des snapshots CLOB de la derniere heure.

### Logique

1. Lister les fichiers Parquet R2 du dernier jour sans `volume_1h`
   peuple (ou tous si first run)
2. Pour chaque fichier `snapshots/YYYY-MM-DD/HH.parquet` :
   a. Telecharger le Parquet depuis R2
   b. Query DuckDB pour recuperer les volumes agreges sur la fenetre
      [HH-1h, HH]
   c. Join avec le DataFrame du Parquet (par `condition_id` + `asset_id`)
   d. Update la colonne `volume_1h`
   e. Re-upload le Parquet sur R2

### Criteres de succes M3

- Apres 24h : sur un echantillon de 10 Parquet R2, `volume_1h` non-null
  pour > 80% des rows (certains marches peu liquides peuvent avoir 0
  trade dans l'heure = null acceptable)
- Script `validate_snapshot.py` retourne OK avec `volume_1h` peuple

### Edge cases

- **Marche resolu durant la fenetre** : certains trades juste avant la
  resolution peuvent etre absents de `trades_all` (Goldsky lag).
  Acceptable, on ne re-process pas retroactivement.
- **Markets tres liquides** : agregation de milliers de trades, performance
  check a faire. Indexing DuckDB sur `(condition_id, asset_id, timestamp_ts)`
  doit gerer.

---

## Ordonnancement systemd

Ajouter 3 timers (en plus des 3 existants M1) :

- `polybot-proxy-factory.timer` : hourly
- `polybot-resolutions.timer` : hourly
- `polybot-goldsky.timer` : hourly
- `polybot-populate-volume.timer` : hourly, offset +30 min apres les
  trades pour laisser Goldsky sync

## Tests unitaires globaux

1. Pour chaque indexer : mock API, verifier qu'on insere correctement
2. `proxy_eoa_map` : insert idempotent (meme proxy 2x -> 1 row)
3. `resolutions` : transition proposed -> disputed -> settled fonctionne
4. `populate_volume_1h` : calcul correct avec un dataset de trades simules

## Tests d'integration

1. Depuis VPS, run `indexer_proxy_factory` sur les 100 derniers blocks
   -> check que des mappings apparaissent dans DuckDB
2. `indexer_resolutions_uma` sur derniere heure -> check qu'on capture
   les `Settle` events recents
3. `indexer_onchain_goldsky` -> check que `trades_all` grossit
4. End-to-end : apres 6h de run, les 15 wallets Tier A doivent avoir
   leurs EOAs mappes dans `proxy_eoa_map`

## Composants reportes (decision 2026-04-24)

- **`indexer_onchain_goldsky`** : reporte. Le subgraph Goldsky
  (`polymarket-orderbook-resync/prod`) est bloque au block 81.2M
  (donnees de ~jan 2026), 108 jours en retard. Aucun autre subgraph
  Goldsky Polymarket disponible. La table `trades_all` reste vide
  jusqu'a ce qu'une source de donnees a jour soit identifiee.
- **`populate_volume_1h`** : reporte. Depend de `trades_all` (Goldsky).
  La colonne `volume_1h` reste NULL conformement a ADR-006.

M3 se cloture avec 2/4 composants livres :
1. `indexer_proxy_factory` ✓
2. `indexer_resolutions_uma` ✓

## A ne PAS faire en M3

- Clustering Victor (reporte M10, cf plan B)
- CEX funding detection (reporte M9)
- Re-scoring complet des wallets (reporte M7)
- Mapping heuristique (confidence < 1.0) — on garde uniquement
  les mappings canoniques v1, les heuristiques viennent en M7

## Budget Alchemy

Estimation consommation M3 :
- Backfill proxy factory : ~1.5M CU (one-shot)
- Incremental proxy factory : ~50K CU/mois
- Incremental resolutions UMA : ~30K CU/mois
- Total : < 2M CU / 300M free tier = 0.7% du quota

Large marge pour M4-M12.
