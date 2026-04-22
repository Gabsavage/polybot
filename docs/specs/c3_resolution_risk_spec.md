# Composant C3 — Resolution Risk Filter — Spec technique

## Objectif

Évaluer le risque qu'un marché Polymarket se résolve de manière 
ambiguë ou soit disputé. Produit un score composite LLM + rules + 
oracle reliability qui enrichit les alertes C1/C2 et répond aux 
commandes `/risk` de l'opérateur.

## Milestone

M5 — C3 Resolution Risk Filter

## Dépendances

- M1 : `markets` (sera populée en M2, mais C3 peut être testée sur 
  dataset simulé)
- M2 : `markets` (metadata complets via Gamma API)
- M3 : `resolutions` (historique de disputes UMA par catégorie)
- Claude API (Anthropic, Haiku 4.5)
- Bot Telegram (pour endpoint `/risk`)

## Architecture globale

Le score C3 est calculé comme **combinaison pondérée** de 3 signaux :
c3_score = 0.50 × llm_score + 0.30 × rules_score + 0.20 × oracle_reliability_score

Où chaque signal est normalisé sur [0.0, 1.0], avec 0.0 = très clean 
(aucun risque) et 1.0 = dispute quasi-certaine.

### Mapping score → catégorie

```python
def score_to_category(score: float) -> str:
    if score < 0.20:
        return "CLEAN"
    elif score < 0.40:
        return "LOW"
    elif score < 0.60:
        return "MEDIUM"
    elif score < 0.80:
        return "HIGH"
    else:
        return "CRITICAL"
```

### Intégration dans les alertes (modulation douce v1)

C3 ne bloque pas les alertes C1/C2 en v1. Mais il modifie leur 
présentation :

- `CLEAN` ou `LOW` : pas de warning, affichage standard
- `MEDIUM` : tag `⚠️` dans l'alerte
- `HIGH` : tag `🚨` dans l'alerte, message "Resolution risk élevé"
- `CRITICAL` : tag `❌🚨` dans l'alerte, message "Résolution très 
  incertaine, diligence renforcée requise"

En v2 post-shadow (M11+), on pourra calibrer pour passer en 
pénalisation dure (filtrer ou réduire size) selon les perfs observées.

## Composant 1 — LLM (50% du score)

### Modèle

**Claude Haiku 4.5** via Anthropic API.

Rationale :
- Cohérent avec ADR-009 (hybride LLM + rules validé en Phase A)
- Coût négligeable : ~$0.25 / M tokens input, ~$1.25 / M tokens output
- Capable de classification sémantique sur question phrasing ambigu
- Latence < 2s (cohérent avec target /risk < 5s)

### Invocation

1 call Haiku par marché **au moment où il apparaît pour la première 
fois** dans la table `markets` (détecté par l'indexer_markets_gamma 
en M2 via le `last_seen_at` NULL).

### Prompt engineering

Template de prompt stable (versionné) :
You are evaluating the resolution risk of a prediction market on
Polymarket. Your task is to assess how likely this market is to be
disputed, resolved ambiguously, or have its outcome contested.
Market question: "{question}"
Resolution source: "{resolution_source}"
Description: "{description}"
Category: "{category}"
End date: "{end_date}"
Evaluate the following dimensions (each 0.0 to 1.0):

Question clarity (0.0 = crystal clear, 1.0 = ambiguous)

Is the question phrasing unambiguous?
Are key terms well-defined?
Example HIGH: "Will X happen soon?" (what is "soon"?)
Example LOW: "Will Bitcoin reach $100K before March 31 2026?"


Source reliability (0.0 = official/trusted, 1.0 = unclear/manipulable)

Is the resolution source specified?
Is it an authoritative source (official announcement, government
body, exchange)?
Example LOW: "Per SEC filing" or "Per official Fed announcement"
Example HIGH: "According to news reports" (which news? who decides?)


Historical dispute risk (0.0 = type never disputed, 1.0 =
category disputed often)

Based on the market category and question type
Sports scores: low dispute rate
Political controversies, identity questions ("is X truly Y"),
subjective assessments: high dispute rate


Edge case vulnerability (0.0 = binary clean outcome, 1.0 = many
edge cases)

Could the answer be "partially yes"?
Could events happen that make the question moot?
Could the exact timing matter?



Return your assessment as JSON only, no other text:
{
"question_clarity": float,
"source_reliability": float,
"historical_dispute_risk": float,
"edge_case_vulnerability": float,
"overall_llm_score": float,
"reasoning": "One or two sentences explaining the main risk factor"
}
The overall_llm_score should be a weighted combination of the four
dimensions, with question_clarity and source_reliability weighted
more heavily (together ~60%) than the other two.

### Parsing de la réponse

