# Polycasquette — Progress

## 2026-04-20 — Phase C bouclée

- Ground truth enrichi (14/32 adresses via API Polymarket)
- Notebook pilote Iran cluster exécuté end-to-end
- Recall 71% (5/7 GT flaggés), Precision 50% (5/10 flags vrais)
- Faille méthodologique identifiée : les heuristiques Niveau A ne distinguent pas insider gagnant vs contrariant perdant
- Biais de survivorship documenté sur le GT (tous les cas médiatisés sont des gagnants)
- Verdict : GO pour phase B avec 4 ajustements prioritaires dont un fondamental (alignement directionnel)
- Design du bot ajusté : human-in-the-loop obligatoire, pas d'auto-trade

Next: 2-3 jours pause, puis phase B (plan de développement du bot)

---

## Phase C — Détail

### Livrables produits

| Fichier | Description |
|---------|-------------|
| `data/ground_truth/cases.csv` | 18 cas forensiques |
| `data/ground_truth/wallets.csv` | 31 wallets (22 avec adresse, 71%) |
| `data/ground_truth/sharps_positive.csv` | 9 sharps (6 avec adresse, 67%) |
| `data/ground_truth/enrichment_log.md` | Log des lookups API Polymarket |
| `data/ground_truth/iran_base_rate_investigation.csv` | 5 flags non-GT classifiés (tous faux positifs) |
| `docs/C_plan_recherche_backtest.md` | Plan C v2 (12 expériences, gates) |
| `docs/C_synthese_pilote.md` | Synthèse pilote Iran — résultats corrigés |
| `docs/archive/C_plan_recherche_v1.md` | Plan C v1 archivé |
| `notebooks/01_pilote_iran_cluster.ipynb` | Notebook pilote Iran (9 parties) |
| `scripts/enrich_ground_truth.py` | Script enrichissement adresses |

### Résultats clés pilote Iran

- **7/7 wallets GT retrouvés** via Data API publique
- **Recall C2** : 5/7 = 71% (2 ratés : périphérique + camouflé)
- **Precision C2** : 5/10 = 50% (5 FP : 2 contrariants perdants, 2 sharps géo, 1 indéterminé)
- **F1** : 59%
- **Correction majeure** : 2 wallets initialement classés "vrais informés" étaient des contrariants perdants (~$260K de pertes). Precision corrigée de 90% → 50%

### 4 ajustements identifiés pour phase B

1. **Alignement directionnel** (critique) — outcome_traded + realized_pnl pour distinguer insider vs contrariant
2. **Features diversification** — nb_markets, pct_geopolitical, still_active_post_event
3. **Clustering Victor 2020** — deposit-address-reuse via RPC Polygon
4. **CEX funding source** — shared deposit detection via trace USDC

### Blocages connus

| Problème | Impact | Contournement |
|----------|--------|---------------|
| CLOB `/trades` auth-only | Pas de vue marché-first | Data API par wallet + Dune pour leaderboard C1 |
| CLOB `/prices-history` vide sur résolus | Pas de timeline prix native | Reconstitution depuis prix d'entrée des trades |
| 12 adresses GT irrécupérables | Recall C2 max ~7/11 sur test set | Accepté comme limite structurelle |
| Heuristiques direction-blind | 50% precision (contrariants flaggés) | Ajustement 1 : filtre directionnel post-résolution |
| GT biaisé gagnants-only | Pas de ground truth sur contrariants | Documenter le biais, pas de fix possible |
