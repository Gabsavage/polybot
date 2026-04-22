# Composant C2 — Informed Trading Alert — Spec technique

## Objectif

Détecter et alerter sur des patterns d'informed trading (insider probable 
ou sharp conviction forte) sur les marchés Polymarket, en scannant en 
continu les marchés "hot" et en appliquant un score composite basé sur 
7 features on-chain + 1 signal d'alignement directionnel minimal.

## Milestone

M6 — C2 MVP + alert_outcomes + promotion shadow mode

## Leçons de phase C intégrées

1. **Heuristiques Niveau A incomplètes** : precision observée 50% sur 
   le cas Iran. Les features seules ne distinguent pas "insider gagnant" 
   de "contrariant perdant". → Ajout de l'alignment directionnel v0.
2. **Biais de survivorship du ground truth** : les cas documentés 
   (rapport 3) sont tous des gagnants. Les vrais insiders qui se sont 
   trompés ne sont pas dans le GT. → Le bot doit être honnête sur sa 
   precision réelle attendue (pas 90% comme en v1 erronée, plutôt 
   40-60%).
3. **Human-in-the-loop obligatoire** : precision 50% ne permet pas 
   d'auto-trade. Le bot émet, l'opérateur décide. → Pas d'auto-trade 
   en v1.
4. **Shadow mode anticipé** : dès M6, les alertes C2 vont dans #alerts 
   mais l'opérateur ne trade pas pendant 4+ semaines. Les alertes sont 
   enrichies post-résolution pour calibration.

## Dépendances

- M1 : `clob_orderbook_snapshots` sur R2 (pour récupérer price 4h avant)
- M2 : `markets` (metadata), `trades` (trades temps réel Tier A)
- M3 : `proxy_eoa_map` (consolidation per-user), `resolutions` (trigger 
  post-résolution)
- M5 : C3 Resolution Risk (enrichissement alerte)
- M6 : `alert_outcomes` (table pour logger post-résolution)

## Trigger

Scan périodique toutes les 5 minutes, déclenché par systemd timer.

## Sélection des marchés "hot" (scope scan)

Un marché est éligible au scan C2 si **au moins UNE** des 3 conditions 
est vraie (combinaison OR) :

### Condition 1 — Volume explosif récent
volume_1h / avg_volume_1h_last_7d > 3

Le marché a un volume 1h actuel > 3× la moyenne 1h sur les 7 derniers 
jours. Signal qu'il se passe quelque chose d'inhabituel.

### Condition 2 — Mouvement de prix significatif
abs(price_change_1h) > 0.10 AND volume_1h > 500

Le prix a bougé de > 10% en 1h ET il y a au moins $500 de volume dans 
l'heure (sinon c'est un trade isolé sur un marché mort, pas intéressant).

### Condition 3 — Approche de résolution avec activité
time_to_resolution < 72h AND volume_24h > 10000

Marché proche de résolution avec volume significatif. Fenêtre classique 
d'activité insider.

### Implémentation

Materialized view `markets_hot` recalculée toutes les 5 minutes :

```sql
CREATE OR REPLACE VIEW markets_hot AS
SELECT 
    m.condition_id,
    m.title,
    m.slug,
    m.end_date,
    m.volume_24h,
    m.liquidity,
    -- Condition 1 : volume spike
    (m.volume_1h / NULLIF(m.avg_volume_1h_7d, 0)) > 3 AS vol_spike,
    -- Condition 2 : price move
    (ABS(m.price_change_1h) > 0.10 AND m.volume_1h > 500) AS price_move,
    -- Condition 3 : near resolution
    (EXTRACT(EPOCH FROM (m.end_date - NOW())) / 3600 < 72 
     AND m.volume_24h > 10000) AS near_resolution,
    -- Flag global
    ((m.volume_1h / NULLIF(m.avg_volume_1h_7d, 0)) > 3
     OR (ABS(m.price_change_1h) > 0.10 AND m.volume_1h > 500)
     OR (EXTRACT(EPOCH FROM (m.end_date - NOW())) / 3600 < 72 
         AND m.volume_24h > 10000)) AS is_hot
FROM markets m
WHERE m.resolved = FALSE
  AND m.active = TRUE;
```

