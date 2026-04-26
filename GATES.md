# GATES.md

Decision gates entre milestones de la phase B. Reference : B_plan_developpement.md §4.

---

## Gate M6 → M7 — FINAL

**Date** : 2026-04-26
**Tag** : `m6-complete`
**Decision** : [x] GO

### Critères

- [x] C2 pipeline fonctionnel (scans toutes les 5 min, 200+ marchés hot)
- [x] alert_outcomes job fonctionne (10 outcomes enrichis)
- [x] Daemon unifié — 0 erreurs DuckDB lock en 12h
- [x] /toggle shadow fonctionne
- [ ] Alertes C2 émises : 0 (normal — seuil 4/7 non atteint, pipeline OK)

### Architecture

- Daemon unifié : bot + C1 + C2 + 5 indexers dans un seul process
- ThreadPoolExecutor(max_workers=1) pour sérialiser les écritures DB
- Anciens timers/services M2-M3 supprimés
- 3 timers M1 conservés (snapshot, universe-refresh, healthcheck)

---

## Gate M5 → M6 — FINAL

**Date** : 2026-04-25
**Tag** : `m5-complete`
**Decision** : [x] GO

### Critères

- [x] /risk < 5s
- [x] Cache : 2ème appel = 0 call LLM
- [x] C1 alertes incluent vrai score C3 (11/11)
- [x] resolution_risk_cache : 11 entries

---

## Gate M4 → M5 — FINAL

**Date** : 2026-04-25
**Tag** : `m4-complete`
**Decision** : [x] GO

### Critères

- [x] Alerte C1 test reçue dans #ops < 2 min
- [x] Format lisible mobile
- [x] Dédup fonctionne
- [x] /status et /bankroll fonctionnent
- [x] 11 alertes C1 émises

### Key metrics

- 11 alertes C1 en shadow mode
- Bankroll initialisé à $2000
- Quarter-Kelly sizing actif

---

## Gate M3 → M4 — FINAL

**Date** : 2026-04-25
**Tag** : `m3-complete`
**Decision** : [x] GO

### Critères

- [x] proxy_eoa_map : 91,974 (objectif >= 15) — 15/15 Tier A matchés
- [x] resolutions : 1,014,570 (objectif >= 100)
- [x] trades_all : 5,332,147 (objectif >= 10,000)

### Pivots majeurs

- Goldsky mort → Alchemy RPC direct
- Factory scan brut → lookup ciblé (15 calls vs 75M blocks)
- UMA Oracle → ConditionalTokens contract
- Alchemy free tier → PAYG

---

## Gate M2 → M3 — FINAL

**Date** : 2026-04-24
**Tag** : `m2-complete`
**Decision** : [x] GO

### Critères quantitatifs

- [x] COUNT(markets) > 10 000 → **64 307** ✅
- [x] COUNT(trades) > 10 → **871** ✅
- [x] COUNT(tracked_wallets WHERE tier='A') = 15 → **15** ✅
- [x] Logs < 1% erreurs / 24h → **< 0.1%** ✅ (1 seul échec markets timer sur ~160 runs)

### Incidents

- Trades daemon : 119 restarts au déploiement initial (service activé
  avant migration/seed). Stabilisé après, 0 erreurs depuis.
- Markets gamma : upsert initial 58 min (row-by-row executemany).
  Optimisé via temp table bulk → 11s. Timer remis à 15 min.

### Key metrics prod

