# Phase C — Plan de recherche et backtest

*Document de référence pour la phase de validation empirique qui précède le développement. Destiné à être versionné dans les project files. Cadrage convenu lors de l'échange préparatoire : backfill 12 mois glissants (avril 2025 → avril 2026) + cibles Théo (oct-nov 2024), approche duale faux positifs (A base rate + B sharps connus), allocation effort 50% C2 / 35% C1 / 15% C3, Scénario B hybride sur 2 semaines (~30-40h) avec notebook pilote en annexe.*

*Version 1.0 — avril 2026.*

---

## 0. TL;DR de la phase C

Avant d'investir 4-6 semaines à coder le bot, on valide empiriquement sur des données historiques que les trois composants auraient effectivement fonctionné. Plutôt qu'un backtest exhaustif — irréaliste en 30-40h — on vise **une conviction ciblée sur les zones d'incertitude méthodologique les plus fortes** : calibration des seuils C2 sur les 18 cas forensiques sans overfitting, identification de sharps indépendants sans seed list pour C1, et scoring C3 sur les 3-4 marchés historiquement disputés.

La phase C est structurée en trois livrables :

1. **Un dataset de ground truth** formalisé en CSV/Parquet (18 cas forensiques + 8-10 sharps positifs + échantillon témoin aléatoire).
2. **Le présent plan écrit** qui spécifie pour chaque expérience : la question, les données, la méthode, les critères de succès, le temps estimé.
3. **Un notebook pilote** qui reconstruit le cluster Iran strikes OU Maduro sur la stack cible (Dune free + Goldsky + DuckDB + polars) pour valider que le pipeline tient la route, hors de tout commitment de dev.

**Decision gate final** : si à la fin de la phase C on a (a) retrouvé ≥ 3 des 4 cas les plus clean via les heuristiques Niveau A du rapport 3, (b) identifié ≥ 5 sharps indépendants de la seed list via BSS/CLV avec FDR BH, (c) scoré correctement Zelensky suit / Ukraine minerals en `[HIGH]` ou `[CRITICAL]`, alors phase D (dev) est validée. Sinon on ajuste les heuristiques avant de coder.

**Contrainte budget phase C** : pas d'upgrade Dune Plus avant d'avoir éprouvé le free tier. On accepte que certaines queries soient longues ou requièrent du découpage, plutôt que de cramer 49$ sans savoir.

---

## 1. Cadrage méthodologique

### 1.1 Ce qu'on teste, ce qu'on ne teste pas

**On teste** :
- Les heuristiques Niveau A du rapport 3 (fresh wallet + concentration + CEX shared + pré-event) auraient-elles flaggé les cas connus ?
- Les métriques de skill du rapport 4 (edge, CLV, BSS) identifient-elles les sharps publiquement connus et en trouvent-elles de nouveaux ?
- Le LLM Haiku score-t-il correctement l'ambiguïté sémantique des marchés historiquement disputés ?
- Le pipeline technique (Dune + Goldsky + DuckDB + polars sur VPS) tient-il la charge d'un backfill 12 mois ?

**On ne teste pas** :
- Des modèles ML supervisés (Isolation Forest, XGBoost) — trop peu de labels, risque d'overfitting massif sur 18 cas.
- La latence temps réel — on est offline pendant toute la phase C.
- L'anti-honeypot sur cas réels — aucun cas documenté de honeypot réussi, on teste uniquement sur cas synthétiques (cf §5.B.4).
- L'exécution, le sizing réel, l'interface Telegram.

### 1.2 Trois vérités inconfortables qui structurent le protocole

Reprises du rapport 4 §9.5 parce qu'elles conditionnent chaque choix méthodologique qui suit :

**(1) Il n'y a pas de ground truth labelée propre.** Les 18 cas forensiques sont un corpus d'indices, pas de preuves juridiques. La ligne sharp/insider est poreuse (cas Théo). On produit des **suspicion scores probabilistes**, jamais de labels binaires. La "precision" du composant 2 n'est pas mesurable strictement — on mesure un intervalle borné.

**(2) Le multiple testing détruit la plupart des claims.** Sur 1-3M wallets historiques, une dizaine de features, et des seuils ajustés, on va produire des dizaines de milliers de "signaux" sous $H_0$. **FDR Benjamini-Hochberg est systématique**, pas optionnel. Tout leaderboard sans correction est du bruit.

**(3) Polymarket a des limites structurelles de visibilité.** Proxy wallets exigent mapping préalable. Order book off-chain invisible historiquement (spoofing non détectable rétroactivement). Migration USDC.e → USDC native change les filtres. Neg Risk vs Vanilla CTF = deux exchanges. Finalité Polygon probabiliste (attendre 64+ blocs). Trous subgraph T4 2023 / T1 2024. On reconnaît ces limites comme faux négatifs acceptés plutôt que de prétendre les contourner.

### 1.3 Posture sur l'overfitting

Le corpus de 18 cas est petit (N=18). Calibrer des seuils sur ces 18 cas puis "montrer" qu'ils performent bien sur ces mêmes 18 cas est du narrative fit, pas une validation.

**Discipline adoptée** :
- Les seuils numériques du rapport 3 (wallet_age < 30j, concentration > 0.90, etc.) sont traités comme **priors publiés**, pas comme paramètres à optimiser sur nos données. On les utilise tels quels, ou on les tune sur un sous-ensemble train et valide sur un sous-ensemble test temporel strict.
- Les 18 cas sont **splittés en train (8 cas antérieurs à juillet 2025) et test (10 cas postérieurs)**. La coupure temporelle est non-négociable — pas de cross-validation random car les features ont une structure temporelle (évolution OpSec des acteurs, concept drift).
- Aucune métrique n'est reportée sans **un intervalle de confiance** (bootstrap N=1000 sur les trades/wallets quand possible).

### 1.4 Approche duale pour les faux positifs (validation Q2)

Deux protocoles complémentaires, cf cadrage :

**(A) Base rate statistique** — on prend tous les trades > $5K sur une fenêtre de 3 mois, on applique l'heuristique, on mesure le taux de flag. On ne peut pas classifier en faux positif / vrai positif en absolu, donc on **reporte un intervalle** :
- **Borne basse de precision** = flags matchant un des 18 cas connus / total flags.
- **Borne haute de precision** = (flags matchant cas connus + flags sur wallets avec patterns similaires ET résolution profitable post-event) / total flags.
- **Faux positifs présumés** = flags qui résolvent contre le parieur ou sur marchés sans catalyseur externe identifiable.

**(B) Contrôles positifs sharps** — Domer, Aenews, Kickstand7, gopfan2, HolyMoses7, Beachboy4. Ils doivent **ne pas être flaggés** par C2 (heuristiques informed trading), et **bien se positionner** sur le leaderboard C1 (métriques skill). Si l'heuristique C2 flag Domer, c'est qu'elle overfitte sur "fresh + concentré + niche" sans distinguer de la conviction légitime informée.

---

## 2. Constitution des datasets historiques

### 2.1 Scope temporel confirmé