## Les 7 features C2

Pour chaque marché hot, calcul des 7 features suivantes. Chaque feature 
produit un **résultat binaire** (passe / ne passe pas son seuil) et 
contribue à +1 au score composite.

### Feature 1 — Fresh wallets concentration

**Métrique** : pourcentage du volume 1h provenant de wallets créés 
il y a moins de 7 jours.

```sql
SELECT 
    SUM(CASE WHEN (t.timestamp_ts - w.first_seen_ts) < INTERVAL '7 days' 
             THEN t.size_usd ELSE 0 END) / NULLIF(SUM(t.size_usd), 0) 
    AS fresh_wallets_ratio
FROM trades_all t
JOIN wallets w ON w.address = t.proxy_wallet
WHERE t.condition_id = ?
  AND t.timestamp_ts >= NOW() - INTERVAL '1 hour';
```

**Seuil** : `fresh_wallets_ratio > 0.50`

Rationale : un insider typique crée un wallet dédié pour cacher son 
identité. Si > 50% du volume récent vient de wallets neufs, c'est 
suspect.

### Feature 2 — Top-5 holders concentration

**Métrique** : pourcentage du volume 1h détenu par les 5 plus gros 
holders.

```sql
WITH top5 AS (
    SELECT proxy_wallet, SUM(size_usd) AS total
    FROM trades_all
    WHERE condition_id = ?
      AND timestamp_ts >= NOW() - INTERVAL '1 hour'
    GROUP BY proxy_wallet
    ORDER BY total DESC
    LIMIT 5
)
SELECT SUM(total) / (SELECT SUM(size_usd) FROM trades_all 
                     WHERE condition_id = ? 
                     AND timestamp_ts >= NOW() - INTERVAL '1 hour')
```

**Seuil** : `top5_concentration > 0.70`

Rationale : un vrai move de foule implique beaucoup de petits traders. 
Un move concentré sur 5 wallets suggère une coordination ou un insider.

### Feature 3 — Time to event

**Métrique** : heures restantes avant la résolution du marché.

```sql
SELECT EXTRACT(EPOCH FROM (end_date - NOW())) / 3600 AS hours_to_event
FROM markets WHERE condition_id = ?;
```

**Seuil** : `hours_to_event < 48`

Rationale : les insiders attendent souvent le dernier moment pour prendre 
position, quand l'information devient asymétrique mais avant le reveal.

### Feature 4 — Niche market flag

**Métrique** : volume cumulatif total du marché depuis sa création.

```sql
SELECT SUM(size_usd) AS cumul_volume 
FROM trades_all 
WHERE condition_id = ?;
```

**Seuil** : `cumul_volume < 50000` (marché niche/petit)

Rationale : les gros marchés populaires ont trop d'intelligence collective 
pour qu'un insider ait un edge significatif. Les marchés niches sont 
asymétriques : peu de traders informés, beaucoup de traders naïfs.

### Feature 5 — Price momentum 1h

**Métrique** : amplitude du mouvement de prix sur 1h.

```sql
SELECT (price_now - price_1h_ago) / price_1h_ago AS momentum_1h
FROM prices_1m 
WHERE condition_id = ?
-- récupérer le dernier et celui d'il y a 1h
```

**Seuil** : `abs(momentum_1h) > 0.05` (mouvement > 5% sur 1h)

Rationale : un mouvement significatif = quelque chose se passe, pas juste 
du noise. Important : on mesure l'amplitude, pas la direction (l'alignment 
est traité à part).

### Feature 6 — Volume Z-score robuste

**Métrique** : écart-type du volume 1h actuel vs distribution 7j.

