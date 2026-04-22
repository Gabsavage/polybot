# Composant C1 — Sharp Money Copy — Spec technique

## Objectif

Émettre des alertes Telegram en quasi-temps réel (latence < 2 min) quand 
un wallet Tier A prend une position significative, avec un sizing recommandé 
pour l'opérateur humain.

## Milestone

M4 — C1 Sharp Money Copy

## Dépendances

- `trades` (populée par indexer_trades en M2)
- `tracked_wallets` (seed list Tier A, M2)
- `markets` (metadata marchés, M2)
- `alerts` (table pour logger les alertes émises, M4)
- Bot Telegram (token, chat, topics configurés)

## Trigger

Déclenché automatiquement à chaque INSERT dans la table `trades` (via 
poll/trigger dans l'orchestrator en M4, ou via re-scan périodique).

## Logique de filtrage (décider si émettre une alerte)

Un trade déclenche une alerte SEULEMENT si tous ces critères sont remplis :

### Critère 1 — Size minimum
size_usd >= 1000

Rationale : un sharp Tier A fait potentiellement des dizaines de trades par 
jour. Filtrer sur conviction significative ($1K+) donne un bon ratio 
signal/bruit.

À ajuster en shadow mode : si < 1 alerte/jour, loosen à $500. Si > 10/jour, 
tighten à $2000.

### Critère 2 — Rate limit par wallet x market
Pas d'alerte émise pour (wallet, market_id) dans les 3 dernières heures

Rationale : si un sharp fait de l'averaging (achat échelonné), on capte la 
première position. La 2ème/3ème alerte dans les 3h n'apporte pas de 
nouvelle info.

Si le sharp revient 3h+ après, c'est potentiellement une nouvelle thèse 
(news intermédiaire), méritant une nouvelle alerte.

### Critère 3 — Dédup de base
Hash bucket = (wallet_address, market_id, side, timestamp // 300)
= identifiant unique par fenêtre de 5 minutes

Empêche les doubles alertes si l'orchestrator est relancé ou si un trade 
est traité 2 fois pour une raison technique.

### Critère 4 — Liquidité minimale
Best bid depth + best ask depth >= 500 USD (= 10 × size_min / 20)

Si le marché est ultra illiquide, on n'alerte pas du tout (impossible de 
rentrer sans slipper massivement).

Si la liquidité est entre 500 et 10×size_suggéré → tag `⚠️ low_liquidity` 
dans l'alerte (on émet quand même, mais on prévient).

## Sizing recommandé

Formule **quarter-Kelly** fractionnaire :
size_suggested_usd = bankroll × 0.25 × edge_estimated × confidence_multiplier

### Paramètres v1

| Paramètre | Valeur | Source |
|-----------|--------|--------|
| `bankroll` | Lu depuis `bankroll_state` (mis à jour via `/bankroll` command) | User |
| `0.25` | Quarter-Kelly (conservateur) | ADR Kelly fractionnaire |
| `edge_estimated` | 0.04 si A1, 0.02 si A2 | Défaut v1, recalibré M7 |
| `confidence_multiplier` | 1.0 si A1, 0.6 si A2 | Défaut v1 |

### Exemple

Bankroll $2000, alerte Tier A1 :
size = 2000 × 0.25 × 0.04 × 1.0 = $20

Bankroll $2000, alerte Tier A2 :
size = 2000 × 0.25 × 0.02 × 0.6 = $6

### Caps absolus

- `size_suggested_max = 5% × bankroll` (cap de sécurité)
- `size_suggested_min = $10` (si calcul donne moins, on suggère $10 
  sinon pas la peine d'alerter)

## Tags warning

Tags ajoutés à l'alerte (informatif, ne bloquent pas l'émission) :

- `⚠️ low_liquidity` : si `depth_1pct < 10 × size_suggested`
- `⚠️ first_time_on_market` : si ce wallet n'a jamais tradé sur ce 
  `condition_id` avant (nécessite une query historique rapide)
- `⚠️ possible_late_entry` : si le prix a bougé de > 10% dans les 15 min 
  précédant le trade du sharp (on checke via `clob_snapshots` sur R2 ou 
  via les autres trades du marché en DB)

## Format de l'alerte Telegram

Canal : #alerts
Format inspiré du plan B §9.2 :
🎯 Sharp Money Alert (C1)
👤 Wallet : <wallet_name> (Tier <A1|A2>)
📊 Marché : <market_title>
💰 Trade : <BUY|SELL> <YES|NO>
💵 Size : $<size_usd> @ <price>
📈 Move : <N/A en M4, ajouté en M6 via alignment_score>
⚖️ Resolution Risk : <C3 result en M5, placeholder en M4>
💡 Size suggéré : <size_suggested_usd>€ (<%bankroll>%, quarter-Kelly)
<tags warning si applicable>
🔗 https://polymarket.com/event/<event_slug>
⏱️ alert_id <AL_YYYYMMDD_XXXX>

## Stockage des alertes

Table `alerts` (M1) :
```sql
CREATE TABLE alerts (
    alert_id VARCHAR PRIMARY KEY,  -- format AL_YYYYMMDD_XXXX
    component VARCHAR CHECK (component IN ('C1', 'C2', 'C3_manual')),
    emitted_at TIMESTAMP DEFAULT NOW(),
    trade_hash VARCHAR,  -- FK vers trades.transaction_hash
    wallet_address VARCHAR,
    condition_id VARCHAR,
    side VARCHAR,
    size_usd DECIMAL(18,2),
    price DECIMAL(6,4),
    size_suggested_usd DECIMAL(18,2),
    resolution_risk_score DECIMAL(3,2),  -- placeholder en M4
    tags VARCHAR[],  -- array de tags warning
    telegram_message_id BIGINT,  -- pour édition ultérieure si résolution
    -- Shadow mode fields (M6)
    shadow_mode BOOLEAN DEFAULT FALSE,
    alignment_score INTEGER,  -- -1, 0, +1 ou NULL
    -- Post-résolution fields (M6)
    outcome_known BOOLEAN DEFAULT FALSE,
    was_direction_correct BOOLEAN,
    realized_pnl_simulated DECIMAL(18,2)
);
```

## Gestion des erreurs

- Telegram API down : retry 3 fois avec backoff, puis log dans #errors et 
  DB. Alerte sera re-tentée au prochain trigger.
- Bankroll pas à jour (> 14 jours) : inclure warning dans l'alerte "Bankroll 
  pas update depuis X jours, size peut être imprecis"
- Wallet trouvé dans trades mais pas dans tracked_wallets : log warning, 
  ne pas émettre (probable bug de consistency)

## Tests unitaires

1. Trade < $1000 → pas d'alerte
2. Trade > $1000 sur wallet A1 → alerte avec size quarter-Kelly
3. Trade dans les 3h suivant une alerte sur même (wallet, market) → pas 
   d'alerte
4. Trade sur marché illiquide (< $500 depth) → pas d'alerte
5. Trade sur marché mid-liquidity → alerte avec tag low_liquidity
6. Trade A2 → sizing 0.6× vs A1

## Tests d'intégration

1. Forger un trade fictif sur un wallet Tier A1 → alerte Telegram reçue 
   avec format correct
2. Même trade re-poussé 2x → pas de dédup Telegram (déjà vu)
3. Trade sur wallet Tier A2 → sizing plus conservateur

## À ne PAS faire en v1

- ❌ Anti-honeypot sophistiqué (reporté M7, cf plan B)
- ❌ Scoring d'edge dynamique par wallet (défaut v1, recalibré M7)
- ❌ Alertes agrégées sur plusieurs trades dans la fenêtre de 3h
- ❌ Auto-trade (ADR-010, jamais en v1)
- ❌ Alertes sur les SELL (v1 = uniquement BUY car on veut copier les 
  entrées de position, pas les sorties)

## Configuration (settings.py)

```python
class C1Settings(BaseSettings):
    size_min_usd: float = 1000.0
    rate_limit_hours: int = 3  # 1 alerte / (wallet, market) / 3h
    dedup_bucket_seconds: int = 300  # 5 min bucket
    liquidity_min_depth: float = 500.0
    kelly_fraction: float = 0.25
    edge_default_a1: float = 0.04
    edge_default_a2: float = 0.02
    confidence_multiplier_a1: float = 1.0
    confidence_multiplier_a2: float = 0.6
    size_max_pct_bankroll: float = 0.05
    size_min_alert: float = 10.0
```

Permet de tuner sans toucher au code, juste via `.env` ou reload.