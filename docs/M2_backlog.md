# Backlog M2 — Items a traiter en debut de milestone

Items identifies pendant M1 qui doivent etre regles au demarrage de
M2, AVANT d'attaquer les livrables principaux du milestone.

## Pre-requis techniques (bloquants pour M2)

Aucun. M1 est clos et stable, M2 peut demarrer sans dependance
critique a nettoyer.

## Items cosmetiques / hygiene (non-bloquants, a caser)

### 1. Enrichir scripts/validate_snapshot.py

**Priorite** : faible, confort operationnel
**Source** : backlog gate M1
**Description** : le script actuel ne supporte que `--key <path>`.
Ajouter :
- `--last N` : valide les N derniers snapshots sur R2
- `--timestamp YYYY-MM-DD/HH` : valide un snapshot specifique par date
- `--list` : liste tous les snapshots disponibles avec date, taille,
  nombre de rows
**Effort estime** : 30 min

### 2. Documenter le nommage UTC des snapshots R2

**Priorite** : faible
**Source** : backlog gate M1
**Description** : DEJA FAIT via ADR-012 cree le 2026-04-22. A ignorer
(check que l'ADR existe bien dans docs/ADRs/012_utc_timestamps_r2_naming.md).

### 3. Supprimer ancien token Cloudflare

**Priorite** : securite
**Source** : backlog gate M1
**Description** : DEJA FAIT manuellement le 2026-04-22. A ignorer.

### 4. chmod 600 sur .env local Mac

**Priorite** : securite
**Source** : backlog gate M1
**Description** : DEJA FAIT manuellement le 2026-04-22. A ignorer.

## Specs deja pretes pour M2

La spec complete est disponible dans docs/specs/indexer_trades_spec.md.
Inclut :
- Endpoint Polymarket Data API confirme (proxyWallet valide via curl)
- Polling 60s, limit=50
- Dedup via timestamp + transactionHash (belt+suspenders)
- Schema DB complet
- Tests unitaires et d'integration
- Edge cases identifies
- Configuration pydantic-settings

## Livrables M2 (rappel plan B §4)

1. `indexer_markets_gamma` — polling 15 min, upsert `markets`,
   pagination + rate limit
2. `indexer_trades_dataapi` — polling 60s sur 15 wallets Tier A,
   insert `trades`, dedup via spec
3. Seed list Tier A finalisee (DEJA FAIT, 15 wallets dans
   config/tracked_wallets_seed.yaml)
4. Script `scripts/seed_tier_a.py` pour inserer les wallets dans
   DuckDB `tracked_wallets` table
5. Tests d'integration avec mocks API
6. Logs structures /var/log/polybot/

## Criteres de validation M2 (rappel)

- Apres 24h : `COUNT(markets)` > 10 000
- Apres 24h avec Tier A actif : `COUNT(trades)` > 10
- `COUNT(tracked_wallets WHERE tier='A')` = 15
- Logs < 1% erreurs / 24h

## Decision gate M2 → M3 (rappel)

4 questions a repondre avant passage M3 :
1. Seed list defendable ? Pour chaque wallet, justifier en 1 phrase
   pourquoi Tier A
2. Rate limit Data API tient a 60s x 15 wallets ? Marge si on passe
   a 30 wallets ?
3. Patterns inattendus dans les donnees brutes qui devraient modifier
   le plan aval ?
4. Un wallet Tier A silencieux > 30j ? Remplacement envisage ?

## Ordre d'execution recommande pour M2

1. Implementer `indexer_markets_gamma` en premier (populate `markets`
   table, 15-20K rows attendus)
2. Implementer `indexer_trades_dataapi` en second (depend de `markets`
   pour valider condition_id)
3. Implementer `scripts/seed_tier_a.py` (rapide, 20 min)
4. Tests d'integration sur les 3 composants
5. Deploiement VPS : ajout de 2 systemd timers (markets 15min, trades 60s)
6. Gate M2 apres 24h de run
