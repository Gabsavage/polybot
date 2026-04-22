# Decision Gates — Polymarket Bot

Format: bilan ecrit obligatoire avec questions methodologiques avant passage au milestone suivant.

---

## Gate M1 — Fondations infra + snapshot CLOB

**Gate preliminaire — T+45min apres deploiement**. Criteres quantitatifs ci-dessous refletent un etat partiel. Les criteres qualitatifs et la decision finale GO/NO-GO sont a remplir apres 3-4h de stabilite minimum (on revient dessus plus tard dans la journee).

Date : 2026-04-22
Sessions passees sur M1 : 2 (2026-04-21, 2026-04-22)
Lignes de code ajoutees : ~2500 (src/polybot + tests + scripts + deploy + research)

### Criteres quantitatifs

#### Snapshots R2

| Metric | Valeur |
|--------|--------|
| Snapshots reussis depuis deploiement VPS | 1 (timer) + 1 (manual) = 2 |
| Snapshots totaux sur R2 (incluant dev local) | 3 |
| Taille moyenne par snapshot | 23.5 KB |
| Rows par snapshot | 300 (150 marches x 2 tokens) |
| Marches dans snapshot_universe | 150 |
| Filtre volume_24h > $50K | Actif, verifie |
| Null bid/ask | ~11% (marches one-sided, attendu) |
| **Projection 12 mois (hourly)** | **0.19 GB** |
| R2 free tier (10 GB) | Largement OK — ~52x marge |

#### DuckDB

| Metric | Valeur |
|--------|--------|
| Tables creees | 12 (11 + _migrations) |
| Migration 001 appliquee | Oui |
| snapshot_universe peuplee | 150 rows |

#### Systemd timers

| Timer | Status | Dernier run | Prochain | Resultat |
|-------|--------|-------------|----------|----------|
| polybot-snapshot (hourly) | active | 2026-04-22 13:01 CEST | 14:00 CEST | SUCCESS (6.2s CPU) |
| polybot-universe-refresh (6h) | active | 2026-04-22 12:30 CEST | 18:30 CEST | SUCCESS (5.5s CPU) |
| polybot-healthcheck (6h) | active | pas encore declenche | 15:00 CEST | - |

#### Erreurs journalctl

Aucune erreur (priority=err) sur les 2 dernieres heures. Tous les services: `code=exited, status=0/SUCCESS`.

#### Ressources VPS

| Metric | Valeur |
|--------|--------|
| RAM utilisee | 511 MB / 7.8 GB (6.5%) |
| Disque utilise | 3.3 GB / 145 GB (2.3%) |
| Load average | 0.03, 0.01, 0.00 |
| CPU par snapshot | ~6s |

#### CI + tests

| Metric | Valeur |
|--------|--------|
| Unit tests | 17/17 pass |
| Lint (ruff) | Clean |
| Schema validation seed list | 5/5 pass |
| Seed list | 15 wallets (6 original + 9 discovery v2) |

### Questions methodologiques

1. La strategie snapshot R2 tient-elle le volume reel observe ?
   **Reponse : OUI.** 23.5 KB/snapshot x 24h x 365j = 0.19 GB/an. R2 free tier = 10 GB. Marge 52x. Meme si la taille double avec plus de marches, on tient 25+ ans dans le free tier. Non-issue.

2. Y a-t-il eu un echec de snapshot sur les 48h de run ?
   **Reponse : A COMPLETER apres 3-4h.** Sur T+45min : 0 echecs, 2/2 runs (1 timer + 1 manual) reussis. Verdict definitif apres au moins 4 snapshots timer consecutifs.

3. Le heartbeat fonctionne-t-il, ou bruit > rassurance ?
   **Reponse : A COMPLETER.** Timer healthcheck pas encore declenche (prochain run 15:00 CEST). A verifier apres premier run.

4. ADR a figer ?
   **Reponse :** ADR-004 (Contabo Atlanta) fige. Parquet zstd + partitionnement YYYY-MM-DD/HH.parquet figes. Format stable, pas de raison de changer.

### Decisions prises

- VPS : Contabo Atlanta CX23 ($4/mois), US-East, pas besoin de VPN (ADR-004)
- Parquet : zstd compression, partitionnement snapshots/YYYY-MM-DD/HH.parquet
- Seed list : 15 wallets Tier A (11 A1 + 4 A2), schema YAML valide

### Backlog cree (a traiter plus tard)

- [ ] Telegram integration healthcheck (#ops channel) — M4
- [ ] Cold migration job (DuckDB > 90j vers Parquet) — M5
- [ ] Monitoring uptime VPS Contabo premier mois — ongoing

### ADRs ajoutes

- ADR-004 : VPS Provider Contabo Atlanta

### Checklist qualitative (a remplir apres 3-4h de stabilite)

- [ ] >= 4 snapshots timer consecutifs sans echec
- [ ] Healthcheck timer a tourne au moins 1 fois avec succes
- [ ] validate_snapshot.py OK sur un snapshot recent
- [ ] Pas de degradation RAM/CPU apres plusieurs heures
- [ ] Aucune erreur journalctl priorite err

### GO/NO-GO M2 :

**A DECIDER** apres validation de la checklist qualitative ci-dessus.
