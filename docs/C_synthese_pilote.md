# Synthèse du pilote Iran strikes — Phase C

*Notebook : `notebooks/01_pilote_iran_cluster.ipynb`. Exécuté les 18-19 avril 2026.*

---

## 1. Contexte et méthodologie

**Cas pilote** : marché "US strikes Iran by February 28, 2026?" ($90M volume, résolu YES le 28 fév 2026 09:31 UTC, vanilla CTF Exchange). Ground truth : 7 wallets documentés dans le rapport 3 (6 cluster Bubblemaps + Magamyman).

**Objectif** : valider que (a) la stack technique tient la route pour l'ingestion et l'analyse, et (b) les heuristiques Niveau A du rapport 3 détectent effectivement les wallets suspects sans les connaître à l'avance.

**Protocole** :
1. Ingérer les trades des 7 wallets GT via Data API publique (pas CLOB — devenu auth-only)
2. Calculer 4 features Niveau A par wallet : `wallet_age_days`, `concentration_pct`, `max_size_usd`, `time_to_event_hours`
3. Appliquer les seuils du rapport 3 sans modification (age < 30j, concentration > 90%, max_size > $5K, time < 48h)
4. Flagger les wallets avec score ≥ 3/4
5. Élargir aux holders non-GT du marché pour mesurer le base rate de faux positifs

Le 5e critère du rapport 3 (shared CEX deposit address / funding source) n'a **pas** été évalué — il nécessite le traçage des transferts USDC entrants via RPC Polygon, hors scope du pilote.

---

## 2. Résultats techniques

### Stack validée

| Composant | Statut | Notes |
|-----------|--------|-------|
| Data API (`data-api.polymarket.com`) | **OK** | `/trades?user=`, `/holders?market=` fonctionnent sans auth. Rate limit ~1 req/s safe |
| Gamma API (`gamma-api.polymarket.com`) | **OK** | `/markets/{id}` retourne metadata complète. Recherche par slug peu fiable |
| CLOB API (`clob.polymarket.com`) | **KO pour /trades** | Endpoint `/trades` renvoie 401 sans auth. `/prices-history` renvoie vide sur marchés résolus. `/book` et `/midpoint` OK en read-only |
| polars + DuckDB + Parquet | **OK** | Aucun problème de perf sur ~200 trades. polars lazy scan suffisant |
| Coût total | **$0** | Aucune API payante utilisée |

### Pivot principal

La CLOB API `/trades` étant auth-only, l'approche "pull tous les trades du marché puis filtre" est impossible sans clé API. On a pivoté sur une approche **wallet-first** via Data API : query chaque wallet individuellement, filtre côté client sur le `conditionId`. C'est suffisant pour le pilote et pour C2 (où on part des wallets suspects), mais **insuffisant pour C1** (leaderboard) qui nécessite une vue marché-first. Pour C1, Dune API ou Goldsky subgraph seront nécessaires.

---

## 3. Résultats méthodologiques

### 3.1 Recall : 5/7 = 71%

Sur les 7 wallets ground truth, **5 sont flaggés** (score ≥ 3/4) par les heuristiques Niveau A.

**Les 2 ratés** :