```sql
WITH stats AS (
    SELECT 
        AVG(volume_1h) AS mean_vol,
        STDDEV(volume_1h) AS sd_vol
    FROM prices_1m
    WHERE condition_id = ?
      AND timestamp_ts >= NOW() - INTERVAL '7 days'
      AND timestamp_ts < NOW() - INTERVAL '1 hour'
)
SELECT (current_volume_1h - mean_vol) / NULLIF(sd_vol, 0) AS z_score
FROM stats, (SELECT volume_1h AS current_volume_1h FROM prices_1m 
             WHERE condition_id = ? ORDER BY timestamp_ts DESC LIMIT 1);
```

**Seuil** : `z_score > 3.0`

Rationale : cap le bruit naturel du marché. Z-score > 3 = événement à 
probabilité < 1% en distribution normale.

### Feature 7 — Single market dominance (anti-pattern flag)

**Métrique** : proportion du volume 1h qui provient d'un seul wallet.

```sql
WITH volumes AS (
    SELECT proxy_wallet, SUM(size_usd) AS vol
    FROM trades_all
    WHERE condition_id = ?
      AND timestamp_ts >= NOW() - INTERVAL '1 hour'
    GROUP BY proxy_wallet
)
SELECT MAX(vol) / SUM(vol) AS single_dominance
FROM volumes;
```

**Seuil** : `single_dominance > 0.60`

Rationale : si un seul wallet fait 60%+ du volume, c'est souvent un 
gros whale qui prend position discrètement, signal d'un informed trade.

### Feature reportée M9 : shared_cex_deposit_ratio

Non implémentée en M6 faute de la couche CEX funding detection (M9). 
Ce sera la 8ème feature après M9.

## Score composite

```python
score = sum([
    fresh_wallets_ratio > 0.50,
    top5_concentration > 0.70,
    hours_to_event < 48,
    cumul_volume < 50000,
    abs(momentum_1h) > 0.05,
    z_score > 3.0,
    single_dominance > 0.60,
])

# Alerte émise si score >= SEUIL_ALERTE
```

**SEUIL_ALERTE initial : 4/7** (ajustable en shadow mode).

### Stratégie d'ajustement du seuil

- Shadow mode observe 30+ alertes résolues
- Si precision observée < 25% ET volume d'alertes > 3/jour → monter 
  seuil à 5/7
- Si precision > 40% ET < 1 alerte/jour → descendre à 3/7 (désactiver 
  feature 4 qui est la plus restrictive)
- Ne JAMAIS descendre sous 3/7 en v1 (trop bruité)

## Alignment directionnel v0

### Objectif

Distinguer informed trade gagnant de contrariant perdant, sans filtrer 
en v0 (juste logger pour calibration M11).

### Formule

Pour chaque alerte C2, calculer :

```python
# 1. Récupérer price_at_trade (prix moyen pondéré des trades dans la 
#    fenêtre des 10 min autour de l'alerte)
price_at_trade = get_weighted_avg_price(condition_id, alert_time, window_min=10)

# 2. Récupérer price_4h_before depuis CLOB snapshots R2
price_4h_before = get_clob_midpoint(condition_id, alert_time - 4h)

# 3. Calculer momentum
momentum_4h = (price_at_trade - price_4h_before) / price_4h_before

# 4. Déterminer direction dominante du trade (BUY YES ou BUY NO)
#    Si majorité de BUY YES → direction = YES
#    Si majorité de BUY NO → direction = NO
dominant_direction = get_dominant_direction(condition_id, alert_time)

# 5. Calculer alignment
if dominant_direction == "YES":
    if momentum_4h > 0.01:
        alignment = +1  # suit le mouvement, informé probable
    elif momentum_4h < -0.01:
        alignment = -1  # va contre le mouvement, contrariant
    else:
        alignment = 0   # neutre
elif dominant_direction == "NO":
    # symétrique : un BUY NO qui suit une baisse de prix YES = +1
    if momentum_4h < -0.01:
        alignment = +1
    elif momentum_4h > 0.01:
        alignment = -1
    else:
        alignment = 0
```

### Intégration

