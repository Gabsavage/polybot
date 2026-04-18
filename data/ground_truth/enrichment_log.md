# Enrichment Log — 2026-04-18 (manual via API)

## Summary

- **Adresses récupérées** : 14
- **Lookups échoués (404/mauvais profil)** : 6
- **Adresses toujours manquantes** : 11 wallets + 3 sharps institutionnels

## Adresses récupérées (wallets.csv)

| Case | Username | Adresse | Source |
|------|----------|---------|--------|
| 1 - Théo | Michie | `0xed2239a9150c3920000d0094d28fa51c7db03dd0` | polymarket.com/@Michie |
| 2 - Iran | Magamyman | `0x4dfd481c16d9995b809780fd8a9808e8689f6e4a` | polymarket.com/@magamyman |
| 2 - Iran | Dicedicedice | `0xdde15ebd95330ce69136dc0ccd810d22382e02c5` | polymarket.com/@Dicedicedice |
| 2 - Iran | Neodbs | `0x56efadc9defe5b7a21af751e0d026f2cf54136db` | polymarket.com/@Neodbs |
| 2 - Iran | Planktonbets | `0x38745db27f7360a287f6ca3c9b6a6a9c76149801` | polymarket.com/@Planktonbets |
| 6 - Nobel | dirtycup | `0x234cc49e43dff8b3207bbd3a8a2579f339cb9867` | polymarket.com/@dirtycup |
| 12 - Swift | romanticpaul | `0xf5cfe6f998d597085e366f915b140e82e0869fc6` | polymarket.com/@romanticpaul |
| 13 - Pope | syncope | `0xe75c5abf0647d8b2b1f5a8f64f3387d7311df6c2` | polymarket.com/@syncope |
| 15 - XRP | a4385 | `0x506bce138df20695c03cd5a59a937499fb00b0fe` | polymarket.com/@a4385 |

## Adresses récupérées (sharps_positive.csv)

| Username | Adresse | Source |
|----------|---------|--------|
| Aenews (aenews2) | `0x44c1dfe43260c94ed4f1d00de2e1f80fb113ebc1` | polymarket.com/@aenews2 |
| Kickstand7 | `0xd1acd3925d895de9aec98ff95f3a30c5279d08d5` | polymarket.com/@Kickstand7 |
| gopfan2 | `0xf2f6af4f27ec2dcf4072095ab804016e14cd5817` | polymarket.com/@gopfan2 |
| HolyMoses7 | `0xa4b366ad22fc0d06f1e934ff468e8922431a87b8` | polymarket.com/@HolyMoses7 |
| Beachboy4 | `0xc2e7800b5af46e6093872b177b7a5e7f0563be51` | polymarket.com/@Beachboy4 |

## Échecs

| Username | Raison |
|----------|--------|
| SBet365 / Sbet365 | 404 — username exact inconnu ou supprimé |
| AlphaRaccoon | 404 — profil renommé post-exposure (rapport confirme) |
| nothingeverhappens911 | 404 — adresse déjà connue du rapport (`0xa4eb...`) |
| predictorxyz | 404 — adresse déjà connue du rapport (`0x1d9a...`) |
| @aenews (original) | Mauvais profil ($7K volume, -$0.90 P&L) — le vrai est @aenews2 |
| @wintermute | Mauvais profil ($144K volume) — market maker institutionnel trade sous autre profil |

## Adresses toujours manquantes

### wallets.csv (11 lignes sans adresse)
- Théo wallets 5-11 (7 lignes) — données propriétaires Chainalysis, non publiées
- SBet365 (Maduro) — username 404
- Axiom anons (2 lignes) — identité inconnue
- Biden pardons (2 comptes) — screenshots masqués NPR
- Nobel 6741 + 3e compte — usernames exacts inconnus
- AlphaRaccoon — profil renommé, adresse tronquée `0xafEe...`
- Iran Anon 6e wallet — identité inconnue

### sharps_positive.csv (3 lignes sans adresse)
- Wintermute, Jump Trading, Susquehanna — market makers institutionnels, adresses non publiques

## Taux de complétude

| Fichier | Avant | Après | Taux |
|---------|-------|-------|------|
| wallets.csv (31 lignes) | 13/31 (42%) | 22/31 (71%) | **+9 adresses** |
| sharps_positive.csv (9 lignes) | 1/9 (11%) | 6/9 (67%) | **+5 adresses** |
| **Total** | 14/40 (35%) | 28/40 (70%) | **+14 adresses** |