- **Fenêtre principale** : 1er avril 2025 → 15 avril 2026 (~12 mois glissants).
- **Fenêtre ciblée "Théo"** : 1er octobre 2024 → 15 novembre 2024, limité aux 11 wallets du cluster Chainalysis + les marchés présidentielle 2024 / popular vote / swing states (PA, MI, WI, GA, AZ, NC). Pas de full-load 2024.
- **Fenêtre ciblée UMA disputes** : 1er mars 2025 → 15 juillet 2025 pour couvrir Zelensky suit + Ukraine mineral deal (événements UMA spécifiques, pas besoin de trades).

### 2.2 Volumes attendus et budget data

Estimations basées sur rapport 4 §5.1 et rapport 2 §5.

| Dataset | Volume attendu | Source | Taille Parquet compressée |
|---|---|---|---|
| Trades `OrderFilled` sur CTFExchange + NegRiskCTFExchange (12 mois) | 30-60M events | Goldsky subgraph activity + Dune cross-check | 3-6 Go |
| Metadata marchés (12 mois + en cours) | 40-60k marchés | Gamma API | 50-150 Mo |
| Events `ProxyCreation` (12 mois + historique complet factories) | 500k-1M | Alchemy RPC direct (logs filter) | 50-100 Mo |
| Prices 1m/marché (tous marchés significatifs, 12 mois) | 500k-1M séries × ~500 points | CLOB `/prices-history` | 500 Mo-1.5 Go |
| Resolutions + disputes UMA (12 mois) | 30-50k résolutions | Alchemy RPC + UMA GraphQL | 20-50 Mo |
| Funding traces top traders (sélectif) | Variable, limité à top 500 wallets | Alchemy RPC traces ou Dune | 100-300 Mo |
| Cluster Théo ciblé | ~2500 trades/j × 30j × 11 wallets | CLOB + Goldsky + Dune | ~50 Mo |