- Stocké dans `alerts.alignment_score` (colonne INT ajoutée migration M6)
- **Affiché dans l'alerte Telegram** (en information, pas en filtre)
- **NON-filtrant en v0** : une alerte avec `alignment_score = -1` 
  (contrariant probable) est quand même émise — on log pour calibration 
  M11
- En M11, on corrélera `alignment_score` avec `was_direction_correct` 
  (post-résolution). Si forte corrélation → filtrer en v1 les `alignment = -1`.

### Edge cases

- **Pas de snapshot CLOB 4h avant** (markets nouveaux < 4h) : 
  `alignment_score = NULL`, logger warning
- **Momentum ambigu (flat)** : `alignment_score = 0`
- **Direction mixte** (50/50 BUY YES / BUY NO dans la fenêtre) : 
  `alignment_score = NULL`, edge case rare

## Dédup et rate limiting

### Dédup par marché

**1 alerte C2 par marché par fenêtre 6h glissante.**

```python
# Pseudo-code
def should_emit_alert(condition_id):
    last_alert = query("SELECT emitted_at FROM alerts 
                        WHERE component='C2' AND condition_id=? 
                        ORDER BY emitted_at DESC LIMIT 1", condition_id)
    if last_alert and (now() - last_alert) < 6*3600:
        return False
    return True
```

### Cap global

- **Max 2 alertes C2 par heure** (anti-burst)
- **Max 5 alertes C2 par jour** (cap quotidien)

Si dépassement : garder les alertes avec le score le plus élevé, 
ignorer les autres (log info : "C2 alert suppressed, cap reached").

## Format de l'alerte Telegram

Canal : #alerts (shadow mode dès M6)
🔴 [INFORMED] Signal haute conviction (C2)
📊 Marché : <market_title>
🔗 https://polymarket.com/event/<event_slug>
📈 Prix : <price_1h_ago> → <current_price> (<change_1h>%)
💹 Volume 1h : $<volume_1h> (Z-score <z_score>)
🧬 Features validées : <N>/7
✓ Fresh wallets : <fresh_ratio>%
✓ Top-5 concentration : <top5_ratio>%
✓ Time to resolution : <hours>h
✓ Niche market ($<cumul_volume>)
... (seulement les features activées)
🧭 Alignment : <+1|0|-1> (momentum 4h = <momentum_4h>%)
└ <interprétation humaine>
⚖️ Resolution Risk : <C3_result>
💡 Size suggéré : <size_suggested>€ (conservateur, shadow mode)
⏱️ alert_id AL_YYYYMMDD_XXXX · emitted at <timestamp>

## Stockage des alertes C2

Colonnes additionnelles dans `alerts` (migration M6) :

```sql
ALTER TABLE alerts ADD COLUMN score INT;  -- score composite N/7
ALTER TABLE alerts ADD COLUMN features_passed VARCHAR;  
  -- JSON array ex ["fresh_wallets", "top5_concentration", "niche"]
ALTER TABLE alerts ADD COLUMN alignment_score INT;
  -- -1, 0, +1 ou NULL
ALTER TABLE alerts ADD COLUMN momentum_4h DECIMAL(6,4);
  -- raw momentum value, pour analyse post-hoc
```

## Table alert_outcomes (M6)

```sql
CREATE TABLE alert_outcomes (
    alert_id VARCHAR PRIMARY KEY,
    condition_id VARCHAR NOT NULL,
    resolved_at TIMESTAMP,
    resolution_outcome VARCHAR CHECK (resolution_outcome IN ('YES', 'NO', 'INVALID', 'PENDING')),
    direction_traded VARCHAR,  -- 'YES' ou 'NO' (du trade flaggé)
    was_direction_correct BOOLEAN,
    price_at_alert DECIMAL(6,4),
    price_at_resolution DECIMAL(6,4),
    shadow_pnl_simulated DECIMAL(18,2),  
    -- PnL hypothétique si opérateur avait tradé le size_suggéré
    computed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_alert_outcomes_market ON alert_outcomes (condition_id);
```

