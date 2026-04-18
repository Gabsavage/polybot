# Polymarket en France : trader, builder, rester clean

**Bottom line — avril 2026.** Polymarket est **géobloqué en France depuis le 29 novembre 2024** sur intervention de l'ANJ et figure de facto dans la liste des offres de jeu illégales ; mais la plateforme a effectué un spectaculaire retour aux US via l'acquisition de QCEX (DCM CFTC) en juillet 2025 et une levée ~2 Md$ d'ICE/NYSE entre octobre 2025 et mars 2026. Pour un résident fiscal français, deux messages clés : (i) **trader Polymarket via VPN reste possible techniquement, expose juridiquement sur le terrain fiscal plus que pénal, et la qualification la plus défensive est le PFU actifs numériques à 31,4 %** (article 150 VH bis CGI) ; (ii) **construire un SaaS analytics basé sur la data publique Polymarket est largement réalisable depuis la France en micro-entreprise puis SASU, tant qu'on reste sur de l'analytics pur** et qu'on évite le copy-trading automatisé qui tomberait potentiellement sous CASP (MiCA) voire CTA (CFTC) côté US. Le cadre fiscal a récemment durci : la CSG est passée à 10,6 % (LFSS 2026), le PFU total à 31,4 %, et la directive DAC8 est en vigueur depuis le 1ᵉʳ janvier 2026. Chaque zone de flou importante est explicitement signalée — ce rapport ne dispense pas d'une consultation d'avocat fiscaliste au-delà de 5 000 € de gains annuels ou pour toute structuration entrepreneuriale.

---

## Partie 1 — Statut légal de Polymarket par juridiction (Q1 2026)

### 1.1 États-Unis : retour complet via QCX, plateforme double

Le settlement CFTC de janvier 2022 (Order 22-09, amende **1,4 M$**, géoblocage des US persons) est resté inchangé sur son principe, mais Polymarket a construit en 2025 une **voie de retour entièrement réglementée**. Trois événements majeurs :

- **15 juillet 2025** : le DOJ (SDNY) et la CFTC envoient des *declination notices* à Polymarket. Les deux enquêtes civiles et pénales déclenchées par le **raid FBI du 13 novembre 2024** chez Shayne Coplan (SoHo, saisie du téléphone et des appareils, aucune inculpation) sont closes sans charges sous l'administration Trump II. Coplan confirme publiquement le jour même.
- **21 juillet 2025** : closing de l'acquisition **QCEX** (QCX LLC comme DCM + QC Clearing LLC comme DCO) pour **112 M$**, donnant à Polymarket ses licences CFTC.
- **25 novembre 2025** : la CFTC publie un **Amended Order of Designation** transformant QCX LLC (d/b/a *Polymarket US*) en DCM pleinement opérationnel avec accès intermédié via FCMs. Lancement iOS le 2-3 décembre 2025, focus initial sports betting, rollout invite-only puis ouverture progressive.

La CFTC a évolué sous **Caroline Pham** (Acting Chair du 20 janv. au 22 déc. 2025, approche "back-to-basics") puis **Michael Selig** (confirmé le 22 décembre 2025). Un **ANPRM** sur les event contracts a été publié au Federal Register le 16 mars 2026. Côté capital, **ICE (parent NYSE) a investi ~2 Md$** entre octobre 2025 et mars 2026 (valorisation pré-money 8 Md$, post-money ~9 Md$), avec partenariat de distribution de données institutionnelles (*Polymarket Signals and Sentiment*, février 2026). **1789 Capital** (Donald Trump Jr.) et **Founders Fund** (Thiel) sont au capital. Partenariat **X/xAI** officialisé le 6 juin 2025.

**Structure duale en avril 2026** : *Polymarket US* (QCX, CFTC-DCM, KYC, FCMs, USD fiat) pour les US persons ; *Polymarket International* (Adventure One QSS Inc., Panama, USDC.e sur Polygon, proxy wallet Safe) pour le reste du monde, non régulé par la CFTC. **Contestations état-par-état** en cours : Nevada Gaming Control Board (plainte civile janvier 2026), Massachusetts (injonction contre Kalshi applicable par analogie), Ohio (jugement défavorable 9 mars 2026) — patchwork fédéralisme / préemption non tranché.

### 1.2 France : géoblocage effectif, offre illégale qualifiée

**Accessible sans VPN : non.** L'ANJ a publié le 29 novembre 2024 un communiqué confirmant que « suite à l'intervention de l'ANJ, le site POLYMARKET ne propose plus ses services sur le territoire français ». Polymarket a accepté un géoblocage volontaire plutôt qu'un blocage administratif contentieux. L'éditeur identifié par l'ANJ est **Adventure One QSS Inc.** (Panama). Le déclencheur a été l'affaire du trader français "Théo" (~30-45 M$ misés sur la victoire de Trump, gains ~85 M$ selon presse). L'ANJ a publié en avril 2026 une communication intitulée « Plateformes de marchés de prédiction : des sites illégaux en France », **qualifiant explicitement les prediction markets de jeux d'argent non autorisés** au sens de la loi du 12 mai 2010 et du Code de la sécurité intérieure.

