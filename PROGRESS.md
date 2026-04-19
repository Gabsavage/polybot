# Polycasquette — Progress

## Phase C — Recherche et backtest

### Fait

- **Ground truth constitué** — 18 cas forensiques, 31 wallets (22 avec adresse, 71%), 9 sharps positifs, 14 adresses enrichies via API Polymarket
- **Documents de référence** — 9 fichiers dans `docs/reference/` (brief, architecture, 6 rapports de recherche)
- **Plan C rédigé** — `docs/C_plan_recherche_backtest.md`, 12 expériences, allocation 50% C1 / 35% C2 / 15% C3, decision gates définis
- **Notebook pilote Iran lancé** — `notebooks/01_pilote_iran_cluster.ipynb`, Parties 1-3 structurées, marché identifié (condition_id, token IDs, $90M volume)
- **Pivot API** — CLOB `/trades` devenu auth-only, pivoté sur Data API publique (`data-api.polymarket.com/trades?user=<addr>`), notebook mis à jour

### En cours

- **Exécution notebook pilote** — validation cellule par cellule, en attente résultats Partie 2 (ingestion via Data API) et Partie 4 (verdict)

### Reste à faire (phase C)

- [ ] Finaliser pilote Iran — verdict GO/NOGO sur pipeline
- [ ] Créer `data/ground_truth/markets_disputed.csv` (5-8 cas C3)
- [ ] E1 — Leaderboard FDR-BH sans seed list (6-8h)
- [ ] E2 — Identifier nouveaux sharps hors seed (3-4h)
- [ ] E3 — Anti-honeypot cas synthétiques (3-4h)
- [ ] E7-E9 — Calibration + test C2 sur train/test set (5-8h)
- [ ] E11 — LLM scoring C3 Haiku (2-3h)
- [ ] Gate 2 — Décision phase D

### Blocages connus

| Problème | Impact | Contournement |
|----------|--------|---------------|
| CLOB `/trades` auth-only | Ingestion marché entier impossible sans clé | Data API par wallet (OK pour pilote, limite pour C2 base rate) |
| CLOB `/prices-history` vide sur marchés résolus | Pas de timeline prix native | Reconstitution depuis prix d'entrée des trades |
| 12 adresses GT irrécupérables (Chainalysis propriétaire) | Recall C2 max ~7/11 sur test set | Accepté comme limite structurelle |