**Budget total estimé en stockage** : 5-10 Go compressé en Parquet. Tient largement sur le disque VPS (40 Go nominal) et sur laptop local pour la phase C (on n'a pas besoin du VPS pour cette phase).

### 2.3 Gestion des gotchas techniques (critique)

Les quatre gotchas du brief sont bloquants si mal gérés. Procédures explicites :

**(G1) USDC.e vs USDC native.** On filtre les trades à partir d'août 2023 sur l'adresse USDC native (`0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359`). Pour la fenêtre Théo (oct-nov 2024), vérification manuelle : d'après rapport 2 la migration était "progressive", il reste possible que certains trades soient settled en USDC.e fin 2024. **Action** : pour Théo uniquement, on backfill sur les DEUX adresses USDC et on réconcilie. Check à faire en semaine 1 du pilote : requête Dune sur `ctfexchange_evt_orderfilled` entre oct et nov 2024, groupby address USDC — si volume USDC.e > 5% du total, on l'inclut.

**(G2) Neg Risk vs Vanilla CTF.** Deux exchanges coexistent depuis 2024. Tous les marchés multi-outcomes (présidentielle, swing states, Nobel, Next Pope) sont sur Neg Risk. On requête systématiquement les deux contrats (`polymarket_polygon.ctfexchange_evt_orderfilled` + `polymarket_polygon.negriskctfexchange_evt_orderfilled` sur Dune) et on joint via `condition_id`. La table `markets` de Gamma indique `negRisk: true/false` par marché — on le stocke en colonne pour indexation rapide.

**(G3) Trous subgraph Goldsky T4 2023 / T1 2024.** Pour la fenêtre Théo (oct-nov 2024) c'est tangent mais possiblement OK. **Action** : cross-check systématique Goldsky vs Dune sur les 11 wallets Théo, sur une semaine d'échantillon. Si écart > 2% des events, on bascule sur Dune comme source primaire pour cette fenêtre. Sinon Goldsky.

**(G4) Finalité Polygon probabiliste + reorgs.** Pour du backfill historique, les reorgs sont déjà résolus au moment où on query (fenêtre > 12 mois). Donc non-bloquant en phase C. **Action** : juste noter que pour la phase D (temps-réel), on attendra 64 blocs avant de considérer un trade comme définitif.

**Bonus (G5) — Signature types CLOB.** Rapport 0 mentionne "signature types CLOB (Type 0/1/2)". Pour du backfill, on lit juste les events `OrderFilled` qui sont post-matching, donc signatures déjà validées. Non-bloquant en phase C.

### 2.4 Pipeline de téléchargement et stockage

Architecture simple, offline, pas de VPS en phase C (tout tourne en local) :

```
Sources externes         Extract                  Transform              Load
─────────────────        ─────────                ──────────             ────
Dune (free SQL)    ──▶  Download Parquet    ──▶  polars dataframes  ──▶  DuckDB
Goldsky (GraphQL)  ──▶  Pagination GraphQL  ──▶  pandas → polars    ──▶  Parquet files
CLOB API           ──▶  httpx async batch   ──▶  direct JSON        ──▶  (partitionned by month)
Alchemy RPC        ──▶  eth_getLogs batch   ──▶  decode ABI         ──▶
UMA GraphQL        ──▶  GraphQL paginated   ──▶  JSON flatten       ──▶
```

**Stack locale** :
- Python 3.12, uv pour env
- `polars` pour manipulation (10x plus rapide que pandas sur ces volumes)
- `duckdb` pour SQL ad-hoc et joins cross-sources
- `pyarrow` pour I/O Parquet
- `httpx` + `asyncio` pour les APIs (rate-limit aware)
- Fichiers Parquet partitionnés par mois : `data/trades/year=2025/month=04/*.parquet`

**Pas de Dagster / Airflow / dbt en phase C** — overkill. Notebooks jupyter + scripts Python dans un dépôt privé local. On formalise en Dagster seulement en phase D si besoin.

### 2.5 Estimation temps de backfill

Hypothèses : laptop standard, connexion fibre, aucun coût payant activé.

| Dataset | Temps estimé | Contraintes |
|---|---|---|
| Dune SQL free tier 12 mois trades | 4-8h sur plusieurs queries | 2500 credits/mois, découpage par trimestre obligatoire |
| Goldsky trades 12 mois (all) | 8-15h en pagination | ~50 req/s, ~10M trades cible |
| Goldsky ciblé 11 wallets Théo | 30 min | Trivial |
| CLOB /prices-history top 1000 marchés | 3-6h | Rate limit ~100 req/10s, serialized batch |
| Alchemy RPC ProxyCreation events | 1-2h | eth_getLogs par chunks de 10k blocs |
| UMA resolutions + disputes 12 mois | 1-2h | GraphQL Optimistic Oracle |

**Total heures machine** : 20-35h (tourne en background pendant qu'on fait autre chose). **Total heures dev humain** : 5-8h pour orchestrer, valider, corriger.

### 2.6 Ce qu'on ne backfill PAS en phase C

Pour tenir le budget 30-40h, on renonce explicitement à :
- Les prices 1m détaillées sur *tous* les marchés — on garde top 1000 par volume.
- Le backfill complet des traces de funding pour tous les wallets — on se limite aux top 500 wallets actifs.
- Les tables `Position` du subgraph `positions-subgraph` — on reconstituera les positions à partir des trades si besoin, pas besoin de les stocker en double.
- Les events CTF `PayoutRedemption` pour tous les marchés résolus historiquement — on ne les pull que pour les marchés de la ground truth.

---

## 3. Ground truth labellée

### 3.1 Dataset `cases_forensic.csv` (18 cas, 1 ligne par wallet connu)

Schéma : une ligne par **(case_id, wallet_address)**. Un même case peut avoir N lignes (ex : Théo = 11 lignes, cluster Iran = 6 lignes).

Colonnes :

```
case_id             TEXT   # 'theo', 'iran_strikes', 'maduro', etc.
case_name           TEXT   # 'French Whale Theo cluster'
case_category       TEXT   # 'insider', 'sharp', 'manipulation', 'mixed'
case_confidence     TEXT   # 'confirmed', 'strong_indication', 'indication'
wallet_address      TEXT   # adresse proxy Polymarket, lowercase
wallet_username     TEXT   # ex 'Fredi9999'
market_primary      TEXT   # condition_id du marché principal
market_description  TEXT   # 'Presidential Election Winner 2024'
event_date          DATE   # date de résolution ou révélation
first_trade_ts      TIMESTAMP  # premier trade sur ce marché
position_usdc       NUMERIC    # taille position nette
profit_usdc         NUMERIC    # profit net final
wallet_age_days     INT        # age du wallet au moment de first_trade
concentration_pct   NUMERIC    # % du wallet sur outcome gagnant
funding_source      TEXT       # 'kraken', 'binance', 'coinbase', 'bridge', 'unknown'
shared_deposit_addr TEXT       # deposit address si identifiée (Victor heuristic)
time_to_event_hours NUMERIC    # delta timestamp first_trade vs event public
split_label         TEXT       # 'train' si event_date < 2025-07-01, 'test' sinon
source_url          TEXT       # URL principale du rapport public
notes               TEXT       # contexte spécifique
```

**Construction** : je te prépare en semaine 1 le CSV rempli manuellement à partir du rapport 3. Les adresses masquées (ex : `Michie` pour Théo, Biden pardons où 0x pas publiés) sont marquées `wallet_address = 'RECOVER_VIA_API'` et on les retrouve en interrogeant l'API Polymarket `/public-profile` (cf rapport 3 §Cas 1). Estimation : 4-6h de travail manuel pour arriver à un CSV solide.

**Répartition train/test** (split temporel stricte, coupure 1er juillet 2025) :
- **Train (8 cas)** : Théo (oct-nov 2024), Biden pardons (déc 2024 - jan 2025), Pope Francis (avril 2025), Sethi manip (sept 2024), Wash trading Columbia (transverse), Cas 18 OpenAI (déc 2025 — en limite).
- **Test (10 cas)** : Nobel Peace (oct 2025), AlphaRaccoon Google (déc 2025), Spotify Wrapped (déc 2025), Conclave Pope Leo XIV (mai 2025 — limite, à vérifier), XRP a4385 (jan 2026), Maduro (jan 2026), Super Bowl halftime (fév 2026), Iran strikes (fév 2026), Axiom ZachXBT (fév 2026), Ricosuave Israel strikes (juin 2025 / fév 2026), Taylor Swift engagement (août 2025), UMA Zelensky (juillet 2025), UMA Ukraine minerals (mars 2025).

*Note* : Pope Conclave (mai 2025) et Taylor Swift (août 2025) sont autour de la coupure — les placer dans le test set parce que leur feature principale (niche + pré-event) est plus représentative du régime ciblé. Wash trading Columbia est transverse, utilisé pour le filtre de pré-processing, pas pour C2.

### 3.2 Dataset `sharps_positive.csv` (contrôles positifs C1)

Schéma : une ligne par sharp connu.

```
sharp_id              TEXT   # 'domer', 'aenews', etc.
wallet_primary        TEXT   # ex 0x9d84ce0306f8551e02efef1680475fc0f1dc1344
wallet_aliases        TEXT   # comma-separated, autres wallets du même trader
claim_profit_usdc     NUMERIC  # profit claimé en sources publiques
claim_nb_trades       INT      # ordre de grandeur nb trades
claim_nb_markets      INT      # idem marchés
specialty             TEXT     # 'politics', 'sports', 'culture', 'generalist'
source_url            TEXT
```

Wallets à inclure (8-10 minimum) :
- Domer — `0x9d84ce0306f8551e02efef1680475fc0f1dc1344`
- Aenews — à identifier via API/leaderboards (le rapport ne donne pas l'adresse)
- Kickstand7, gopfan2, HolyMoses7, Beachboy4 — à identifier via API
- Idéalement 2-3 wallets market-maker connus (Wintermute, Jump) pour vérifier que C1 ne les remonte pas comme sharps (ils sont profitable mais pas discriminant en edge)
- 2-3 wallets "one-hit wonders" (big winners Trump 2024 mais N trades faible) — NE doivent PAS apparaître en top sharps

**Construction** : 2-3h de travail manuel, query API Polymarket par username, cross-check Dune leaderboards publics.

### 3.3 Dataset `markets_disputed.csv` (ground truth C3)

Schéma : une ligne par marché disputé ou historiquement ambigu.

```
market_id           TEXT
market_question     TEXT
resolution_outcome  TEXT   # 'Yes', 'No', 'Invalid', '50-50'
was_disputed        BOOL
dispute_count       INT    # nb disputes UMA sur ce marché
resolution_source_url TEXT
ambiguity_category  TEXT   # 'semantic', 'oracle_manipulation', 'news_timing', 'edge_case'
expected_risk_score TEXT   # 'LOW' / 'MEDIUM' / 'HIGH' / 'CRITICAL' — notre jugement a priori
notes               TEXT
```

Cas à inclure (minimum 15-20, mix dispuées et résolues-cleanly) :
- **Disputés forts** : Zelensky suit NATO Summit, Ukraine mineral deal, Bario-like edge cases...
- **Ambigus sémantiques** : TikTok ban US (plusieurs exécutions partielles), GPT-5.5 release (date vs version), Taylor Swift engagement (leak vs annonce officielle)
- **Contrôles — résolus sans dispute** : Présidentielle 2024 (trivial), Super Bowl winner (trivial), Bitcoin ATH > $X (trivial oracle)

**Construction** : 3-4h de recherche. Rapport 3 donne directement Zelensky et Ukraine minerals. Reste à gratter UMA subgraph pour la liste complète des disputes sur l'adapter Polymarket sur 12 mois.

### 3.4 Échantillon de contrôles "témoins" (pour base rate faux positifs C2)

Plus simple : on ne construit pas un CSV nominatif. On query Dune pour récupérer tous les trades > $5K sur la période de test (juillet 2025 → avril 2026) sur marchés cumul volume > $100k (sinon trop de bruit). Estimation : 50-150k trades. On applique l'heuristique C2 Niveau A, on compte les flags, on reporte le taux.

**Important** : on exclut de ce corpus les wallets déjà dans `cases_forensic.csv` (sinon le test est vicié).

---

## 4. Protocole de backtest

### 4.1 Vue d'ensemble des expériences

On a **10 expériences** ordonnées par priorité et dépendances. Chaque expérience a : question, données, méthode, résultat attendu, critère de décision, temps estimé.

| # | Expérience | Composant | Priorité | Temps estimé |
|---|---|---|---|---|
| E1 | Valider pipeline via pilote Iran OR Maduro | Tous | P0 | 10-15h |
| E2 | Backfill ground truth 18 cas + sharps + disputes | Tous | P0 | 6-8h |
| E3 | Reconstitution cluster Théo (test d'ambiguïté) | C1+C2 | P1 | 4-6h |
| E4 | Calibration heuristiques C2 Niveau A sur train set | C2 | P1 | 4-6h |
| E5 | Test C2 sur test set (precision borne basse/haute) | C2 | P1 | 3-4h |
| E6 | Test discriminant C2 sur sharps positifs | C2 | P1 | 1-2h |
| E7 | Leaderboard C1 avec FDR BH, retrouver sharps connus | C1 | P2 | 4-6h |
| E8 | Identifier N nouveaux sharps hors seed list | C1 | P2 | 2-3h |
| E9 | LLM scoring ambiguïté sur markets_disputed | C3 | P2 | 2-3h |
| E10 | Anti-honeypot via cas synthétiques | C1 | P3 | 2-3h |

**Total** : 38-56h. On déborde le budget 30-40h. **Choix explicite** : on garantit E1-E6 (= pilote + C2 complet), E7-E9 si temps (= C1 partiel + C3 rapide), E10 en optionnel à faire en phase D si budget serré.

Les sections suivantes détaillent chaque expérience.

### 4.2 Métriques d'évaluation par composant

**Pour C2 (Informed Trading)** :
- **Recall@train** : sur les 8 cas du train set, quelle fraction aurait été flaggée par l'heuristique Niveau A aux seuils `wallet_age<30 AND concentration>0.90 AND time_to_event<48h AND (niche OR shared_cex)`. Cible : **≥ 75%** (6/8).
- **Recall@test** : idem sur les 10 cas du test set. Cible : **≥ 60%** (6/10).
- **Precision bornée (borne basse, borne haute)** : cf §1.4.
- **Precision@50** : sur les 50 flags les mieux scorés, combien matchent un cas connu ou un wallet qui a clôturé profitable sur un événement à catalyseur public identifiable.
- **Courbe PR** avec seuils multiples, tracée sur le test set.
- **Calibration plot** : si on convertit le score composite en probabilité, est-il calibré (quantile 80% → fréquence observée ~80%) ? Moins critique en v1, à reporter quand même.

**Pour C1 (Sharp Money)** :
- **Recall sharps connus** : sur les 8-10 sharps dans `sharps_positive.csv`, combien apparaissent dans le top-100 du leaderboard post-FDR-BH à q=0.10.
- **Precision top-20** : parmi les top-20 wallets du leaderboard, combien sont soit (a) un sharp connu, soit (b) un wallet qu'une investigation manuelle qualifie de "plausibly skilled". Seuil cible : **≥ 60%** (12/20).
- **Nouveaux sharps identifiés** : N de wallets identifiés hors seed list qui passent le cahier des charges rapport 4 §4.3 (N ≥ 100 trades, K ≥ 20 marchés, L ≥ 3 catégories, FDR BH corrigé).
- **Discriminabilité** : BSS moyen du top-20 vs BSS moyen du 80-100ème percentile. Ratio attendu > 3x.

**Pour C3 (Resolution Risk)** :
- **Accuracy catégorielle** : sur les marchés `markets_disputed.csv`, le score LLM + rules place-t-il correctement dans `LOW / MEDIUM / HIGH / CRITICAL` vs notre label a priori ? Cible : **≥ 70%** d'accord catégoriel, **100%** pour les CRITICAL (Zelensky, Ukraine minerals doivent être CRITICAL).
- **Confusion matrix** : erreurs acceptables entre catégories adjacentes, inacceptables de sauter 2 catégories (LOW classé CRITICAL ou l'inverse).

### 4.3 Correction FDR Benjamini-Hochberg

Non-négociable sur C1 (le plus concerné). Protocole :

1. Pour chaque wallet $w$ avec $N_w \geq 100$ trades résolus, calculer $t$-stat sur edge réalisé : $t_w = \bar{\text{edge}}_w \cdot \sqrt{N_w} / \sigma(\text{edge}_w)$.
2. Convertir en $p_w$ via distribution Student-t à $N_w - 1$ ddl (one-sided, hypothèse alternative $\bar{\text{edge}} > 0$).
3. Trier $p_{(1)} \leq \ldots \leq p_{(M)}$ sur les $M$ wallets testés.
4. Trouver $i^* = \max\{i : p_{(i)} \leq (i/M) \cdot q\}$ avec $q = 0.10$.
5. Rejeter $H_0$ pour tous les wallets avec $p_w \leq p_{(i^*)}$.

**Attendu** : sur 5-10k wallets avec $N \geq 100$ trades, avec $q = 0.10$, on devrait identifier 200-1000 wallets "skillful" au sens FDR. Le leaderboard final est celui-là, trié par $t$-stat décroissant.

**Piège à éviter** : ne pas recalculer les métriques à partir de positions déjà agrégées. Le PnL par trade a besoin d'être brut pour que la variance soit correctement estimée. Reconstruire trade-par-trade depuis `OrderFilled` events.

### 4.4 Protocole de split temporel

**Règle 1** — aucune feature ne peut dépendre d'un event postérieur au trade considéré. En particulier : `resolution_outcome` n'entre que dans le label, jamais dans $X$.

**Règle 2** — la coupure train/test est 1er juillet 2025. Toutes les heuristiques sont calibrées sur train (events résolus avant cette date), évaluées sur test (events résolus après).

**Règle 3** — pour C1 leaderboard, on calcule les métriques de skill sur une fenêtre roulante de 6 mois qui se termine 1 mois avant le trade considéré (éviter leakage via clustering temporel). Le "leaderboard du 15 mars 2026" utilise les trades résolus entre le 15 sept 2025 et le 15 fév 2026.

**Règle 4** — pas de re-backfill pour "améliorer" un résultat qui ne plait pas. Si un seuil donne 50% de recall sur test, on ne retouche pas en prétendant que le seuil train était mal choisi. On documente le résultat honnêtement et on décide.

---

## 5. Expériences détaillées

### E1 — Notebook pilote : reconstitution cluster Iran strikes OU Maduro

**Priorité** : P0, en tête parce que c'est le test de la stack avant toute formalisation complète.

**Question** : notre pipeline technique (Dune free + Goldsky + DuckDB + polars en local) peut-il reconstituer un cluster connu de 3-6 wallets avec les bonnes features (wallet_age, concentration, funding source, timing) en moins de 10h de dev ?

**Choix du cas pilote** : **Maduro** plutôt qu'Iran. Rationnel :
- 3 wallets seulement vs 6 pour Iran → plus gérable pour un pilote
- Adresses complètes publiées (`0x31a56e...`, `0xa72DB1...`) et profiles Polymarket publics vérifiables
- Événement net (4 janvier 2026, capture Maduro), pas de contre-signaux
- Volume de trades gérable : ~60k USDC total investis, timing concentré sur quelques heures
- Dépôts Coinbase-linked vs cluster Iran sur Binance : plus simple à tracer côté labels d'exchanges (Coinbase hot wallets bien documentés)

**Données nécessaires** :
- Les 3 wallets + le 4ème "SBet365" dont l'adresse est à récupérer via API Polymarket
- Le marché "Maduro out by January 31, 2026?" (condition_id à récupérer via Gamma)
- Les trades de ces wallets sur ce marché entre création wallet et event
- Les events `ProxyCreation` pour établir proxy↔EOA
- Les funding traces sur Polygon (Dune `polygon.transactions` via from/to filtrage, ou Alchemy RPC)

**Méthode** :
1. Récupérer `condition_id` et metadata du marché via Gamma API.
2. Récupérer tous les `OrderFilled` events via Goldsky subgraph, filtré sur `maker IN (3 wallets) OR taker IN (3 wallets)`.
3. Calculer wallet_age = timestamp du premier OrderFilled - timestamp du ProxyCreation.
4. Calculer concentration = fraction du volume du wallet sur cet outcome vs tous ses trades historiques.
5. Tracer funding : remonter les transferts USDC entrants vers chaque wallet, identifier l'adresse source, labelliser via Arkham-style (Coinbase hot wallets publiques, dépôt Circle CCTP, etc.).
6. Identifier shared deposit address si présente (Victor 2020 heuristic).
7. Calculer time_to_event_hours = timestamp first_trade - timestamp public news (4 jan 2026 capture Maduro).
8. Produire un rapport jupyter avec un tableau récap par wallet et un verdict : "aurait été flaggé par heuristique Niveau A ?".

**Résultat attendu** : les 3 wallets sortent avec wallet_age < 30j (rapport 3 dit "fresh"), concentration 100%, time_to_event < 48h (dernière bet 5h avant explosions Caracas). Le 4ème (SBet365) pareil. L'heuristique devrait flagger les 3/3 connus et idéalement trouver un 4ème non publié.

**Critère de décision** :
- **Succès** : on reconstitue les features en local, les features matchent qualitativement les valeurs du rapport 3, le code tourne en < 10 min une fois les données loadées → on valide le pipeline et on poursuit.
- **Échec partiel** : on reconstitue les features mais avec des écarts (ex : wallet_age off de plusieurs jours à cause d'un proxy↔EOA manquant) → on documente, on décide cas par cas si c'est réparable.
- **Échec bloquant** : les données ne sont pas accessibles sur free tier (rate limit hard, tables Dune qui manquent, subgraph qui timeout) → on ajuste le plan : soit upgrade Dune Plus immédiatement, soit pivot sur Allium/Flipside free.

**Temps estimé** : 10-15h (semaine 2 du plan).

**Deliverable** : notebook `pilot_maduro.ipynb` en annexe du plan, commit sur repo privé.

---

### E2 — Backfill ground truth + wallets mystère

**Priorité** : P0, prérequis à toute autre expérience.

**Question** : on a un corpus structuré de 18 cas, 8-10 sharps, 15-20 marchés disputés, avec toutes les adresses nécessaires et le split train/test affecté ?

**Méthode** :
1. Rédiger les 3 CSV du §3 à la main, en suivant le rapport 3 comme source primaire.
2. Pour les wallets "à récupérer via API" (Michie, Biden pardons, Magamyman, SBet365, dirtycup, AlphaRaccoon 0xafEe...) : query `https://polymarket.com/@<username>` ou `/public-profile` pour obtenir l'adresse 0x complète.
3. Pour les sharps sans wallet connu (Aenews, Kickstand7, etc.) : idem via API ou Dune leaderboard `@rchen8/polymarket-leaderboard`.
4. Pour les marchés disputés : query UMA subgraph pour la liste des `DisputePrice` events sur l'adapter Polymarket sur 12 mois, enrichir avec Gamma pour les questions.
5. Verification : pour chaque wallet, vérifier que l'adresse donne bien une page Polymarket valide et que le track record matche grossièrement le rapport 3.

**Résultat attendu** : 3 fichiers CSV propres, ~60 lignes totales (18 cases × ~3 wallets/case avg + 10 sharps + 20 markets), validés à la main.

**Critère de décision** : les 3 CSV existent, sont remplis, et contiennent au moins **70% des wallets clés** (on accepte que Michie/Biden pardons/Magamyman restent mystères si l'API ne les rend pas).

**Temps estimé** : 6-8h.

**Livrables** : `cases_forensic.csv`, `sharps_positive.csv`, `markets_disputed.csv` commités dans le repo.

---

### E3 — Reconstitution cluster Théo (test d'ambiguïté)

**Priorité** : P1.

**Question** : les heuristiques Niveau A du rapport 3 flagguent-elles Théo comme "informed" ? Si oui, ça veut dire que le C2 en v1 va produire des alertes sur des sharps légitimes comme Théo. C'est le test le plus important de l'ambiguïté fondamentale.

**Données nécessaires** : cluster Théo 11 wallets + marchés Présidentielle 2024 + swing states sur oct-nov 2024. Cf §2.1 backfill ciblé.

**Méthode** :
1. Pour chaque wallet du cluster Théo, calculer les features C2 Niveau A.
2. Appliquer l'heuristique : `wallet_age<30 AND concentration>0.90 AND time_to_event<48h AND (niche OR shared_cex)`.
3. Compter : combien des 11 wallets Théo sont flaggés ?
4. Analyse qualitative : qu'est-ce qui fait que Théo passerait / ne passerait pas le filtre ?

**Résultat attendu** : probablement, **plusieurs wallets Théo seront flaggés** par l'heuristique naïve (fresh, concentrés sur Trump, ont shared Kraken deposit). C'est le comportement *attendu* — Théo et un insider pur sont indiscernables sur les features on-chain.

**Critère de décision** :
- Si 0 wallet Théo flaggé → l'heuristique est trop stricte (elle va manquer des cas similaires à Théo en régime insider). À loosen.
- Si 1-5 wallets Théo flaggés → comportement attendu. Dans ce cas, **C2 doit être complété par C3 (Resolution Risk) et par l'enrichissement manuel** (la catégorie "election mainstream" devrait ramener le risk_score, le niche_market_flag ne devrait pas trigger). On documente que "sharp vs insider = indiscernable par C2 seul", en assumant que le triage final vient de l'opérateur humain.
- Si 11/11 wallets flaggés → même chose, mais encore plus fort, l'ambiguïté est totale. On accepte et on document.

**C'est le test méthodologique le plus important de la phase C** parce qu'il force une question honnête : est-ce qu'on veut un C2 qui flag tout (recall high, precision low, beaucoup de faux positifs à trier par l'humain) ou un C2 qui cherche les signatures les plus rares (precision high, recall low, mais manque Théo-like quand ils arrivent) ?

**Temps estimé** : 4-6h.

---

### E4 — Calibration heuristiques C2 sur train set

**Priorité** : P1.

**Question** : les seuils du rapport 3 (wallet_age<30, concentration>0.90, etc.) sont-ils bien calibrés sur nos cas, ou faut-il les ajuster ?

**Méthode** :
1. Sur les 8 cas du train set, pour chaque wallet, calculer les 8 features C2 du §2.C.1 de l'architecture.
2. Tracer les distributions de chaque feature sur wallets-cas vs échantillon témoin. Identifier les seuils où on maximise le Youden's J = TPR - FPR.
3. Comparer seuils obtenus vs seuils publiés. Si écart > 20% sur un seuil clé, documenter et décider : respecter le prior publié (conservateur méthodologiquement) ou ajuster.
4. Tester 3 configurations : seuils publiés rapport 3, seuils Youden optimaux, seuils "conservateurs" (Youden + 1 cran plus strict).

**Résultat attendu** : les seuils publiés sont dans le bon ordre de grandeur, avec écarts de calibration de l'ordre de 10-30%. Probablement la bonne config est quelque part entre publié et Youden.

**Critère de décision** : pas de décision unique, on documente les 3 configs et on applique E5 sur les 3 pour voir laquelle performe mieux sur test.

**Temps estimé** : 4-6h.

**Note** : on ne fait PAS de grid search exhaustif sur les 8 features, c'est du overfit garanti sur N=8-16 observations positives.

---

### E5 — Test C2 sur test set : precision bornée

**Priorité** : P1.

**Question** : le C2 calibré sur train set (E4) retrouve-t-il les cas du test set, et avec quelle precision estimée ?

**Méthode** :
1. Appliquer les 3 configurations d'heuristiques (E4) sur **tous les trades > $5K** de la fenêtre test (juillet 2025 → avril 2026), tous marchés > $100k cumul volume.
2. Pour chaque flag, annoter : matche-t-il un cas du `cases_forensic.csv` test set ?
3. Pour les flags non-matchés, annotation manuelle légère top-50 : est-ce un wallet qui a résolu profitable sur un événement à catalyseur public ? (Recherche rapide sur X, Reuters, GDELT).
4. Calculer recall (cas retrouvés / cas test set), precision borne basse, precision borne haute.

**Résultat attendu** : recall 60-80% sur test set, precision borne basse 5-15% (très conservatrice), precision borne haute 20-40%.

**Critère de décision** :
- **Valide pour phase D** : recall ≥ 60%, precision borne haute ≥ 20%, pas de flags Domer-like parmi top 20 flags.
- **Ajuster** : recall < 60% → il faut loosen l'heuristique ou ajouter des features (e.g. trade size absolu, order_book_imbalance). Precision borne haute < 15% → trop bruyant, il faut strict-er.
- **Abandonner C2 v1** : recall < 30% ou precision borne haute < 5%. On revient aux rules board.

**Temps estimé** : 3-4h.

---

### E6 — Test discriminant C2 sur sharps positifs

**Priorité** : P1.

**Question** : les sharps connus (Domer, Aenews, etc.) sont-ils flaggés par C2 ? Idéalement non, ou alors avec un score bien inférieur aux insiders.

**Méthode** :
1. Pour chaque sharp de `sharps_positive.csv`, récupérer leurs trades > $5K sur la fenêtre test.
2. Appliquer l'heuristique C2. Compter combien de leurs trades seraient flaggés.
3. Comparer le score composite C2 moyen des sharps vs celui des insiders du test set.

**Résultat attendu** :
- Domer : wallet_age > 1 an (créé en 2022), diversifié sur 5000+ marchés, concentration faible → devrait avoir peu ou pas de flags.
- Aenews, Kickstand7 : idem.
- Beachboy4 : potentiellement flaggé sur son "6.12M profit en un jour sur sports" si c'était sur marchés thin — à vérifier. Cas intéressant.

**Critère de décision** :
- **Bon** : moins de 5% des trades des sharps sont flaggés, score composite sharps <<< insiders.
- **À retoucher** : > 20% des trades sharps flaggés → ajouter au filtre C2 un critère `wallet_age_days > 180 AND distinct_markets_traded > 50 → ne pas flagger` (sauf cumul de 4+ autres signaux forts).
- **Problème structurel** : > 50% des trades sharps flaggés → l'heuristique est indiscriminante, revoir en profondeur.

**Temps estimé** : 1-2h.

---

### E7 — Leaderboard C1 avec FDR BH

**Priorité** : P2.

**Question** : un leaderboard BSS/edge/CLV post-FDR-BH identifie-t-il correctement les sharps connus dans le top ?

**Méthode** :
1. Sur la fenêtre train (avril 2025 - juin 2025, 3 mois — trop court idéalement, en pratique il faut 6-12 mois pour avoir du N>=100 par wallet, donc on étend la "fenêtre train" à avril 2025 - mars 2026 en acceptant que le test du C1 chevauche la fenêtre test du C2 — ce n'est pas gênant parce que les composants sont indépendants méthodologiquement) : calculer pour chaque wallet actif les métriques du rapport 4 §4.2.
2. Filtrer : $N \geq 100$ trades résolus, $K \geq 20$ marchés distincts, $L \geq 3$ catégories.
3. Appliquer FDR BH à $q = 0.10$ sur les $t$-stats d'edge réalisé.
4. Trier le sous-ensemble rejeté par $t$-stat décroissant.
5. Vérifier : les sharps de `sharps_positive.csv` apparaissent-ils dans le top 100 ?

**Résultat attendu** : ~500-2000 wallets passent le FDR. Domer dans le top 20. Aenews/Kickstand7 dans le top 100.

**Critère de décision** :
- **Valide** : ≥ 6/10 sharps connus dans le top 100, top 20 ne contient pas de wallets "one-hit wonder" évidents.
- **Ajuster** : ≤ 3/10 sharps connus → augmenter les seuils minimums ou revoir la métrique de ranking (pondérer edge/CLV/BSS différemment).

**Pitfall attendu** : Beachboy4 avec ses gros profits sport mais faible diversification catégorielle risque de ne pas passer le $L \geq 3$. C'est le comportement attendu du filtre — mais c'est un rappel que "sharp high-profile" ≠ "sharp généraliste tracké".

**Temps estimé** : 4-6h.

---

### E8 — Identifier N nouveaux sharps hors seed list

**Priorité** : P2.

**Question** : le leaderboard C1 fait-il émerger des wallets intéressants qu'on aurait raté autrement ?

**Méthode** :
1. Prendre le top 50 du leaderboard E7 hors wallets déjà dans `sharps_positive.csv`.
2. Pour chaque wallet, investigation manuelle rapide (~5 min/wallet) : visite page Polymarket, check pattern trades, recherche username sur X.
3. Classifier : "plausibly skilled", "market maker / arbitrageur", "chanceux / one-hit", "douteux / potentiel honeypot".

**Résultat attendu** : 10-20 wallets "plausibly skilled" jamais identifiés publiquement = ça confirme que C1 apporte de la valeur au-delà de la simple seed list.

**Critère de décision** : ≥ 5 wallets plausibly skilled émergent → Tier B se constituera naturellement en phase D.

**Temps estimé** : 2-3h.

---

### E9 — LLM scoring ambiguïté sur markets_disputed

**Priorité** : P2.

**Question** : Claude Haiku avec le prompt du §2.D.1 score-t-il correctement les marchés historiquement disputés ?

**Méthode** :
1. Pour chaque marché de `markets_disputed.csv`, appeler Haiku avec le prompt structuré (question + description + resolution source + outcomes).
2. Combiner avec rules dynamiques (dispute_rate_category, oracle_source_reliability).
3. Calculer `risk_score` composite et catégorie.
4. Comparer avec `expected_risk_score`.

**Résultat attendu** : 70-85% accord catégoriel. 100% des disputés Zelensky/Ukraine minerals en HIGH ou CRITICAL.

**Critère de décision** :
- **Valide** : ≥ 70% accord, 0 erreur critique (LOW classé CRITICAL ou inverse).
- **Ajuster prompt** : 50-70% accord → itérer le prompt Haiku, ajouter des examples, expliciter les red flags dans le few-shot.
- **Revoir architecture** : < 50% accord → le mix LLM/rules 50/30/20 est mal calibré, revoir les pondérations.

**Coût estimé Haiku** : 20 markets × 700 tokens (input+output) × pricing Haiku ≈ $0.02. Négligeable.

**Temps estimé** : 2-3h (prompt iteration inclus).

---

### E10 — Anti-honeypot via cas synthétiques

**Priorité** : P3 (optionnelle si budget temps serré).

**Question** : le filtre anti-honeypot §2.B.4 détecte-t-il un pattern honeypot *plausible* ? Puisqu'on n'a pas de cas documenté, on génère des cas synthétiques.

**Méthode** :
1. Définir 3 personas honeypot synthétiques :
   - **Persona A (jackpot hunter)** : 80% trades petits (<$500) gagnants sur longshots à p<0.15, 20% trades gros (>$5K) sur marchés illiquides avec funding CEX partagé avec 3 autres comptes.
   - **Persona B (track record farmer)** : 200 trades gagnants constants sur sports underdogs <$300, puis 1 grosse position contre une liquidité thin pendant qu'un autre wallet lié prend la position inverse.
   - **Persona C (wash-trading sybil)** : 2 wallets qui se matchent self-trade réciproquement sur 20 marchés thin pour générer un faux volume/edge.
2. Simuler les features correspondantes sur un wallet fictif (ou injecter directement dans DuckDB des rows synthétiques).
3. Appliquer le scoring anti-honeypot §2.B.4. Chaque persona devrait obtenir `honeypot_score > 0.4`.
4. Vérifier que les sharps connus (Domer etc.) obtiennent `honeypot_score < 0.2`.

**Résultat attendu** : les 3 personas flaggés (> 0.4), Domer et Aenews non flaggés (< 0.2).

**Critère de décision** : les 3 personas flaggés + 0 faux positif parmi 10 sharps → OK. Si < 3 personas flaggés → le filtre est sous-dimensionné.

**Temps estimé** : 2-3h.

**Pourquoi P3** : on n'a pas de ground truth réelle, donc la valeur épistémique du test est limitée. C'est plus un sanity check qu'un backtest. En phase D, on monitore en continu les `honeypot_score` des wallets Tier A pour détecter des signes qui émergeraient in-vivo.

---

## 6. Plan de calibration des seuils

### 6.1 Philosophie générale

**Pas de grid search exhaustif** — c'est du overfit garanti sur un petit échantillon. On adopte une approche bayésienne light : les seuils publiés rapport 3/4 sont des **priors informés**, on les laisse sauf si l'évidence sur train set est forte (Youden's J écart > 25%) et stable (robustesse sur bootstrap).

### 6.2 Seuils par composant

**C2 Informed Trading** — seuils à valider/ajuster :

| Seuil | Valeur publiée | Méthode de calibration |
|---|---|---|
| wallet_age_days | < 30 (flag), < 7 (critique) | E4 : distribution sur train set, Youden's J |
| concentration_ratio | > 0.70 (flag), > 0.90 (critique) | E4 : idem |
| trade_size_USDC | > $5K (flag), > $25K (critique) | E4 : MAD cross-market |
| time_to_event_hours | < 48 (flag), < 4 (critique) | E4 : extraire distribution event_date - first_trade_ts sur train |
| num_cluster_wallets | > 2 (flag), > 5 (critique) | Par construction, pas calibré |
| niche_market_volume | < $50k cumul | E4 : vérifier que le seuil 50k est dans la distribution réelle |

**C1 Sharp Money** — seuils déjà dans l'architecture §2.B.2 :

- N ≥ 100 trades : rapport 4 §4.3 règle empirique, on garde.
- K ≥ 20 marchés distincts, L ≥ 3 catégories, HHI < 0.2 : idem.
- FDR BH à $q = 0.10$ : standard, on garde.
- Seuils edge / CLV / BSS (3 cents, 2 cents, 0.05) : **on les valide sur E7/E8** en vérifiant que les sharps connus passent.

**C3 Resolution Risk** — seuils d'intérêt :

- Pondération LLM 50% / rules 30% / oracle 20% : validation qualitative E9, ajustement possible.
- Catégories LOW/MED/HIGH/CRIT aux bornes 0.25/0.50/0.75 : on teste sur E9, ajuste si 2-3 cas clés atterrissent systématiquement dans la mauvaise catégorie.

### 6.3 Discipline anti-overfitting

- Chaque seuil qu'on propose de modifier vs publié doit avoir une justification écrite : "sur le train set, la distribution empirique de X montre que le mode est à Y, donc seuil Z" — pas "ça marche mieux à Z".
- Aucun seuil n'est re-tuné sur le test set. Si les résultats test sont médiocres, on documente et on passe.
- On rapporte les résultats des 3 configurations (publié / Youden / conservateur) sur test set sans cacher les moins bons.

---

## 7. Decision gates

### 7.1 Gate 1 (fin semaine 1) — pilote validé ?

**Condition bloquante pour continuer** : E1 pilote Maduro doit aboutir à une reconstitution des features proche du rapport 3, en < 15h. Si non :

- **Échec soft** : écarts de valeurs acceptables (wallet_age ±3j, concentration ±5%), reste utilisable → on poursuit en documentant.
- **Échec bloquant sur data access** : Dune free rate-limited, subgraph timeout répété → décision : upgrade Dune Plus (49$/mois) si le reste du budget le permet, ou switch Flipside/Allium.
- **Échec bloquant sur compute** : DuckDB+polars en local rame sur 10M trades → décision : migrer sur MotherDuck ($25/mo) ou ClickHouse Cloud Dev ($1/mo + egress). Remonter en contrainte.

### 7.2 Gate 2 (fin semaine 2) — passer en phase D ?

**Critères cumulés** :
- ✅ Pipeline validé (Gate 1) ✔
- ✅ 3 CSV de ground truth complets et cohérents ✔
- ✅ C2 recall train ≥ 75%, recall test ≥ 60%, precision borne haute ≥ 20% ✔
- ✅ C2 ne flag pas les sharps positifs (E6 passé) ✔
- ✅ C1 leaderboard avec FDR BH identifie ≥ 6/10 sharps connus dans top 100 ✔
- ✅ C3 accord catégoriel ≥ 70%, 100% sur CRITICAL ✔

Si **6/6 validés** → phase D confirmée, on code.

Si **4-5/6 validés** → phase D conditionnelle, on identifie le composant faible, on ajuste les heuristiques, on re-évalue rapidement avant de coder. On ne repart pas en phase C complète.

Si **≤ 3/6 validés** → on fait une semaine supplémentaire d'ajustement avant d'engager 4-6 semaines de dev. Plutôt perdre 1 semaine que 6.

### 7.3 Scénarios de pivot / abandon partiel

- **C2 irrécupérable** (recall test < 30%) → v1 sans C2. On code C1 + C3, on réfléchit à C2 v2 avec ML supervisé après avoir accumulé 3-6 mois de trades labellisés en phase D.
- **C1 leaderboard bruyant** (< 3/10 sharps dans top 100) → v1 avec seed list manuelle uniquement (Tier A). On remet à plus tard la détection automatique de sharps Tier B/C.
- **C3 LLM décevant** (accord < 50%) → on part avec rules-only + flag manuel par l'opérateur. Le LLM est ajouté plus tard quand on aura une meilleure vue du prompt optimal.
- **Aucun composant ne passe** (improbable) → on ne code pas le bot. On reste sur le constat honnête que les heuristiques publiques ne suffisent pas et on étudie d'autres pistes (partenariat Bubblemaps, Nansen, abandon du projet, pivot vers un outil plus modeste).

---

## 8. Planning semaine par semaine

### Semaine 1 (15-20h) — constitution et plan

**Objectif** : ground truth complète, plan écrit définitif, choix stack pilote.

| Jour | Tâche | Temps |
|---|---|---|
| 1-2 | E2 — remplir `cases_forensic.csv` (18 cas, adresses à récupérer via API) | 4-6h |
| 2-3 | E2 — remplir `sharps_positive.csv` + `markets_disputed.csv` | 4h |
| 3-4 | Setup stack locale : uv env, scripts Dune/Goldsky/Alchemy, DuckDB + polars smoke test | 3-4h |
| 4-5 | Relecture du plan, ajustements post-constitution ground truth (ex : si un CSV est vide sur 5 cas, ajuster E5) | 2-3h |
| 5 | Commit final plan + CSV + setup, prep semaine 2 | 1h |

**Livrable fin semaine 1** : repo privé avec `C_plan_recherche_backtest.md` + `data/cases_forensic.csv` + `data/sharps_positive.csv` + `data/markets_disputed.csv` + `src/` contenant les scripts d'ingestion de base.

### Semaine 2 (15-20h) — pilote et raffinement

**Objectif** : pilote Maduro validé, raffinement du plan selon ce qui a marché.

| Jour | Tâche | Temps |
|---|---|---|
| 1-3 | E1 — notebook pilote Maduro, reconstitution des 3+1 wallets, features, verdict heuristique | 10-15h |
| 3 | Gate 1 : pilote validé ou pivot ? | (review) |
| 4 | E3 — reconstitution cluster Théo (si temps) | 4-6h OU reporté phase D |
| 5 | Mise à jour `C_plan_recherche_backtest.md` avec leçons apprises + gate 2 preview si assez d'éléments | 1-2h |

**Livrable fin semaine 2** : notebook `pilot_maduro.ipynb` + plan v1.1 mis à jour + décision gate 1 documentée.

### Semaines 3-4 (hors budget initial, optionnelles)

Si Gate 2 nécessite des expériences supplémentaires avant phase D, on y alloue les semaines 3-4 sur E4-E9. Mais **ce n'est pas le scénario nominal** : l'idée est que le pilote + la ground truth + le plan formel suffisent à prendre la décision de phase D, l'exécution des backtests E4-E9 se fait en phase D début pendant qu'on code les ingesters.

**Variante si on veut garder le cadrage strict "pas de dev avant validation complète"** :
- Semaine 3 (~15h) : E3, E4, E6, E7
- Semaine 4 (~15h) : E5, E8, E9, E10

À décider à la fin de la semaine 2 en fonction du résultat pilote et du niveau de conviction obtenu.

---

## 9. Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Dune free tier bloque le backfill 12 mois | Moyenne | Élevé | Plan B Flipside free. Plan C : upgrade Dune Plus (49$/mo, budget disponible ~1 mois juste pour la phase C) |
| Goldsky subgraph trou fenêtre Théo | Moyenne | Moyen | Cross-check Dune sur échantillon. Si trous : Dune seul pour Théo. |
| Adresses wallets cas ground truth pas récupérables via API | Moyenne | Moyen | On accepte 20-30% de wallets "masqués", on travaille sur le reste. Biden pardons probablement perdu en tant que cas, par exemple. |
| Overfitting sur N=18 cas | Élevée | Élevé | Split temporel strict train/test, pas de grid search, seuils publiés comme priors, documentation honnête des limites. |
| C2 flag Théo et sharps → discriminabilité faible | Haute | Moyen | **Attendu et documenté**. C2 + C3 + humain en loop = architecture qui assume l'ambiguïté. Pas un bug, une feature. |
| Pilote Maduro échoue sur accès données | Faible | Élevé | Gate 1 explicite, upgrade Dune Plus au pire, le budget absorbe ~2 mois de Dune Plus sans douleur |
| Anti-honeypot non testable sérieusement | Certaine | Faible | Cas synthétiques (E10) en P3, monitoring in-vivo en phase D |
| Concept drift : un cas 2026 change sa signature post-exposure | Certaine | Faible | Hors scope phase C (on est offline historique). Point à traiter en phase D ops. |

---

## 10. Annexe — ce qui est explicitement hors scope phase C

Pour cadrer les attentes et éviter la dérive :

- **Pas de code du bot**. Les ingesters en phase D. En phase C uniquement scripts jetables d'ingestion ponctuelle + notebooks.
- **Pas de Dagster, Airflow, dbt**. Le setup orchestré vient en phase D.
- **Pas de modèle ML supervisé** (XGBoost, Isolation Forest formel). Rules-based et stats descriptives suffisent pour valider les heuristiques.
- **Pas de TGN / contrastive SSL / GNN**. Rapport 4 §9.3 les classe Tier 3, réservés à une équipe / un budget plus grand.
- **Pas de PIN / VPIN**. Rapport 4 §9.4 les déconseille sur Polymarket.
- **Pas de backtest d'exécution** (slippage, timing orders manuels). C'est en phase D début.
- **Pas de dashboard Streamlit**. Notebooks jupyter pour tout en phase C.
- **Pas de scoring real-time**. Offline pur.
- **Pas d'anti-honeypot in-vivo**. E10 synthétique uniquement, monitoring réel en phase D.
- **Pas de backfill 2022-2024 complet**. 12 mois + cibles Théo seulement.

---

## 11. Références

Les décisions méthodologiques ci-dessus s'appuient sur :

- `0_project_brief.md` — cadrage global
- `A_architecture_technique.md` — architecture technique cible, notamment §2.B (C1), §2.C (C2), §2.D (C3)
- `3_-_informed_trading_and_sharp_money.md` — 18 cas forensiques, §Partie IV patterns on-chain, §Synthèse transversale seuils empiriques
- `4_wallet_clustering.md` — méthodologie FDR BH §4.3, métriques skill §4.2, matrice priorisation §9, trois vérités inconfortables §9.5
- `2_polymarket_stack_technique.md` — stack data APIs CLOB/Gamma/Goldsky/Dune, §9 gotchas techniques

**Références académiques et externes clés** :
- Bailey & López de Prado (2012, 2014) — PSR, DSR
- Benjamini & Hochberg (1995) — FDR
- Victor (FC 2020, LNCS 12059) — deposit-address-reuse heuristic
- Mitts & Ofir (SSRN 2026) — $143M profits anomaux, 210k wallet-market pairs
- Sirolly et al. (Columbia 2025) — wash trading Polymarket
- Chainalysis thread 7 nov 2024 — méthodologie cluster Théo

---

*Fin du document. Version 1.0 à lire en parallèle de `A_architecture_technique.md`. Révisions mineures en fin semaine 2 après notebook pilote (attendre v1.1). Passage phase D conditionné au Gate 2 de §7.2.*