**Cadre applicable** : article **L. 320-1 CSI** (définition large du jeu d'argent : espérance de gain partiellement aléatoire + sacrifice financier) ; monopole FDJ/PMU + agrément ANJ pour paris sportifs, hippiques, poker. Prediction markets hors cadre. **Aucune jurisprudence française spécifique** sur les prediction markets. Le régime **JONUM** (loi SREN mai 2024) ne s'applique pas aux prédictions à gains monétaires directs.

**Sanctions théoriques** : opérateur passible de **3 ans d'emprisonnement + 90 000 € d'amende** (7 ans / 200 000 € en bande organisée, art. L. 324-1 et s. CSI). **Pour le joueur : aucune sanction pénale directe** en l'état du droit ; les risques réels sont contractuels (violation des ToS = fermeture de compte, gel des fonds côté UI) et fiscaux (fragilisation du dossier en cas de contrôle, argument d'activité occulte avec majoration 80 %). Usage de VPN : légalement neutre en France (pas d'infraction pénale), mais **viole les ToS Polymarket**.

### 1.3 Union européenne : MiCA hors sujet, jeux nationaux déterminants

**MiCA (règlement UE 2023/1114)**, applicable intégralement depuis le 30 décembre 2024, **n'adresse pas directement les prediction markets**. Les jeux d'argent restent de **compétence nationale** (exception CJUE à l'art. 56 TFUE). Chaque régulateur national applique son droit :

| Pays | Statut avril 2026 | Source / date |
|---|---|---|
| France | Géobloqué | ANJ 29/11/2024 |
| Belgique | Blacklist | Kansspelcommissie 04/02/2025 |
| Pologne | Blacklist | Ministry of Finance 08/01/2025 |
| Italie | Blacklist (IP-block) | ADM 22/10/2025 |
| Roumanie | Blacklist | ONJN nov. 2025 |
| Portugal | Blocage ISP | SRIJ 17/03/2026 |
| Pays-Bas | Enforcement | KSA 2025 |
| Bulgarie | Blocage ISP | Sofia Regional Court 02/02/2026 |
| Allemagne | Avertissement public | GGL 09/09/2025 (pas de blocage DNS systématique) |
| Espagne | Aucune action publique | Accès théoriquement ouvert |

La **BaFin** n'a pas agi en tant que régulateur financier ; MiCA n'a pas été utilisé pour saisir Polymarket.

### 1.4 Royaume-Uni : géobloqué historiquement

Polymarket a **auto-restreint le UK dès 2021**, sans licence UK Gambling Commission. Les prediction markets tombent dans le *betting intermediary* sous Gambling Act 2005, exigeant une licence UKGC pour tout opérateur ciblant des UK consumers. Pas de blocage ISP (contrairement à l'Australie, où l'ACMA a ordonné un blocage ISP en août 2025). Aucune démarche connue de Polymarket pour obtenir un UKGC en 2025-2026.

### 1.5 Suisse : DNS-block depuis fin 2024

**GESPA** a ajouté polymarket.com à sa blocklist officielle le **26 novembre 2024**, renouvelée trimestriellement (dernières en date : 24 février 2026, 24 mars 2026). Fondement : *Loi fédérale sur les jeux d'argent* (LJAr, en vigueur 1ᵉʳ janvier 2019) ; monopole Swisslos/Loterie Romande ; opérateurs étrangers exclus du licensing. Pas de sanction pénale directe du joueur.

---

## Partie 2 — Utilisateur français : risques concrets et qualification fiscale

### 2.1 Risques opérationnels pour un trader français

**Géoblocage France** : actif depuis le 29 novembre 2024, maintenu en avril 2026 (vérifié via sources spécialisées Q1 2026). Accès sans VPN : impossible en mode trading ; certaines pages publiques de données restent accessibles.

**VPN** : l'usage en France n'est pas une infraction pénale. Polymarket détecte toutefois les VPNs via analyse de wallet, de paiement, et d'empreintes. Conséquences documentées : **fermeture de compte, gel via la UI, refus de KYC ultérieur**. Sur le plan fiscal, l'usage d'un VPN ne crée pas d'infraction mais peut servir à l'administration pour étayer une **qualification d'activité occulte** (majoration 80 %, article 1728 CGI).

**Obligations déclaratives** (priorité) :

- **Formulaire 3916-bis** (art. 1649 bis C CGI) : obligation de déclarer les comptes d'actifs numériques détenus à l'étranger. **Position prudente** : déclarer le compte Polymarket (Adventure One QSS Inc., Panama, URL polymarket.com) — c'est un "organisme établi à l'étranger" conservant des clés via Magic Link / Turnkey. Les wallets purement self-custody (MetaMask, Ledger) ne sont **pas déclarables** en l'état du droit, sauf adoption définitive de l'amendement LF du 9 décembre 2025 (wallets self-custody > 5 000 €, statut à vérifier). **Aucun seuil** de déclenchement : obligation dès 1 € de flux.
- **Sanctions (art. 1736 X CGI)** : **750 € par compte non déclaré** (125 € par omission, plafond 10 000 €/déclaration), porté à **1 500 €** si valeur > 50 000 € à un moment de l'année. Majoration IR 10 % à 80 % selon le manquement. Dans le pire scénario, article 755 CGI (taxation 60 % présomption d'avoirs acquis à titre gratuit) — application aux crypto incertaine.
- **Formulaire 2086** : déclaration annuelle détaillée des plus-values sur actifs numériques. Pas de seuil d'exonération 305 € depuis 2023 — toute cession imposable doit figurer.
- **DAC8** (directive UE) : en vigueur **1ᵉʳ janvier 2026**. Échange automatique d'informations crypto entre administrations fiscales européennes. Réduit fortement la possibilité que des flux Polymarket échappent au fisc français.

### 2.2 Qualification fiscale : trois hypothèses, une recommandation

**Nature technique des positions** : collatéral USDC.e (ERC-20 bridged sur Polygon) ; tokens YES/NO sont des **ERC-1155 émis via le Conditional Token Framework (CTF) de Gnosis**, chacun représentant le droit de percevoir 1 USDC si l'événement se résout favorablement. Architecture **non-custodial** via **Gnosis Safe** en proxy wallet. Faits générateurs multiples : achat YES/NO (split), revente pré-résolution, redemption post-résolution, merge.

#### Hypothèse A — Plus-values sur actifs numériques (article 150 VH bis CGI)

**Base légale** : l'article 150 VH bis CGI impose à 12,8 % IR + 18,6 % prélèvements sociaux (hausse CSG à 10,6 % confirmée par la LFSS 2026 n° 2025-1403 du 30 décembre 2025, soit **PFU total 31,4 %** depuis 2025 rétroactivement) les plus-values sur *actifs numériques* au sens de **l'article L. 54-10-1 CMF** (loi PACTE, 22 mai 2019). Option pour le barème progressif possible (case 2OP, désormais révocable depuis LF 2026).

**Arguments pour** : les tokens CTF respectent littéralement la définition du 1° L. 54-10-1 (bien incorporel, DLT, identification du propriétaire). L'USDC est unanimement admis comme actif numérique (2°). Les tokens sont cessibles sur l'orderbook, ont une valeur de marché indépendante de la résolution. L'exclusion des *instruments financiers L. 211-1* joue en faveur de la qualification : ni titres cotés, ni contrats financiers MiFID II classiques.

**Arguments contre** : la CFTC les qualifie de *binary event contracts* (swaps). L'OSC canadien les a qualifiés d'*options binaires* (instruments financiers) en 2023. Si requalifiés en contrats de pari ou options binaires, ils sortent potentiellement de L. 54-10-1. **Le BOFiP BOI-RPPM-PVBMC-30 ne mentionne pas les prediction markets** — aucune position doctrinale officielle.

**Distinction occasionnel vs habituel** : depuis le 1ᵉʳ janvier 2023, la LF 2022 a créé **l'article 92, 2, 1° bis CGI** qui bascule les gains en BNC (et non plus en BIC) dès lors que les opérations sont effectuées « dans des conditions analogues à celles d'un professionnel ». **Aucun seuil chiffré légal** — appréciation in concreto par faisceau d'indices (outils pro, fréquence, volumes, systématisation). Le BOFiP (BOI-BIC-CHAMP-60-50, ACTU-2023-00099) précise que ce régime BNC subsidiaire n'a vocation à jouer « que dans des cas d'espèce exceptionnels ».

**Seuil de non-imposition 305 €** : supprimé depuis 2023 pour la déclaration ; toute cession imposable doit figurer sur 2086.

#### Hypothèse B — Gains de jeux d'argent et de hasard

**Principe** : le BOFiP **BOI-BNC-CHAMP-10-10-20-40 §400** exonère les gains de loteries, tombolas et jeux divers « même habituels » car ils ne constituent pas une « source de profits » au sens de l'article 92 CGI. Fondement : l'aléa rompt le caractère lucratif.

**Exception jurisprudentielle** : **CE 21 juin 2018 n° 412124** (poker en ligne ~1 300 parties/an) : BNC dès lors que le joueur « maîtrise de façon significative l'aléa inhérent au jeu par les qualités et le savoir-faire qu'il développe » et en retire des revenus significatifs. Trois critères cumulatifs.

**Polymarket = jeu de hasard au sens du droit français ?** Oui selon l'ANJ (communiqués novembre 2024 et avril 2026) : « espérance de gain partiellement aléatoire + sacrifice financier » (art. L. 320-1 CSI). **Mais** la qualification *police des jeux* n'est pas automatiquement transposable à la *fiscalité* (rappel CE 2018).

**Question critique non tranchée** : les gains issus d'un jeu **non autorisé** en France bénéficient-ils de la non-imposition ? Points d'analyse :
- La non-imposition découle non d'une exonération, mais de l'absence de qualification de source de profits. Elle n'est donc *pas conditionnée* à la légalité de l'opérateur — argument pro-non-imposition.
- **A contrario**, le BOFiP impose les revenus d'activités illégales (BOI-BNC-CHAMP-10-10-20-40 §10). Le juge peut panacher.
- **Aucune jurisprudence directe**. Le Conseil des prélèvements obligatoires (note décembre 2024) constate le silence doctrinal.

#### Hypothèse C — BNC (article 92 CGI)

Applicable si (i) conditions analogues à un professionnel (art. 92, 2, 1° bis), ou (ii) jurisprudence poker 2018 (maîtrise d'aléa + revenus significatifs). **Imposition** : barème progressif IR (0/11/30/41/45 %) + cotisations TNS (~40-45 % charges incluses). Régime **micro-BNC** (abattement 34 %) sous seuil **77 700 €** ; déclaration contrôlée 2035 au-delà.

#### Arbitrage et recommandation

| Profil | Qualification privilégiée | Degré de confiance | Fondement |
|---|---|---|---|
| Trader occasionnel (<5 k€/an) | **PFU actifs numériques 31,4 %** | Moyen (60 %) | 150 VH bis — USDC clairement actif numérique |
| Alt. occasionnel | Non imposable (jeu) | Faible (20 %) | Analogie FDJ, fragile car opérateur illégal |
| Trader régulier (>20 k€, systématique) | **BNC (art. 92, 2, 1° bis)** | Moyen-élevé (70 %) | Conditions analogues à un professionnel |
| Trader pro temps plein | BNC déclaration contrôlée + TNS | Élevé (85 %) | Unanimité doctrinale |

**Position recommandée par défaut** pour le trader occasionnel : **appliquer le régime 150 VH bis (PFU 31,4 %) via formulaire 2086** sur la plus-value globale EUR → USDC (entrée) → USDC (sortie) → EUR. Cette position :

- évite le risque pénal de non-déclaration et la majoration pour activité occulte ;
- est cohérente avec le traitement crypto standard et défensive en cas de contrôle ;
- ne dépend pas de la qualification contestée des tokens YES/NO car on impose la variation globale du portefeuille crypto ;
- reste réversible si le contribuable obtient ultérieurement une position plus favorable.

**Consultation avocat fiscaliste** fortement recommandée au-delà de 5 000 € de gains annuels ou en cas d'activité régulière. Cabinets référencés spécialisés crypto : ORWL Avocats (William O'Rorke), Revo Avocats (Alexandre Lourimi), Cabinet Bornhauser, Strategia Avocats, Odessa Avocats.

### 2.3 Vue d'ensemble synthétique

| Critère | A — 150 VH bis | B — Jeu non imposable | C — BNC |
|---|---|---|---|
| Taux IR | 12,8 % (ou barème) | 0 % | Barème 0-45 % |
| Prélèvements sociaux | 18,6 % | 0 % | CSG/CRDS via TNS |
| Cotisations sociales | Non | Non | **Oui** (~23 % micro, ~40 % déclaration contrôlée) |
| Formulaire principal | 2086 + 2042 | Aucun | 2042-C-Pro / 2035 |
| Seuil d'application | Aucun | Aucun | >~77 700 € bascule micro/réel |
| Sécurité juridique | Moyenne (tokens YES/NO contestables) | **Faible** (jeu illégal, pas de doctrine) | Élevée si activité caractérisée |
| Taux effectif 2 000 € gains | 628 € (31,4 %) | 0 € | ~858 € |
| Taux effectif 20 000 € | 6 280 € | 0 € théorique / BNC si requalification | ~8 580 € |

### 2.4 Cas chiffrés

**Hypothèses communes** : célibataire, 1 part, TMI 30 %, revenus salariés 40 k€ par ailleurs. Barème 2026 revalorisé.

**Scénario 1 — Trader occasionnel, 2 000 € de gains nets**
- PFU 150 VH bis : 2 000 × 31,4 % = **628 €**
- Jeu non imposable (hypothèse risquée) : **0 €**
- Micro-BNC : base 1 320 € après abattement 34 %, IR ~396 € + cotisations ~462 € = **~858 €**
- *Option prudente : 628 € (PFU).*

**Scénario 2 — Trader régulier, 20 000 € de gains nets**
- PFU 150 VH bis : **6 280 €**
- Jeu non imposable : 0 € en façade, mais **risque de requalification BNC quasi certain** à ce niveau si activité systématique (poker 2018 + art. 92, 2, 1° bis)
- Micro-BNC : base 13 200 €, IR marginal ~3 960 € + cotisations URSSAF 4 620 € = **~8 580 €**
- *À ce niveau, la question du caractère habituel devient déterminante ; consultation fiscaliste obligatoire.*

**Scénario 3 — Builder SaaS, 30 000 € CA**

| Option | Net en poche | Total prélèvements |
|---|---|---|
| Micro-BNC (abattement 34 %, URSSAF 23,1 %) | **~21 000 €** | ~9 000 € (~30 % CA) |
| SASU à l'IS, distribution 100 % dividendes | ~14 600 € | ~10 400 € (~34,7 %) |
| SASU mixte salaire 12 k€ + dividendes | ~16-18 000 € | Défavorable à 30 k€ car charges assimilé salarié |
| EURL TNS | ~18-20 000 € | Intermédiaire, dividendes >10 % capital = cotisations |

**Arbitrage** : à 30 k€, **micro-BNC est l'option la plus efficiente**. Bascule en SASU IS pertinente au-delà de ~60-80 k€ CA avec stratégie salaire minimum + dividendes, ou si charges réelles > 34 % (cloud, sous-traitance, API).

---

## Partie 3 — Plateformes alternatives

| Plateforme | Juridiction | Licence | KYC | Accès FR sans VPN | Volumes / notes |
|---|---|---|---|---|---|
| **IBKR ForecastEx** | US (CFTC DCM) via IBKR Ireland | **CFTC DCM** | Oui | **OUI** | **Seule option légale propre en France.** Macro + climat uniquement pour EEE. Frais 0,01 $/contrat, coupon ~3,8 % APY. |
| Kalshi | US Delaware | CFTC DCM (1ᵉʳ) | Oui | Non | Leader régulé. Valo 22 Md$ (mars 2026), ARR 600-700 M$. Sports ouverts depuis janv. 2025. Contesté Nevada/MA/OH. |
| Polymarket US | US (QCX) | CFTC DCM | Oui | Non | Invite-only US, KYC, via FCMs. |
| Polymarket International | Panama | Aucune | Non (wallet) | Non (géobloc. FR) | Global, USDC.e, UMA oracle. |
| PredictIt | US (PMRC) | No-Action CFTC 25-20 (juil. 2025) | Oui | Non | Politique US only. Limite 3 500 $/contrat. |
| **SX Bet** | SX Network + Arbitrum | Aucune | Non | Techniquement oui / interdit ANJ | Sports P2P, >780 M$ cumul. Non-custodial. |
| **Overtime Markets** (ex-Thales) | Curaçao / on-chain Optimism/Base | Aucune | Non | Idem | Sports décentralisé, fusion Thales avril 2025, token OVER. 200 M$+ cumul. |
| **Limitless Exchange** | Base L2 | Aucune | Non | Idem | **>1 Md$ cumul avril 2026**, marchés crypto/stocks courts. Token LMTS. |
| Myriad Markets | DASTAN/Decrypt, Abstract+Linea | Aucune | Basique | Idem | 100 M$+ cumul nov. 2025, intégré Trust Wallet. |
| Azuro Protocol | On-chain (Polygon/Gnosis/Base) | B2B infra | Non | Idem | SDK/liquidity layer pour ~28 dApps. Token AZUR. |
| Drift BET | Solana | Aucune | Non | Idem | Extension de Drift perp, pool 500 M$. |
| Zeitgeist | Polkadot parachain | Aucune | Non | Idem | **Quasi-mort**, ZTG delisté fin 2025. |
| Omen/Presagio | Gnosis Chain | Aucune | Non | Idem | Niche agents IA, volumes faibles. |
| Augur v1/v2 | Ethereum | Aucune | Non | Idem | **Quasi-mort**, reboot sept. 2025 en R&D. |
| Manifold | US | Play-money | Non | Oui | Hors scope (Mana non convertible depuis mars 2025). |

**Pour un résident français cherchant une solution "propre"** : **IBKR ForecastEx** via IBKR Ireland est la seule option CFTC-régulée, accessible sans VPN, fiscalement claire (actifs sur compte titres classique). Limitée à des indicateurs macroéconomiques/climat — pas de politique US ni de sports pour les comptes EEE.

---

## Partie 4 — Construire un SaaS analytics Polymarket

### 4.1 France / UE

**Scraping et API** : Polymarket expose trois APIs publiques (Gamma, CLOB, Data) sans authentification pour les endpoints read-only, des SDKs open-source (TS/Python/Rust), et un **Builder Program officiel** qui redistribue fees/volumes aux applications tierces. Signal explicite : **la construction d'outils tiers est encouragée**. Les ToS n'interdisent pas l'usage commercial des endpoints publics documentés. Jurisprudence clé : **hiQ v. LinkedIn** (9th Cir. 2019/2022) confirme que scraper des données publiques non authentifiées ne viole pas le CFAA, **mais** le breach of contract reste invocable si on crée un compte acceptant les ToS puis scrape au-delà (LinkedIn a gagné 500 k$ + injonction en décembre 2022). En UE, attention au **droit sui generis des bases de données** (Dir. 96/9/CE) et à la clause TDM opt-out (Dir. 2019/790, art. 4). Recommandation : **ne pas créer de compte Polymarket juste pour scraper** ; respecter les rate limits ; s'en tenir aux endpoints publics.

**RGPD et données on-chain** : la CNIL (2018) et l'**EDPB Guidelines 02/2025** (adoptées avril 2025) considèrent les adresses wallet, hashes, timestamps comme **données personnelles** au sens du RGPD. **Arrêt CJUE C-413/23 EDPS v. SRB** (4 septembre 2025) — *game changer* : approche **relative** de la pseudonymisation, la qualification dépend des moyens de ré-identification dont dispose effectivement l'acteur. Pour un SaaS sans outil Chainalysis/Arkham/Nansen, argument défensif que les wallets restent anonymes *dans ses mains*. Bonnes pratiques : éviter d'afficher ENS/identités, base légale **intérêt légitime** (art. 6-1-f RGPD), politique de confidentialité transparente, DPIA recommandée, droit d'opt-out du dashboard. Aucune plainte RGPD publique connue contre les dashboards Polymarket tiers existants (Polymarketanalytics, PolyTrack, etc.) en avril 2026.

**Structure juridique et fiscalité** :

- **Micro-entreprise BNC** : plafond **77 700 €**, abattement 34 %, cotisations URSSAF ~21-26 %. **Franchise TVA en services** : seuils **37 500 € (base) / 41 250 € (majoré)** en vigueur avril 2026 (le seuil unique 25 k€ initialement prévu par le PLF 2026 n'a pas été retenu — à vérifier au moment de la déclaration).
- **SASU à l'IS** : 15 % jusqu'à 42 500 € de bénéfice (conditions : CA < 10 M€, capital libéré 75 % PP), 25 % au-delà. Dividendes PFU 31,4 %. Président assimilé salarié (~75-80 % de charges sur rémunération brute).
- **EURL** : IR par défaut (option IS possible), gérant majoritaire TNS. Dividendes > 10 % capital soumis cotisations TNS.

**TVA SaaS** : B2C UE règle du lieu du client, **OSS** avec seuil 10 000 € de ventes intra-UE B2C ; B2B UE reverse charge si n° TVA intracom valide (VIES) ; hors UE en principe hors champ TVA française, mais attention **US state sales tax** (economic nexus) et DST UK.

### 4.2 International (cible US)

**CTA CFTC (7 USC § 1a(12))** : conseil sur commodity interests rémunéré = enregistrement potentiel. Les event contracts Polymarket US sont des **swaps régulés**. **Exemption *publisher*** (Lowe v. SEC, 472 U.S. 181 (1985), appliquée par analogie CFTC) : contenu impersonnel + publication bona fide + périodicité régulière = protection. Newsletter factuelle → safe. Signals individualisés → perd l'exemption. **De minimis CTA** : exempté si < 15 clients sur 12 mois et pas de holding out publiquement (Reg. 4.14(a)(10)).

**OFAC** : *strict liability* ; même depuis la France, servir un US person ou un SDN peut engager. Stack minimum : IP geoblocking pays sanctionnés (Iran, Corée du Nord, Cuba, Syrie, zones occupées Ukraine), SDN screening (sanctions.io, ComplyAdvantage ~50-200 €/mois), wallet screening (Chainalysis/TRM) si affichage on-chain, CGU excluant les sanctioned persons.

### 4.3 Copy-trading et signals : la zone grise

**Statut CIF (L. 541-1 CMF)** : concerne le conseil en *instruments financiers* (L. 321-1 CMF) ou biens divers. Position **AMF DOC-2020-02** : les actifs numériques ne sont pas des instruments financiers sauf s'ils sont assimilables à des titres (security tokens). **Conséquence** : le CIF n'est pas déclenché si les tokens Polymarket sont considérés comme crypto-actifs et non instruments financiers.

**Statut CASP sous MiCA** : l'article 3 MiCA donne une définition large (*digital representation of value or right, transferable, DLT*). Les tokens CTF entrent **vraisemblablement** dans cette définition. Services réglementés pertinents (annexe MiCA) : conseil sur crypto-actifs (service 7), gestion de portefeuille (service 8). **Analytics pur et publication factuelle : hors champ.** Signals personnalisés : risque CASP *conseil*. **Copy-trading automatisé : risque CASP *gestion de portefeuille*, agrément AMF requis.** L'ESMA a confirmé (Q&A 2463, Supervisory Briefing 35-42-1428 de mars 2023) que le copy-trading crypto relève du service 7 ou 8 selon configuration.

**Position AMF spécifique aux prediction markets** : **aucune** publiée en avril 2026. Zone de flou réglementaire explicite. Si requalification *options binaires* (instruments financiers MiFID II), **interdiction de publicité de l'article L. 533-12-7 CMF** s'applique (régime options binaires depuis 2017).

**Structuration** : pour un builder solo résident fiscal FR, **rester en structure française (SASU/EURL/micro) est la recommandation n°1**. Toute structure étrangère sans relocation physique effective expose à **l'article 209 B CGI** (CFC) et à une requalification pour *établissement stable en France* ou *place of effective management* :

| Structure étrangère | Taxation | Risque 209 B |
|---|---|---|
| Delaware/Wyoming LLC | Transparent IRS, mais 209 B si détention > 50 % et taxation privilégiée | **Fort** |
| Estonie OÜ (e-Residency) | 22 % sur distribution (hausse 2025) | Atténué UE (Cadbury Schweppes 2006) mais substance requise |
| Dubai (DIFC/IFZA/ADGM) | 9 % corporate tax (UAE, juin 2023) | **Fort** : IS < 60 % du taux FR → présomption régime privilégié |

**Pilier 2 OCDE** (taux minimum 15 %, art. 223 VJ-VZ CGI) ne s'applique qu'aux groupes > 750 M€ CA consolidé — **hors sujet pour un solo-builder**.

### 4.4 Positionnement produit recommandé

**Tier "safe"** : dashboards factuels, leaderboards anonymisés, statistiques historiques, back-testing, alertes impersonnelles par seuils publics, newsletter éditoriale régulière.

**Tier "risqué" à éviter solo sans conseil juridique** : recommandations personnalisées utilisateur par utilisateur, signals "buy now" à audience individualisée, auto-copy-trading (exécution pour le compte du client), gestion discrétionnaire.

---

## Partie 5 — Risques opérationnels côté Polymarket

**Freeze de fonds et ban de wallets** : Polymarket est techniquement non-custodial (fonds dans un Gnosis Safe contrôlé par l'utilisateur), ne peut donc pas saisir les USDC on-chain, mais peut **bloquer l'interface**, **geler le trading** via wallet analysis, **bannir des wallets** pour Sybil/wash trading, insider trading, ou accès depuis juridiction restreinte. Les **Enhanced Market Integrity Rules** (23 mars 2026) précisent 3 catégories d'insider trading prohibé ; sanctions possibles : suspension, termination, pénalités monétaires, référence aux autorités.

**Hack Magic Labs (22-24 décembre 2025)** : exploitation d'une vulnérabilité du provider d'authentification tiers. Vidage de wallets signalé par plusieurs utilisateurs. Polymarket a confirmé sans divulguer le nombre d'utilisateurs ni le montant volé. **Leçon : self-custody impérative** — exporter la clé Magic Link depuis reveal.magic.link/polymarket, l'importer dans MetaMask/Rabby, idéalement avec un hardware wallet Ledger/Trezor.

**Controverses de résolution UMA** : le pattern récurrent est le risque *oracle* plus que le risque *smart contract*. Cas documentés :

- **Barron Trump / $DJT** (juin 2024, >1 M$) : UMA résout NO à plusieurs reprises ; Polymarket **passe outre** et rembourse les YES sans preuves publiques. Précédent où la plateforme contredit son oracle.
- **Ukraine Trump mineral deal** (mars 2025, ~7 M$) : wallet "BornTooLate.eth" accumule ~1,3 M tokens UMA (top-5 staker) et force la résolution YES malgré absence d'accord ; Polymarket **refuse les remboursements**. Premier cas documenté de *capture d'oracle* par une whale.
- **Zelensky suit before July** (juillet 2025, ~160-237 M$ de volume) : résolution finale NO malgré couverture médiatique majoritairement YES ; prix YES chute de 0,19 $ à 0,04 $ ; communauté rejette les propositions de réexamen.
- **Myrnohrad / ISW** (14 novembre 2025) : source de résolution (ISW) se trompe sur une avance russe ; marché résout avant correction.

**Mécanisme UMA DVM** : bond proposer ~750 USDC, challenge period 2 h, escalade vers vote token-weighted sur 48 h. Faiblesses : concentration UMA tokens, résolutions subjectives ambiguës, Polymarket peut remboursement ad hoc (arbitraire).

**Clarifications rétroactives** : système officiel de bulletin board updates. Exemples : Musk/DOGE (17 février 2025), TikTok ban. Source récurrente de contestations utilisateurs — Polymarket les présente comme pré-annoncées, les utilisateurs les perçoivent rétroactives.

**Stratégies de protection** :

1. Self-custody dès le départ, idéalement avec hardware wallet et export de la clé Magic Link si déjà créé.
2. Sortir régulièrement les USDC.e vers un wallet externe entre sessions (prévoir bridge USDC.e → USDC natif pour retrait CEX).
3. Multi-wallets avec parcimonie — les règles de mars 2026 renforcent la détection Sybil.
4. Lire les résolution rules AVANT de prendre position, éviter les marchés à résolution subjective (fashion, *involvement*, *consensus of credible reporting*).
5. Ne pas laisser de solde dormant pendant les disputes (3-6 jours de trading gelé possibles).
6. Surveiller Discord Polymarket et #voting-discussion UMA en cas de position significative.
7. Pas de VPN pour contourner le géoblocage : wallet analysis peut détecter et geler.

---

## Partie 6 — Recommandations pratiques actionnables

### Checklist "100 % clean" trader français

1. **Privilégier IBKR ForecastEx** via Interactive Brokers Ireland si le périmètre macro/climat suffit — seule voie réglementée accessible sans VPN.
2. Si usage Polymarket International : comprendre que c'est une zone grise, pas une infraction pénale du joueur, mais expose fiscalement et contractuellement.
3. **Déclarer le compte Polymarket sur 3916-bis** (Adventure One QSS Inc., Panama) sans attendre un seuil, chaque année.
4. **Imposer les gains via formulaire 2086 au PFU 31,4 %** (150 VH bis) sur les cash-out EUR — c'est la position la plus défensive.
5. Conserver **traçabilité exhaustive** : historique on-chain Polygon, screenshots Polymarket, relevés PSAN pour flux EUR↔USDC. Outils : Waltio, Koinly.
6. **Self-custody** des fonds entre sessions, hardware wallet, export clé Magic si utilisée.
7. Éviter marchés à résolution subjective et gros soldes pendant disputes.

### Seuils de consultation professionnelle

- **> 5 000 € gains/an** : consulter avocat fiscaliste (ORWL, Revo, Bornhauser, Strategia, Odessa).
- **> 20 000 € gains/an ou activité régulière** : consultation obligatoire pour arbitrer entre PFU et BNC.
- **Activité pro à temps plein ou structuration entrepreneuriale** : avocat + expert-comptable spécialisés crypto.

### Setup recommandé builder SaaS

**Phase MVP (CA < 50 k€)** : micro-entreprise BNC, franchise en base TVA, activité « services informatiques » ou « édition logicielle », pas de KYC si B2C simple, politique de confidentialité RGPD basique (intérêt légitime), OFAC geoblocking via Cloudflare, positionnement **analytics pur**.

**Phase scale (CA 50-200 k€)** : SASU à l'IS ou EURL IS (~1 500 € création), TVA obligatoire, OSS pour B2C UE, comptable trimestriel (~2 500-4 000 €/an), RC Pro (500-1 500 €/an), sanctions.io pour screening, consultation avocat avant tout lancement signals/copy-trading.

**Zones à éviter solo sans conseil** : copy-trading automatique (risque CASP gestion de portefeuille), signals personnalisés adressés individuellement, structuration offshore sans relocation physique effective (risque CFC 209 B).

### Roadmap compliance scale

1. **Month 0-6** : analytics public, disclaimer *information only*, geoblocking pays sanctionnés, CGU claires.
2. **Month 6-12** : ajout KYC light pour abonnements payants, sanctions screening, DPIA RGPD.
3. **Month 12-24** : si signals envisagés, audit avocat, positionnement éditorial impersonnel (exemption publisher Lowe v. SEC).
4. **Au-delà** : si copy-trading : soit agrément CASP AMF, soit licence DCM US (hors de portée solo), soit pivot vers pure analytics B2B institutionnel avec licences de données (modèle du ICE-Polymarket Signals feed).

---

## Conclusion : trois prises de position

**D'abord, la fiscalité prime sur la légalité administrative** pour le trader individuel français. L'ANJ a déclaré Polymarket illégal ; le fisc français n'a aucune position publiée. La position défensive robuste en 2026 est **PFU 31,4 % sur actifs numériques** via 2086, avec déclaration 3916-bis systématique. Cette approche cumule deux avantages : elle impose (donc neutralise l'argument d'activité occulte) et elle ne dépend pas de la qualification contestée des tokens YES/NO.

**Ensuite, la double vie de Polymarket change la donne internationale** mais pas le cadre français. L'obtention du DCM CFTC via QCEX et l'investissement ICE/NYSE de 2 Md$ donnent à Polymarket US une légitimité institutionnelle sans précédent, mais l'ANJ n'a montré aucun signe d'assouplissement et MiCA n'harmonise pas les jeux d'argent. Un builder SaaS international doit raisonner en **double cadre** : France/UE (CASP possible si copy-trading, CIF hors sujet) et US (exemption publisher robuste si produit impersonnel, CTA si signals personnalisés).

**Enfin, la bonne zone de valeur pour un builder français est l'analytics B2B institutionnel ou éditorial grand public, pas le copy-trading solo**. Le partenariat ICE-Polymarket *Signals and Sentiment* lancé en février 2026 confirme que les données Polymarket deviennent une classe d'actifs d'information à part entière. Un produit de dashboards, backtests, newsletter analytique, éventuellement API value-added, reste largement réalisable depuis une micro-entreprise française, avec une trajectoire naturelle vers SASU IS dès 60-80 k€ de CA. Tant qu'on résiste à la tentation du signal individualisé et du copy-trading automatisé, le cadre réglementaire est praticable. Dès qu'on les franchit, il faut soit un avocat spécialisé, soit un agrément, soit un pivot.