- Markets : 64K via Gamma API (3x l'estimation initiale de 20K)
- Trades : 871 pour 15 wallets Tier A
- Markets sync : 97s total (87s fetch + 11s upsert) — viable sur timer 15 min
- RAM : 565 MB / 7.8 GB
- 6 services systemd actifs (3 M1 + 2 M2 + trades daemon)

---

## Gate M1 → M2 — FINAL

**Date d'ouverture du gate** : 2026-04-22 12:15 CEST
**Date de bascule M1 → M2** : 2026-04-22 15:15 CEST
**Decision finale** : [x] GO  /  [ ] NO-GO  /  [ ] GO conditionnel

---

### Criteres quantitatifs

#### Infrastructure

- [x] **VPS operationnel et accessible**
  - SSH polybot fonctionne
  - Uptime depuis deploiement : 3h00 consecutives sans crash
  - Contabo VPS 10 Atlanta, 4 vCPU / 8 GB RAM

- [x] **systemd timers actifs** (3 sur 3)
  - polybot-snapshot.timer : active (hourly)
  - polybot-universe-refresh.timer : active (6h)
  - polybot-healthcheck.timer : active (6h)

- [x] **DuckDB initialisee**
  - 12 tables presentes (11 metier + _migrations)
  - Migration 001 appliquee

#### Snapshots CLOB

- [x] **Nombre de snapshots reussis depuis deploiement**
  - 4 snapshots reussis sur 4 attendus (100%)
  - Parquet R2 : 10.parquet (UTC), 11, 12, 13
  - Trous : aucun
  - Note : nommage en UTC, mapping UTC+2 = CEST

- [x] **Selection top-150 fonctionne**
  - Refresh universe tourne a 12:30 CEST (SUCCESS)
  - Nombre de marches par snapshot : 140-150 (coherent avec filtre volume_24h > $50K)

- [x] **Stockage R2**
  - 4 snapshots recents presents sur R2
  - Taille moyenne par Parquet : 23.5 KB
  - Null bids : ~11% (marches one-sided, attendu)
  - Schema : 10 colonnes, types corrects

- [x] **Projection volume R2 12 mois**
  - Calcul : 23.5 KB x 24 x 365 / 1024 / 1024 = 0.19 GB/an
  - Sous le free tier 10 GB ? OUI (52x marge)

#### Stabilite

- [x] **Aucune erreur journalctl**
  - Tous les services : `code=exited, status=0/SUCCESS`
  - 0 erreur priorite err

- [x] **Backoff sur 429** : non declenche (pas de rate limit observe)

- [x] **Heartbeat actif**
  - Premier run healthcheck a 15:00 CEST : SUCCESS (4s CPU)
  - Prochain run prevu a 21:00 CEST

#### Cout et ressources

- [x] **Budget infra dans la cible**
  - VPS Contabo : $4/mois
  - R2 Cloudflare : free tier (0.19 GB utilise sur 10 GB = 1.9%)
  - Total : $4/mois / cible 30 EUR (tres large marge)

- [x] **Ressources VPS OK**
  - RAM utilisee : ~490 MB / 7.8 GB (6.3%)
  - Disque utilise : 3.3 GB / 145 GB (2.3%)
  - CPU peak pendant snapshot : 6s sur 60 min (~0.17%)
  - Load avg : 0.02 (quasi-idle)

---

### Criteres qualitatifs

- [x] **Le heartbeat est-il rassurant ou bruyant ?**
  - [x] Rassurant (info utile, frequence OK)
  - Format succinct, pas de bruit. Formalisation Telegram en M4.

- [x] **Est-ce que je comprends ce qui se passe a chaque run ?**
  - Oui. Logs systemd clairs. Aucune black box.

- [x] **Suis-je serein avec ce deploiement ?**
  - Oui. Tous les criteres verts, aucune erreur, ressources stables.

---

### Les 4 questions methodologiques

#### Q1 — La strategie snapshot R2 tient-elle le volume reel observe ?

**Reponse : OUI.** Observe 23.5 KB/snapshot x 24h x 365j = 0.19 GB/an.
R2 free tier (10 GB) tient 25+ ans au rythme actuel. Non-issue.

#### Q2 — Y a-t-il eu un echec de snapshot sur les premieres heures ?

**Reponse : NON.** 4/4 runs timer reussis (13h, 14h, 15h +
refresh_universe 12h30). Plus 1 manual au deploiement. Total 5/5
succes, 0 echec. Pas de rate limit 429.

#### Q3 — Le heartbeat fonctionne-t-il, ou bruit > rassurance ?

**Reponse : Fonctionnel.** Premier healthcheck run a 15:00 OK (4s CPU).
Format succinct. A reevaluer en M4 quand Telegram sera integre.

#### Q4 — Quels ADRs a figer maintenant ?

**ADRs valides :**
- [x] ADR-001 a ADR-007 (M1, crees ce jour)
- [x] ADR-008 a ADR-011 (Phase A, migres depuis A_architecture_technique.md)

Total : 11 ADRs dans docs/ADRs/.

---

### Decisions prises

- VPS Contabo Cloud VPS 10 Atlanta, $4/mois
- Snapshot CLOB hourly, partitionnement YYYY-MM-DD/HH.parquet zstd
- Top-150 markets avec filtre volume_24h > $50K
- Refresh universe 6h, healthcheck 6h
- Seed list Tier A : 15 wallets (11 A1 + 4 A2)
- Discovery v2 avec auto-classification A1/A2/reject + red flags

---

### Backlog M2 (a traiter au debut de M2)

- [ ] Enrichir scripts/validate_snapshot.py avec --last N, --timestamp, --list
- [ ] Documenter le nommage UTC des snapshots R2 (README ou ADR)
- [ ] Supprimer l'ancien Cloudflare API Token general (securite)
- [ ] chmod 600 sur .env local Mac

---

### Decision finale

**Synthese** : M1 deploye en prod Contabo Atlanta. VPS stable 3h, 4
snapshots consecutifs reussis sur R2, 0 erreur journalctl, ressources
VPS avec enorme marge (6.3% RAM, 2.3% disque). Healthcheck valide.
Seed list Tier A a 15 wallets.

**Decision** : **GO** pour M2.

**Action immediate** : Attaquer M2 (indexer trades Data API + indexer
markets Gamma) selon docs/specs/indexer_trades_spec.md.

**Date de decision** : 2026-04-22 15:15 CEST
**Valide par** : Gab (manual review)