| Wallet | Raison du raté | Type |
|--------|---------------|------|
| `0xa4eb5222...` (nothingeverhappens911) | `concentration_pct` sous le seuil 90% — ce wallet a tradé sur d'autres marchés Iran (ceasefire, regime fall). Membre **périphérique** du cluster, pas concentré sur le seul marché 28 fév | Faux négatif structurel : membre secondaire d'un cluster |
| `0x4dfd481c...` (Magamyman) | `wallet_age_days` > 30 — actif depuis octobre 2024 (4 mois avant l'event). Le rapport 3 documente explicitement ce cas comme du **camouflage par activité organique** | Faux négatif attendu : adversaire sophistiqué |

Ces deux ratés sont **informatifs, pas problématiques** : ils correspondent exactement aux limites prédites par le rapport 3. Les heuristiques Niveau A ne sont pas conçues pour attraper les membres périphériques ou les insiders qui construisent un historique crédible. C'est le rôle du clustering (shared deposit, funding timing) en phase D.

### 3.2 Precision : 70%

Sur les wallets effectivement flaggés (score ≥ 3/4), on a **10 flags** : 5 GT + 5 non-GT.

**Investigation manuelle des 5 flags non-GT** (`data/ground_truth/iran_base_rate_investigation.csv`) :

| Wallet | Classification | Justification clé |
|--------|---------------|-------------------|
| `0x5307e5...` | **Faux positif — contrariant perdant** | Acheté NO massivement sur "US strikes Feb 28/March 1/March 2". Pertes totales ~$160K. Signature technique identique aux insiders mais **direction inverse**. |
| `0x9c5e99...` | **Faux positif — contrariant perdant** | Acheté NO à $90K sur Feb 28 → -100%. Même profil que 0x5307. |
| `0x01a0aa...` | Indéterminé | 240 trades, 54 marchés. Concentré Iran mais diversifié. Sharp géopolitique possible |
| `0x5060b4...` | Faux positif — sharp géopolitique | 996 trades, 108 marchés, encore actif avril 2026. Diversifié : Iran + tarifs + Chine |
| `0xca765a...` | Faux positif — sharp multi-thématique | 164 trades, 42 marchés. Élections Thaïlande/Hongrie/Vietnam + tennis + Iran |

**Les 5 flags non-GT sont tous des faux positifs.** Aucun informé non-documenté retrouvé. En particulier, les deux wallets initialement classés "vrai informé probable" (`0x5307e5...` et `0x9c5e99...`) ont en réalité parié **contre** les frappes et perdu massivement. L'investigation des positions réelles sur Polymarket a invalidé la classification initiale basée sur les seules features on-chain.

**Precision calculée** :

| Mesure | Formule | Valeur |
|--------|---------|--------|
| Precision | 5 GT flaggés / 10 flags | **50%** |
| F1 | 2 × 0.50 × 0.71 / (0.50 + 0.71) | **59%** |

*Note : la precision de 50% (et non 70% comme initialement reporté) reflète le fait que seuls 5 des 10 flags correspondent à des wallets GT confirmés. Les 7 wallets GT incluent 2 non-flaggés, et seuls 5 des 7 GT passent le seuil ≥ 3/4. La precision "7 GT / 10 flags = 70%" supposait que les 7 GT étaient tous flaggés, ce qui est faux — 2 sont ratés. Precision = vrais positifs / total positifs = 5/10 = 50%.*

**Correction du 19 avril** : la version initiale de cette synthèse reportait une precision borne haute de 90% en classant `0x5307e5...` et `0x9c5e99...` comme "vrais informés probables". L'investigation manuelle des positions Polymarket a révélé que ces deux wallets ont parié dans la **mauvaise direction** (NO au lieu de YES) et perdu ~$260K au total. C'est une erreur méthodologique instructive : **les features on-chain (fraîcheur, concentration, sizing, timing) ne capturent pas la direction du trade ni l'outcome**. Un contrariant convaincu et un insider informé produisent la même signature heuristique.

### 3.3 Verdict par critère du plan C

| Critère plan C (§1.3) | Seuil | Résultat | Statut |
|------------------------|-------|----------|--------|
| G1 — Pipeline validé | Features matchent rapport 3 | 7/7 wallets retrouvés, features cohérentes | **PASS** |
| G4 — C2 recall ≥ 60% | ≥ 60% | 71% (5/7) | **PASS** |
| G5 — C2 ne flag pas les sharps | < 5% trades flaggés | Non testé sur ce pilote (sharps pas sur ce marché) | Reporté E9 |

---

## 4. Surprises et apprentissages

### Ce qui a bien marché

**Les heuristiques Niveau A isolent un pool restreint.** Sur un marché à $90M de volume avec des dizaines de holders, le filtre (fresh + concentré + gros sizing + pré-event) isole 10 wallets. C'est un taux de flag de ~30% des holders significatifs — suffisamment sélectif pour être opérable par un humain en investigation manuelle.

**Le recall de 71% sur les insiders documentés est solide.** Les 5 wallets GT flaggés correspondent aux membres les plus visibles du cluster (gros sizing, fresh wallets, concentration extrême). Les 2 ratés sont des cas documentés comme difficiles (périphérique, camouflé).

### Ce qui pose problème

**Faille critique : les heuristiques ne distinguent pas la direction du trade.** C'est l'apprentissage principal du pilote. Les wallets `0x5307e5...` et `0x9c5e99...` ont exactement la même signature on-chain que les insiders GT (fresh, concentré, gros sizing, pré-event) mais ont parié **NO** — contre les frappes — et perdu respectivement ~$160K et ~$100K+. Les features Niveau A détectent "high conviction pre-event bets" indépendamment du fait que le parieur ait raison ou tort. Un contrariant convaincu et un insider informé sont **indiscernables** sur les 4 features actuelles.

**Biais de ground truth : survivorship bias sur les cas documentés.** Les 18 cas forensiques du rapport 3 sont exclusivement des insiders **gagnants** — identifiés précisément parce qu'ils ont gagné gros et attiré l'attention. Les contrariants perdants, par construction, ne font pas l'objet d'articles Bubblemaps/CoinDesk. Le ground truth est biaisé vers les insiders qui ont eu raison. Un système entraîné uniquement sur ces cas héritera de ce biais.

**Confusion sharp géopolitique vs insider one-shot.** Les wallets `0x5060b4...` (996 trades, 108 marchés) et `0xca765a...` (164 trades, 42 marchés) passent les seuils parce qu'ils sont récents et concentrés sur l'Iran — mais pour des raisons légitimes (le conflit US-Iran était le sujet dominant de janvier-février 2026). Les heuristiques Niveau A ne distinguent pas un sharp géopolitique actif d'un insider one-shot.

**Le critère funding source manquant est probablement le plus discriminant.** Le rapport 3 documente que le cluster Bubblemaps a été identifié principalement via shared Binance deposit address. Sans ce critère, on rate les membres périphériques (nothingeverhappens911) et on ne peut pas relier les wallets entre eux.

### Ce qui est structurellement limité

**Magamyman est indétectable par des heuristiques simples.** Actif depuis octobre 2024 avec un historique de trading organique, il ne déclenche aucun flag de fraîcheur. Le rapport 3 le documente explicitement comme un cas de "camouflage par activité organique". La seule façon de le détecter est via (a) clustering avec les autres wallets du cluster via shared deposit, ou (b) analyse du timing précis (premier trade 71 min avant annonce). Le critère `time_to_event < 48h` est trop loose pour ce cas — `time_to_event < 2h` l'aurait attrapé, mais au prix de rater d'autres insiders qui tradent plus tôt.

---

## 5. Recommandation : GO avec 4 ajustements prioritaires

Les résultats du pilote justifient le passage en phase D. Les heuristiques Niveau A fonctionnent sur le cas le plus clean du corpus (Iran strikes) avec un recall de 71% — au-dessus du seuil du plan C (≥ 60%). La precision de 50% est en-dessous de ce qu'on voudrait en production, mais c'est mesuré sur un échantillon de 10 flags seulement, et les faux positifs sont classifiables par investigation manuelle en quelques minutes.

**Les 4 ajustements suivants sont nécessaires avant déploiement C2 en production :**

### Ajustement 1 — Signal d'alignement directionnel (NOUVEAU, critique)

C'est l'apprentissage principal du pilote : les heuristiques actuelles ne capturent pas la direction du trade. Un insider achète YES (direction correcte). Un contrariant achète NO (direction incorrecte). Les deux ont la même signature on-chain.

**Solution** : ajouter un signal d'alignement entre la direction du trade et le sentiment marché / news émergentes au moment du trade. Concrètement :
- `outcome_traded` : YES ou NO — est-ce que le wallet parie dans la direction de l'événement qui finit par se produire ?
- `price_at_entry` vs `resolution_price` : le wallet achète-t-il un outcome à prix bas qui finit à $1 (insider classique) ou un outcome à prix haut qui finit à $0 (contrariant) ?
- Post-résolution seulement : `realized_pnl > 0` comme filtre binaire — un insider gagnant a par définition un PnL positif. Ce filtre élimine les contrariants perdants trivalement.

**Caveat** : ce filtre ne peut être appliqué qu'**après résolution** du marché, pas en temps réel. En temps réel, la confusion insider/contrariant reste entière. Pour le C2 pré-résolution, on peut approximer via `outcome_traded == direction du consensus marché en hausse` (le wallet parie-t-il dans le sens du mouvement de prix, ou contre ?).

### Ajustement 2 — Features de diversification (anti-sharp filter)

Ajouter un scoring secondaire qui pénalise les wallets avec :
- `nb_markets_lifetime > 50` → réduire le score de 1 point
- `pct_geopolitical < 80%` → réduire le score de 1 point
- `still_active_post_event = true` → réduire le score de 1 point (un insider disparaît après)

### Ajustement 3 — Couche clustering pour membres périphériques

Implémenter la heuristique Victor 2020 (deposit-address-reuse) pour relier les wallets entre eux. C'est ce qui a permis à Chainalysis et Bubblemaps d'identifier les clusters. Nécessite le traçage des transferts USDC via RPC Polygon (Alchemy free tier).

### Ajustement 4 — Détection CEX funding source

Le rapport 3 identifie le shared Binance deposit comme le signal le plus discriminant du cluster Iran. Nécessite : (a) liste des hot wallets CEX connus, (b) traçage des 2 premiers hops de funding entrant, (c) matching deposit addresses.

---

## 6. Limitations et caveats

**Ce pilote ne prouve pas que les heuristiques fonctionnent en général.** Il prouve qu'elles fonctionnent sur un cas spécifique (Iran strikes) qui est le plus clean du corpus (fresh wallets, concentration extrême, timing net). Les cas plus ambigus (Théo, Taylor Swift, Pope Conclave) produiront des résultats très différents. La validation cross-cas (expériences E7-E9 du plan C) reste nécessaire.

**La base rate est biaisée à la baisse.** L'endpoint `/holders` ne retourne que les wallets qui détiennent encore des shares post-résolution. Les traders qui ont redeemed n'apparaissent pas. Le vrai dénominateur (tous les traders du marché) est probablement 5-10x plus grand, ce qui diluerait la precision. Pour un base rate réaliste, il faudra Dune ou Goldsky pour accéder à tous les `OrderFilled` events du marché.

**Pas de FDR BH sur ce pilote.** Le score composite 0-4 est trop discret pour bénéficier d'une correction multiple testing. FDR BH sera appliqué en expérience E1 (leaderboard C1 avec scores continus BSS/CLV/edge).

**Le pilote ne teste pas l'anti-honeypot.** Aucun des wallets analysés ne présente de pattern honeypot (track record construit pour piéger des copieurs). Ce test est reporté à l'expérience E3 (cas synthétiques).

**Classification manuelle initiale erronée.** La première classification (19 avril matin) avait identifié 2 wallets comme "vrais informés probables" sur la base des features on-chain seules (fraîcheur, concentration, sizing). L'investigation des positions réelles sur Polymarket (19 avril soir) a révélé qu'ils avaient parié dans la mauvaise direction. **Leçon : ne jamais classifier un wallet sans vérifier la direction du trade et le PnL réalisé.** Les features on-chain ne suffisent pas — l'outcome est indispensable.

**Le ground truth des 18 cas forensiques est biaisé vers les gagnants.** Tous les cas du rapport 3 sont des insiders/manipulateurs qui ont profité. Aucun cas de "contrariant insider" (quelqu'un qui aurait eu l'info mais parié dans la mauvaise direction) n'est documenté — parce que personne ne fait d'article sur un insider qui perd. Ce biais de survivorship doit être reconnu explicitement dans toute évaluation des heuristiques.

---

## 7. Prochaines étapes concrètes

### Immédiat (cette semaine)

- [ ] Créer `data/ground_truth/markets_disputed.csv` pour C3 (~1h)
- [ ] Lancer E7 — calibration heuristiques C2 sur train set (Maduro, Biden pardons, Théo) — vérifier si les seuils tiennent sur d'autres cas
- [ ] Lancer E9 — test discriminant sur sharps positifs (Domer, Aenews2, Beachboy4) — vérifier qu'ils ne sont PAS flaggés

### Semaine prochaine

- [ ] E1 — leaderboard FDR-BH C1 (le gros morceau, 6-8h)
- [ ] E11 — LLM scoring C3 Haiku sur markets_disputed
- [ ] Gate 2 — décision finale GO phase D

### Phase D (si Gate 2 PASS)

- Semaine 1 : implémenter proxy↔EOA mapping + Victor deposit-address-reuse clustering
- Semaine 2 : CEX funding source detection via Alchemy RPC + signal directionnel (outcome_traded + realized_pnl)
- Semaine 3 : C1 sharp money + anti-honeypot
- Semaine 4 : C2 informed trading avec les 4 ajustements

---

*Fin de la synthèse. Ce document sera mis à jour après les expériences E7-E9 et le Gate 2.*