Peuplée par job `log_alert_outcomes` daily qui :
1. Joint `alerts` avec `resolutions` via `condition_id`
2. Calcule `was_direction_correct` et `shadow_pnl_simulated`
3. Update `alerts.outcome_known = TRUE` pour les alertes résolues

## Critères de succès M6

### Techniques

- Materialized view `markets_hot` se recalcule toutes les 5 min sans 
  erreur
- C2 scan s'exécute en < 30s sur l'ensemble de `markets_hot` (~50-200 
  marchés)
- Durée totale end-to-end (scan → features → alerte) < 60s

### Fonctionnels

- En shadow mode, sur les 30 premières alertes émises :
  - Au moins 20 ont `alignment_score` non-NULL (⇒ snapshot CLOB 4h 
    avant existe)
  - Distribution raisonnable : pas 100% `alignment = +1` ou 100% `= -1`
- Aucune alerte avec score < 4/7 émise (seuil respecté)
- Aucune duplication (1 alerte/marché/6h validée)
- Rate limit respecté (pas > 2/h, pas > 5/jour)

### Shadow mode (3-4 semaines après M6)

- Precision observée ≥ 25% (plancher acceptable, cf escape valve M12)
- Au moins 15 alertes résolues
- `alignment_score` corrélé à `was_direction_correct` (corrélation > 0.2)

## Tests unitaires

1. `markets_hot` view calcule correctement les 3 conditions OR
2. Chaque feature retourne un booléen correct sur dataset simulé
3. Score composite = somme des features (test sur 7 combinaisons 
   représentatives)
4. Dédup 6h fonctionne (2 alertes même marché dans 3h → 1 émise, 
   2ème ignorée)
5. Cap 2/h respecté (5 alertes tentées en 30 min → 2 premières émises)
6. `alignment_score` calculé correctement pour 4 cas : BUY YES + 
   momentum positif, BUY YES + momentum négatif, BUY NO + momentum 
   positif, BUY NO + momentum négatif

## Tests d'intégration

1. Scan manuel sur les 10 derniers marchés hot de la journée → vérifier 
   qu'au moins 1 alerte candidate apparaît
2. Alerte forcée sur un marché connu → vérifier message Telegram 
   bien formatté
3. Résolution d'un marché avec une alerte → vérifier `alert_outcomes` 
   peuplée correctement après `log_alert_outcomes` daily

## À ne PAS faire en v1

- ❌ Auto-trade (ADR-010)
- ❌ Score pondéré continu (v1 = simple sum binaire, plus lisible)
- ❌ Alignment filtrant (v0 : juste loggé, calibration M11)
- ❌ Feature 8 CEX funding (M9)
- ❌ Clustering Victor (M10)
- ❌ ML pour classifier insider vs contrariant (au-delà de M12, si 
  la data le supporte)

## Configuration (settings.py)

```python
class C2Settings(BaseSettings):
    # Scan parameters
    scan_interval_minutes: int = 5
    
    # Hot market criteria
    vol_spike_ratio_threshold: float = 3.0  # volume_1h vs avg 7d
    price_move_1h_threshold: float = 0.10  # 10%
    price_move_min_volume: float = 500.0
    near_resolution_hours: int = 72
    near_resolution_min_volume_24h: float = 10000.0
    
    # Feature thresholds
    fresh_wallets_min_ratio: float = 0.50
    top5_min_concentration: float = 0.70
    time_to_event_max_hours: int = 48
    niche_market_max_cumul_volume: float = 50000.0
    momentum_1h_min: float = 0.05
    z_score_min: float = 3.0
    single_dominance_min: float = 0.60
    
    # Alert threshold
    score_min: int = 4  # N/7 pour émettre
    
    # Dedup and rate limit
    dedup_window_hours: int = 6
    max_alerts_per_hour: int = 2
    max_alerts_per_day: int = 5
    
    # Alignment
    momentum_4h_threshold: float = 0.01  # 1% pour déterminer signe
    alignment_lookback_hours: int = 4

    # Sizing (shadow mode = conservative)
    shadow_mode_size_multiplier: float = 0.5  # 50% du Kelly normal
```