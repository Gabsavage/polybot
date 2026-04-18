# Projet Polymarket Bot — Brief consolidé

## Objectif
Bot personnel d'aide à la décision pour trading sur Polymarket, usage privé, 
générer du revenu récurrent + capter les gros coups informés quand ils passent.
Non destiné à être publié ou commercialisé en v1 (edge privé préservé).

## Capital et horizon
- Capital initial: 1500-2000€ (SOL existants convertis + apport possible)
- Sizing adaptatif selon liquidité marché et force signal
- Stratégie bankroll: part réinvestie + part trésorerie intouchable (règle à coder)
- Horizon MVP fonctionnel: 4-6 semaines
- Contraintes temps: side project, 15-20h/semaine
- Budget infra: <30€/mois

## Architecture globale (validée)
Système de SIGNALS uniquement, pas d'exécution automatique en v1.
Un bot Telegram privé avec 3 types de messages:

1. **Sharp Money Copy** (composant 1) — edge borrowed, signal récurrent 
   plusieurs fois par jour. Filtre anti-honeypot intégré (détection faux-sharp 
   qui construisent un track record pour drainer des copieurs).

2. **Informed Trading Alert** (composant 2) — anomalies type insider, signal 
   rare haute conviction. Heuristiques Tier 1 brief 4: fresh wallet + shared 
   CEX deposit + niche market + pré-event + concentration > 90%.

3. **Resolution Risk Filter** (composant 3) — défensif, fonction d'évaluation 
   d'un marché donné. Appelée automatiquement dans les alertes 1 et 2, 
   ET disponible à la demande via commande Telegram /risk <url>.

Exécution: manuelle par l'utilisateur sur Polymarket (accès via VPN).
Évolution v2 envisageable: auto-exec du composant 1 si validation confirmée.

## Stack technique envisagée (à détailler en phase A)
- VPS Hetzner 5-10€/mois
- Data: Dune free + CLOB API directe + Goldsky subgraph Polymarket (free)
- Stockage: DuckDB + Parquet local
- Code: Python (pandas/polars, py-clob-client)
- Alertes: bot Telegram privé (python-telegram-bot)

## Contraintes légales/fiscales
- Accès Polymarket via VPN (géobloqué FR depuis nov 2024)
- Position fiscale par défaut: PFU 31,4% actifs numériques (art. 150 VH bis CGI)
- Déclaration 3916-bis obligatoire dès premier flux
- Outil strictement privé non publié (évite risques CASP/MiCA, copy-trading auto)
- Pas de KYC Polymarket (géobloc empêche)

## Principes de design
- Signaux probabilistes (scores de suspicion), pas labels binaires
- Anti-honeypot intégré dans composant 1
- Backtest systématique sur les 18 cas forensiques du brief 3
- Correction FDR Benjamini-Hochberg sur les leaderboards
- Brier scores et CLV (Closing Line Value) pour mesurer skill réel vs luck
- Ne jamais publier les heuristiques complètes (concept drift adversarial)
- Human-in-the-loop pour toute décision de trade
- Gotchas techniques à gérer: USDC.e vs USDC native, Neg Risk vs Vanilla CTF,
  finalité Polygon probabiliste, signature types CLOB (Type 0/1/2)

## Hors scope v1 (explicitement)
- Exécution automatique des trades
- Produit commercial / SaaS public
- Backend multi-user / auth
- API publique
- Sports betting (focus politique/géopolitique/crypto/culture initialement)

## Ground truth et posture méthodologique
Pas de ground truth officielle pour "insider trading" — posture pragmatique:
scores de suspicion + investigation manuelle pour décision de trade.
Conviction suffisante pour trader ≠ preuve pour tribunal.
Reference heuristique: "odds tellement basses que ça ne peut pas arriver sauf 
si tu sais" = edge vs implied prob × sizing × timing pré-event.

## Références projet
Les 6 rapports de recherche détaillés sont dans les project files:
- 1_mapping_analytics_ecosystem.md (paysage concurrentiel)
- 2_polymarket_stack_technique.md (architecture data Polymarket)
- 3_informed_trading_and_sharp_money.md (18 cas forensiques + benchmarks)
- 4_wallet_clustering.md (méthodes de détection et clustering)
- 5_polymarket_france_compliance.md (cadre légal/fiscal FR + alternatives)
- 6_solo_quant_builder.md (analyse produit/monétisation — pertinent si pivot commercial futur)