```python
import json
from anthropic import Anthropic

def get_llm_score(market: dict) -> tuple[float, str]:
    client = Anthropic()
    
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": build_prompt(market)
        }]
    )
    
    response_text = message.content[0].text
    
    try:
        parsed = json.loads(response_text)
        score = float(parsed["overall_llm_score"])
        reasoning = parsed["reasoning"]
        # Validation
        score = max(0.0, min(1.0, score))  # clamp [0, 1]
        return score, reasoning
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"LLM response parsing failed: {e}")
        # Fallback conservateur : score neutre 0.5
        return 0.5, "LLM parsing failed, defaulted to neutral score"
```

### Coût estimé

Par marché :
- Input : ~600 tokens (prompt + question + description)
- Output : ~100 tokens (JSON réponse)
- Coût par call : ~$0.00015 + $0.000125 = ~$0.00028 (négligeable)

Volume annuel :
- ~15K marchés actifs par an sur Polymarket
- Total : 15K × $0.00028 = **~$4/an** largement sous cap budget

## Composant 2 — Rules dynamiques (30% du score)

3 rules objectives combinées :

### Rule 1 — Historical dispute rate par catégorie

```sql
-- Calcul sur table `resolutions` (populée par indexer_resolutions_uma en M3)
SELECT 
    category,
    COUNT(*) FILTER (WHERE disputed = TRUE) * 1.0 / COUNT(*) AS dispute_rate
FROM resolutions r
JOIN markets m ON m.condition_id = r.condition_id
WHERE r.settled_at >= NOW() - INTERVAL '6 months'
GROUP BY category;
```

Signal normalisé :
```python
def rule_dispute_rate(market: dict, dispute_rates: dict) -> float:
    category = market.get("category", "unknown")
    rate = dispute_rates.get(category, 0.05)  # default 5%
    # Mapping : rate 0% → 0.0, rate 20%+ → 1.0
    return min(rate / 0.20, 1.0)
```

### Rule 2 — Liquidité vs bond UMA

```python
def rule_bond_ratio(market: dict) -> float:
    liquidity = market.get("liquidity_usd", 0)
    uma_bond = 500  # bond standard Polymarket ~$500, à confirmer
    
    if liquidity <= 0:
        return 0.5  # pas de liquidité, neutre
    
    bond_ratio = uma_bond / liquidity
    
    # Si bond < 10% de liquidité, fort incitatif à disputer
    # Si bond > 50% de liquidité, peu d'incitation
    if bond_ratio < 0.10:
        return 1.0
    elif bond_ratio > 0.50:
        return 0.0
    else:
        # Interpolation linéaire entre 0.10 et 0.50
        return (0.50 - bond_ratio) / 0.40
```

### Rule 3 — Fenêtre temporelle de dispute

```python
def rule_time_window(market: dict) -> float:
    end_date = market["end_date"]
    resolution_window_hours = 2  # fenêtre de dispute UMA standard ~2h
    
    hours_to_end = (end_date - datetime.now()).total_seconds() / 3600
    
    # Si résolution imminente (< 24h), peu de temps pour disputer = plus risqué
    if hours_to_end < 24:
        return 0.7
    elif hours_to_end < 72:
        return 0.4
    else:
        return 0.1  # large fenêtre, disputes bien gérées
```

### Score rules composite

```python
rules_score = (
    0.50 * rule_dispute_rate +  # plus important : historique réel
    0.30 * rule_bond_ratio +
    0.20 * rule_time_window
)
```

## Composant 3 — Oracle reliability (20% du score)

Le plus simple : basé sur l'identité du proposer/resolver UMA.

```python
def get_oracle_reliability(market: dict) -> float:
    """
    Retourne 0.0 pour un oracle très fiable (Polymarket Official UMA adapter),
    1.0 pour un oracle inconnu ou historiquement problématique.
    """
    # En M5 v1 : tous les marchés Polymarket utilisent le UMA Optimistic 
    # Oracle V2 via les adapters officiels (UmaCtfAdapter v2 ou Neg Risk).
    # Ces 2 adapters ont un track record solide.
    
    adapter = market.get("adapter", "unknown")
    
    if adapter == "uma_ctf_adapter_v2":
        return 0.1  # très fiable
    elif adapter == "neg_risk_adapter":
        return 0.15  # légèrement moins de recul historique, mais OK
    else:
        return 0.5  # inconnu, prudence
```

En M6+ on pourra raffiner en regardant les stats par proposer sur les 
12 derniers mois (track record individuel).

## Schéma DB

Table `resolution_risk_cache` (migration M5) :

