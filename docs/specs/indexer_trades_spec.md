# Indexer Trades — Spec technique

## Objectif

Détecter en quasi-temps réel (latence < 2 min) les nouveaux trades effectués 
par les wallets Tier A trackés, et les stocker dans DuckDB pour consommation 
par C1 (Sharp Money Copy) en M4.

## Milestone

M2 — Indexers de base + seed list Tier A

## Dépendances

- `tracked_wallets` (table DuckDB peuplée en M2 depuis 
  `config/tracked_wallets_seed.yaml`)
- `trades` (table DuckDB, schéma migration 001)
- Polymarket Data API (accessible depuis VPS US sans géoblock)

## Source de données

**Endpoint** : `https://data-api.polymarket.com/trades`

**Paramètres** :
- `user=<proxy_address>` (l'adresse Polymarket, confirmée comme proxy dans 
  le JSON via le champ `proxyWallet`)
- `limit=50` (safe pour absorber les bursts, aucun downside observé)

**Champs utilisés par trade** :
- `proxyWallet` : adresse du wallet (clé de jointure avec tracked_wallets)
- `transactionHash` : hash unique on-chain (clé de dédup)
- `timestamp` : unix timestamp du trade
- `conditionId` : ID du marché Polymarket
- `asset` : token ID spécifique (YES ou NO)
- `side` : "BUY" ou "SELL"
- `size` : montant USD
- `price` : prix par token au moment du trade
- `outcome` : "Yes" ou "No" (pour affichage alert)
- `outcomeIndex` : 0 (YES) ou 1 (NO)
- `title` : nom du marché (pour alertes)
- `slug` + `eventSlug` : pour construire URL Polymarket
- `name` : pseudo public du wallet (pour alertes)

## Architecture

### Fréquence

Polling toutes les **60 secondes** par wallet. Loop async sur les 15 wallets 
Tier A, 1 call HTTP par wallet par tick.

Volume : 15 wallets × 60 calls/heure × 24h = 21 600 calls/jour. Bien sous le 
rate limit Polymarket (100 req/sec = 8.64M req/jour).

### Dédup logic

**Combinaison timestamp + hash** pour maximum de robustesse :

1. Chaque wallet a un `last_seen_timestamp` stocké dans `tracked_wallets`
2. À chaque poll :
   a. Fetch `limit=50` derniers trades du wallet
   b. Filtre côté code : `trades[t.timestamp > last_seen_timestamp]` (rapide)
   c. Pour chaque trade filtré, vérifier si `transactionHash` existe déjà 
      dans `trades` table (dédup robuste)
   d. Si non existant : INSERT dans `trades` table + trigger processing
   e. Update `last_seen_timestamp = max(new_trades.timestamp)` sur le wallet

Justification : timestamp pour filter rapide, hash pour dédup absolu (insensible 
aux trades simultanés, aux réordonnancements API, aux edge cases bloc 
Polygon).

### Schéma de stockage

Table `trades` (M1) :
```sql
CREATE TABLE trades (
    transaction_hash VARCHAR PRIMARY KEY,  -- clé de dédup
    proxy_wallet VARCHAR NOT NULL,          -- FK vers tracked_wallets
    condition_id VARCHAR NOT NULL,          -- FK vers markets (M2)
    asset_id VARCHAR NOT NULL,              -- token ID (YES ou NO)
    side VARCHAR CHECK (side IN ('BUY', 'SELL')),
    size_usd DECIMAL(18,2) NOT NULL,
    price DECIMAL(6,4) NOT NULL,
    outcome VARCHAR,                         -- 'Yes' ou 'No'
    outcome_index INTEGER,                   -- 0 ou 1
    timestamp_unix BIGINT NOT NULL,
    timestamp_ts TIMESTAMP NOT NULL,         -- converti depuis timestamp_unix
    market_title VARCHAR,
    market_slug VARCHAR,
    event_slug VARCHAR,
    wallet_name VARCHAR,                     -- pseudo public au moment du trade
    ingested_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trades_wallet_time ON trades (proxy_wallet, timestamp_ts DESC);
CREATE INDEX idx_trades_market_time ON trades (condition_id, timestamp_ts DESC);
```

Table `tracked_wallets` update (ajouter colonne) :
```sql
ALTER TABLE tracked_wallets ADD COLUMN last_seen_timestamp BIGINT DEFAULT 0;
```

## Gestion des erreurs

- **Timeout Polymarket** (> 10s sur un call) : log warning, skip ce wallet 
  pour ce tick, retry au tick suivant
- **HTTP 429 rate limit** : backoff exponentiel (1s, 2s, 4s, 8s), abandon 
  après 4 tentatives, log warning
- **HTTP 403 géo-block** : log error critique, pousse vers #errors (signifie 
  que le VPS a perdu son IP US — très improbable mais on vérifie)
- **JSON parsing error** : log warning avec raw response (tronquée 500 chars), 
  skip ce trade
- **DuckDB insert error** (duplicate key, etc.) : log info, considère comme 
  trade déjà vu, continue

## Heartbeat

Toutes les N minutes (ex 15 min), log dans `#ops` :
Indexer trades: 15/15 wallets polled, X new trades ingested, Y errors

Si > 3 erreurs consécutives sur un wallet dans une fenêtre 15 min → alerte 
dans #errors "Wallet <address> unreachable".

## Tests unitaires

1. Dédup via transactionHash fonctionne (mock : même hash deux fois → 1 insert)
2. Filter par timestamp fonctionne (mock : trades mix anciens/récents → 
   seuls nouveaux retenus)
3. Insertion d'un trade complet hydrate tous les champs correctement
4. Backoff sur 429 fonctionne
5. Pas d'insert si tous les trades du wallet sont anciens

## Tests d'intégration (avec API réelle)

1. Depuis VPS, poll Domer (0x9d84...), assert qu'on a ≥ 1 trade en réponse
2. Poll de suite après, assert qu'on n'insère pas de doublon (dédup OK)
3. Après 60s, re-poll : si Domer a tradé, on détecte son trade, sinon 
   timestamp reste inchangé

## Edge cases à gérer

- **Trade d'un wallet Tier A dans un marché non-indexé** (marché pas dans 
  snapshot_universe) : on stocke quand même le trade, le manque de 
  metadata marché sera résolu en M3 (sync_markets_gamma)
- **Wallet qui n'a jamais tradé** : `last_seen_timestamp` = 0 initialement, 
  premier poll retourne les 50 derniers trades, tous considérés comme 
  "nouveaux" à leur premier vu mais dédupliqués aux polls suivants via hash
- **Wallet qui trade en burst** (30 trades en 60s) : `limit=50` capture 
  tout, dédup OK, pas de miss

## À ne PAS faire en v1

- ❌ Stream WebSocket (ADR-008 : polling 60s suffit)
- ❌ Mapping proxy↔EOA (arrive en M3)
- ❌ Filtrer trades < $1000 au niveau indexer (on stocke tout, le filtre 
  size se fait dans C1 en M4)
- ❌ Calculer edge du wallet en direct (fait en M7 dans wallet_metrics)