```sql
CREATE TABLE resolution_risk_cache (
    condition_id VARCHAR PRIMARY KEY,
    c3_score DECIMAL(4,3) NOT NULL,  -- score composite [0.0, 1.0]
    category VARCHAR CHECK (category IN ('CLEAN', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    
    -- Breakdown par composant
    llm_score DECIMAL(4,3),
    llm_reasoning VARCHAR,
    llm_model VARCHAR,  -- "claude-haiku-4-5-20251001"
    llm_prompt_version VARCHAR,  -- "v1.0" pour versioning des prompts
    
    rules_score DECIMAL(4,3),
    rules_dispute_rate DECIMAL(4,3),
    rules_bond_ratio DECIMAL(4,3),
    rules_time_window DECIMAL(4,3),
    
    oracle_score DECIMAL(4,3),
    oracle_adapter VARCHAR,
    
    -- Meta
    computed_at TIMESTAMP DEFAULT NOW(),
    invalidated_at TIMESTAMP,  -- si invalidé manuellement, timestamp
    invalidated_reason VARCHAR
);

CREATE INDEX idx_resolution_risk_category ON resolution_risk_cache (category);
CREATE INDEX idx_resolution_risk_computed ON resolution_risk_cache (computed_at DESC);
```

## Cache strategy

**Permanent + invalidation manuelle** (ADR-009 aligné).

### Comportement normal

1. Nouveau marché apparaît dans `markets` via indexer Gamma
2. C3 compute déclenché (appel Haiku + rules + oracle)
3. Résultat stocké dans `resolution_risk_cache`
4. Réutilisé pour toutes les alertes C1/C2 sur ce marché
5. Si le marché résout normalement, jamais recomputed

### Invalidation manuelle via Telegram

Commande `/rerisk <condition_id_or_slug>` :

```python
@bot.command("rerisk")
async def rerisk_command(update, context):
    identifier = context.args[0]
    condition_id = resolve_identifier(identifier)
    
    # Mark as invalidated
    db.execute("""
        UPDATE resolution_risk_cache 
        SET invalidated_at = NOW(), 
            invalidated_reason = 'manual_override'
        WHERE condition_id = ?
    """, condition_id)
    
    # Recompute
    market = db.get_market(condition_id)
    new_score = compute_c3_score(market)
    
    # Reply with new score
    await update.message.reply_text(format_c3_response(new_score))
```

## Endpoint `/risk` (Telegram)

Commande disponible à l'opérateur pour demander un C3 à la demande.

### Parsing de l'entrée

```python
async def risk_command(update, context):
    if not context.args:
        await update.message.reply_text(
            "Usage: /risk <url_or_slug>\n"
            "Example: /risk https://polymarket.com/event/will-fed-cut-rates-june-2026"
        )
        return
    
    input_str = context.args[0]
    
    # Parsing : peut être URL Polymarket ou slug ou condition_id
    condition_id = parse_market_identifier(input_str)
    
    if not condition_id:
        await update.message.reply_text("Market not found. Check URL or slug.")
        return
    
    # Check cache first
    cached = db.get_resolution_risk(condition_id)
    
    if cached and not cached.invalidated_at:
        score_data = cached
    else:
        market = db.get_market(condition_id)
        if not market:
            await update.message.reply_text("Market metadata not found.")
            return
        score_data = compute_c3_score(market)
    
    # Format and reply
    response = format_c3_response_detailed(score_data)
    await update.message.reply_text(response, parse_mode='Markdown')
```

### Format de réponse détaillée
⚖️ Resolution Risk Analysis
📊 Marché : "{market_title}"
🔗 Polymarket
🎯 Score : {c3_score:.2f}/1.00 → {category}
📈 Breakdown :
• LLM analysis : {llm_score:.2f} (50% weight)
{llm_reasoning}
• Rules dynamics : {rules_score:.2f} (30% weight)
- Historical dispute rate : {rules_dispute_rate:.2f}
- Liquidity/bond ratio : {rules_bond_ratio:.2f}
- Time window : {rules_time_window:.2f}
• Oracle reliability : {oracle_score:.2f} (20% weight)
- Adapter: {oracle_adapter}
🔍 Interprétation :
{interpretation_text}
⏱️ Computed : {computed_at_relative}

### Target latence

- **Cache hit** : < 500ms (juste DB read + format)
- **Cache miss** : < 5s (2s LLM + 1s rules + < 1s format + overhead)

## Prompt versioning

Le prompt LLM est versionné (`llm_prompt_version` dans cache) pour permettre des évolutions.

Stratégie :
- v1.0 initial = prompt ci-dessus
- Si on modifie le prompt, version devient v1.1 et on **invalide le cache** pour les marchés actifs (ou on laisse l'ancien pour les historiques)
- Garder trace de quel prompt a été utilisé pour chaque marché historique est utile pour calibration M11

## Intégration avec C1 et C2

### Pour les alertes C1 (Sharp Money Copy)

Dans le flux C1 (cf c1_sharp_money_spec.md) :

```python
def emit_c1_alert(trade: Trade):
    # ... critères de filtrage C1 ...
    
    # Récupération C3
    c3 = get_resolution_risk(trade.condition_id)
    
    if c3.category in ("HIGH", "CRITICAL"):
        alert_visual = "🚨" if c3.category == "HIGH" else "❌🚨"
        warning_text = f"Resolution risk {c3.category} : {c3.llm_reasoning}"
    else:
        alert_visual = ""
        warning_text = ""
    
    telegram_message = format_alert_c1(trade, c3, alert_visual, warning_text)
    send_telegram(telegram_message)
```

### Pour les alertes C2 (Informed Trading)

Même logique que C1, intégré dans le flux de c2_informed_trading_spec.md.

## Critères de succès M5

### Fonctionnels

- Les 3 cas historiques disputés (Zelensky, Ukraine minerals, Barron 
  Trump, cf phase C) reçoivent un score `HIGH` ou `CRITICAL`
- La précision sur un batch test de 50 marchés récents sortis de 
  phase C est > 75% (catégorisation humaine vs LLM)
- `/risk` répond en < 5s sur cache miss, < 500ms sur cache hit

### Techniques

- Cache permanent fonctionne : 2ème `/risk` sur même marché = pas 
  d'appel LLM
- Invalidation `/rerisk` fonctionne : force un recompute
- Coût LLM cumulé sur M5 en test < 1€ total
- Fallback neutre (score 0.5) si LLM parsing échoue

## Tests unitaires

1. Mapping score → catégorie : 5 tests (un par catégorie à la limite)
2. `score_to_category(0.19)` = "CLEAN"
3. `score_to_category(0.20)` = "LOW"  
4. Formule composite : test avec llm=0.8, rules=0.6, oracle=0.3 → 
   score = 0.5*0.8 + 0.3*0.6 + 0.2*0.3 = 0.64
5. Rule dispute_rate : test avec dispute_rate 0% → 0.0, 20% → 1.0, 
   10% → 0.5
6. Rule bond_ratio : test avec ratio 0.05 → 1.0, 0.60 → 0.0
7. Rule time_window : test avec 12h → 0.7, 48h → 0.4, 168h → 0.1
8. Parsing LLM response : JSON valide, invalide, tronqué
9. Cache hit/miss : 2 calls même condition_id → 1 appel LLM
10. Fallback sur parsing échec : retourne 0.5 + log

## Tests d'intégration

1. Test end-to-end sur 3 cas disputés historiques (Barron, Zelensky, 
   Ukraine minerals) : score attendu `HIGH` ou `CRITICAL`
2. Test end-to-end sur 3 cas clean (Fed rate, Bitcoin price, sports) : 
   score attendu `CLEAN` ou `LOW`
3. Test `/risk` Telegram : réponse formatée correcte en < 5s

## Configuration (settings.py)

```python
class C3Settings(BaseSettings):
    # LLM
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_max_tokens: int = 300
    llm_prompt_version: str = "v1.0"
    llm_timeout_seconds: int = 10
    
    # Weights
    weight_llm: float = 0.50
    weight_rules: float = 0.30
    weight_oracle: float = 0.20
    
    # Rules sub-weights
    weight_rule_dispute_rate: float = 0.50
    weight_rule_bond_ratio: float = 0.30
    weight_rule_time_window: float = 0.20
    
    # Category thresholds
    threshold_clean: float = 0.20
    threshold_low: float = 0.40
    threshold_medium: float = 0.60
    threshold_high: float = 0.80
    
    # UMA bond (for rule_bond_ratio)
    uma_bond_usd: float = 500.0
    
    # Cache
    cache_invalidation_allowed: bool = True  # allow /rerisk command
    
    # /risk endpoint
    risk_command_timeout_seconds: int = 5
```

## À ne PAS faire en v1

- ❌ Fine-tuning du modèle Haiku (overkill, prompt engineering suffit)
- ❌ Utiliser plusieurs modèles (ensemble, voting) — overkill en v1
- ❌ Scoring catégorie par source reliability (reporté M8+ si besoin)
- ❌ Auto-invalidation du cache (uniquement manuel via /rerisk)
- ❌ Filtrage dur des alertes selon c3_score (modulation douce v1)
- ❌ API publique /risk (v1 = uniquement Telegram command)

## Évolutions prévues

**M11 (post-shadow mode)** : 
- Calibration empirique des weights LLM/rules/oracle selon les dispute 
  rates observés
- Recalibration des thresholds de catégorie selon distribution 
  observée
- Possiblement passer en pénalisation dure si précision > 80%

**M12+** :
- Track record individuel par proposer UMA
- Prompt v2 avec few-shot learning sur disputes observées en shadow mode