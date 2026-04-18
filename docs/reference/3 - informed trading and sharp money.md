# Corpus documenté de trading informé et sharp money sur Polymarket

**Bottom line up front**: ce rapport rassemble **18 cas forensiques documentés** de trading informé, sharp money et manipulation sur Polymarket (2022-2026), avec adresses wallet Polygon, montants USDC, timing et sources. Le corpus couvre un spectre allant du cas benchmark "French Whale Théo" (~$85M profit sur 11 wallets) au trading présumé d'insiders gouvernementaux sur les strikes US-Iran (février 2026, ~$1.2M) en passant par des cas niche révélateurs (Nobel Peace Prize, conclave papal, Super Bowl halftime, Google Year in Search). Les patterns on-chain récurrents (**fresh wallet < 30 jours**, **concentration > 90% sur un outcome**, **shared CEX deposit address**, **entry à implied prob < 20% dans une fenêtre < 48h avant event**) produisent une heuristique de détection robuste, tempérée par trois limites structurelles : bonnes OpSec (Railgun correct, mules KYC, OTC) restent indétectables ; ~25% du volume historique est wash trading (Columbia 2025), polluant toute feature basée sur volume ; et la même signature peut refléter conviction informée légitime (Théo) ou insider trading pur (Biden pardons).

---

## Partie I — Fiches forensiques par cas

### Cas 1 — The French Whale "Théo" (Fredi9999, Theo4, PrincessCaro, Michie)

**Période** : septembre-novembre 2024. **Marchés** : Presidential Election Winner 2024, Popular Vote Winner, swing states (PA, MI, WI, GA, AZ, NC). Volume cumulé du marché présidentiel : ~$3,7 Mds.

**Wallets (4 publiquement confirmés par Polymarket 24 oct 2024 + Reuters, Bloomberg, WSJ)** :
- **Fredi9999** : `0x1f2dd6d473f3e824cd2f8a89d9c69fb96f6ad0cf`
- **PrincessCaro** : `0x8119010a6e589062aa03583bb3f39ca632d9f887`
- **Theo4** : `0x56687bf447db6ffa42ffe2204a05edaa20f55839`
- **Michie** : adresse 0x complète **non publiée publiquement** (confirmée par Reuters/Polymarket comme 4e compte du cluster ; récupérable via API Polymarket `/public-profile`)

**Chainalysis (7 nov 2024)** a étendu le cluster à **9 wallets confirmés + 10e wallet ajouté** (+$4,8M profit) + **11e wallet suspecté non confirmé** (+$2,1M). Les adresses 0x au-delà des 4 initiaux n'ont jamais été publiées publiquement par Chainalysis (données propriétaires).

**Montants** :
- Exposition initiale ~$28M (24 oct) → ~$45M (28 oct) → $52M (fin oct, Harry Crane "Fredi9999 Tracker")
- **Profit final : $85,6M selon Chainalysis** (9 wallets = $78,7M + 10e = $4,8M + 11e suspecté = $2,1M)
- Dépôts depuis **Kraken**, tranches de $500K-$1M
- Jusqu'à **71 bets/minute**, **2 500 bets/24h** (fragmentation anti-impact)
- Trade signature sur popular vote : 26% → 39% en quelques heures (Domer, 16 oct)

**Timeline (Domer threads X/Twitter)** :
- 7 oct 2024 : première identification publique de Fredi9999 par @Domahhhh comme largest Trump holder (~7,2M shares, $6,4M positions) → https://x.com/Domahhhh/status/1843320398735106155
- 15-16 oct : cluster à 4 accounts identifié par @Domahhhh et @fozzydiablo → https://x.com/Domahhhh/status/1846597997507092901
- 18 oct : WSJ "Mystery Polymarket Trader Bets Millions on Trump" (Alexander Osipovich)
- 24 oct : NYT DealBook identifie nationalité française ; Polymarket publie statement "no evidence of manipulation"
- 1 nov : WSJ interview anonyme de Théo ("extensive trading experience, financial services background") — méthodologie **YouGov "neighbor poll"** pour capturer shy Trump voters dans PA, MI, WI
- 6-7 nov : Chainalysis publie cluster étendu à 9→10→11 wallets

**Méthodologie clustering Chainalysis** : fusion sur 3 vecteurs conjoints — (1) funding patterns communs, (2) timing synchrone, (3) **cash-out vers mêmes adresses de dépôt CEX** (vecteur le plus discriminant).

**Outcome** : Trump gagne présidence + 7 swing states + popular vote. **Thèse "edge réel"** (Matt Levine, Polymarket, Théo) validée rétrospectivement. Polymarket capitalise le récit "prediction markets > polls", ce qui précède l'investissement ICE de $2Mds (oct 2025).

**Enseignements détection** : le cluster Théo reste le **benchmark d'ambiguïté** — les mêmes patterns on-chain (multiplication wallets, concentration extrême, funding CEX structuré) peuvent refléter conviction informée légitime OU manipulation OU insider. Le post-mortem seul a permis de trancher ; un détecteur real-time aurait produit une alerte indistinguishable d'un insider pur.

**Sources clés** : WSJ Osipovich (https://www.wsj.com/finance/polymarket-election-trader-trump-a5e58cab) ; DealBook (https://www.nytimes.com/2024/10/24/business/dealbook/polymarket-trump-trader.html) ; Chainalysis thread (https://x.com/chainalysis/status/1854294962147364961) ; Free Press Nocera (https://www.thefp.com/p/french-whale-makes-85-million-on-polymarket-trump-win) ; Polymarket Hidden Wealth (https://hiddenwealth.polymarket.com/markets/french-whale-7-31-25) ; CBS 60 Minutes.

---

### Cas 2 — Iran strikes US-Israël (28 février 2026) — "Operation Epic Fury"

**Marché** : "US strikes Iran by February 28, 2026?" ($90M volume spécifique, ~$529M cumulé toutes échéances Iran).

**Cluster de 6 wallets Bubblemaps** (thread X 28 fév 2026, id 2027718004193300791) :

| Wallet / Username | Position | Profit net | Notes |
|---|---|---|---|
| `0x1caA6a7ad0c6916aeF7b67946De2e57Ad24846a0` | 560 680 "Yes" shares @ ~$0,108 | **~$494 375** (payout ~$560K) | plus gros gagnant du cluster |
| `0xa4eb52229991c074bc560f825bf2776d77acd010` (nothingeverhappens911) | — | — | lié à cluster "Skoobidoobnj" via dépôt Binance partagé |
| `0x3811e09bb2fa30aff16d9be28c09ee9bba478f61` | — | — | — |
| @Dicedicedice | 150 000 shares @ $0,20 | **~$120 000** | — |
| @Neodbs | — | — | — |
| @Planktonbets | — | — | — |
| Anon (6e) | 55 556 "Yes" @ 18¢ | **+$45 556** (ROI +456%) | concentration 100% un seul contrat |

**Total combiné net (The Block review)** : **$989 191** (Bubblemaps annonçait $1.2M avant corrections).

**Wallet séparé "Magamyman"** (https://polymarket.com/@magamyman, adresse 0x non publiée mais récupérable via API) :
- Compte actif depuis octobre 2024 (pas fresh — camouflage par activité organique)
- +$431 146,10 sur strike 28 fév + $143 321,30 sur Khamenei out 31 mars = **~$574K/jour**
- **Premier trade 71 minutes avant l'annonce publique** à implied prob ~17%, position ~$87K
- Rep. Mike Levin (D-CA) a demandé publiquement enquête sur ce profil

**Cluster étendu CNN/Bubblemaps (24 mars 2026)** : 38 comptes présumés d'une seule personne, nets >$2M sur strikes du 28 fév ; pre-funding depuis le 22 février. Un autre cluster affiche 93% win-rate sur wagers 5 chiffres concernant opérations militaires non annoncées depuis oct 2024 (Israel strikes), juin 2025 (Fordow US airstrikes) et fév 2026.

**Contre-exemple instructif** : un wallet qui avait accumulé +$2M en pariant "No" sur strikes a perdu **$6,5M en un seul jour** post-attaques (Lookonchain) — montre que le "informed edge" n'est pas partagé uniformément.

**Suites régulatoires** : Rep. Ritchie Torres dépose H.R. 7004 (Public Integrity in Financial Prediction Markets Act of 2026) ; enquête CFTC active ; ex-employé Polymarket suspecté (non confirmé).

**Sources** : The Block (https://www.theblock.co/post/391650) ; CoinDesk (https://www.coindesk.com/markets/2026/02/28/suspected-insiders-make-over-usd1-2-million-on-polymarket-ahead-of-u-s-strike-on-iran) ; Bloomberg ; CNN (https://www.cnn.com/2026/03/24/politics/iran-war-bets-prediction-markets) ; NPR ; Mitts & Ofir SSRN paper (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6426778).

---

### Cas 3 — Maduro capture (4 janvier 2026) — "Operation Absolute Resolve"

**Marché** : "Maduro out by January 31, 2026?" — côté 5-7¢ pendant des semaines avant de spiker quelques heures avant capture.

**Trois wallets fresh (Lookonchain X, tweet id 2007639475497881625)** — profit combiné **$630 484** :

| Wallet | Username | Investi | Profit | Timing |
|---|---|---|---|---|
| `0x31a56e9E690c621eD21De08Cb559e9524Cdb8eD9` | Burdensome-Mix | ~$32-34K | **~$409 882** | dernier bet à 21:58 ET vendredi, <5h avant explosions Caracas |
| `0xa72DB1749e9AC2379D49A3c12708325ED17FeBd4` | — | ~$5 800 | ~$75 000 | — |
| SBet365 (0x non publiée) | SBet365 | ~$25 000 | ~$145 600 | — |

**Profils Polymarket publics** :
- https://polymarket.com/@0x31a56e9E690c621eD21De08Cb559e9524Cdb8eD9-1766730765984
- https://polymarket.com/@0xa72DB1749e9AC2379D49A3c12708325ED17FeBd4-1766534754187

**Signatures insider** : tous 3 fresh + pre-funded quelques jours avant, activité exclusivement Venezuela/Maduro, **94% win-rate**, aucune obfuscation (cashout via CEX US mainstream — funding via flux Coinbase-linked selon tracer Andrew "10 GWEI"). **Bubblemaps a démenti publiquement** le 5 janvier les rumeurs liant Burdensome-Mix à un cofondateur de WLFI.

**Sources** : Lookonchain (https://x.com/lookonchain/status/2007639475497881625) ; NPR (https://www.npr.org/2026/01/05/nx-s1-5667232/polymarket-maduro-bet-insider-trading) ; Fox Business ; CryptoSlate.

---

### Cas 4 — Axiom / ZachXBT reveal (26-27 février 2026) — "Market designed to catch insiders, itself insider-traded"

**Marché** : "Which crypto company will ZachXBT expose for insider trading?" (28 outcomes, ~$40M volume). Meteora était favori >50% toute la semaine ; Axiom grimpe tard mercredi (pic 46,2% pré-publication).

**Wallets insider identifiés** :

| Wallet | Username | Position | Profit |
|---|---|---|---|
| `0x1d9af60c679cd0b577c3c4ccb4b1a4be4174426d` | predictorxyz (aka "JustADegen" sur Fomo, trader CRABS selon ZachXBT) | 477 415 "Yes Axiom" @ avg $0,14 | **$411 600** (~7x) |
| `0x054eC2F0cCf...` (tracé Bubblemaps vers Broox/@WheresBroox via wallet FarpaW) | — | 212K "Yes" @ $0,33 (+ "No" en camouflage) | **~$421 000** |
| Anon | — | 109 450 @ $0,33 pre-reveal | — |
| 2 autres addresses | — | 1 market only each | +$354 000 et +$144 000 |

**Total flaggé** : Lookonchain 12 wallets = **>$1M combined** ; Polysights 5 wallets = $50K → $266K ; BeInCrypto estime **8 des top 10 earners** sont insiders.

**Statistique frappante** : **56,2% des 3 630+ adresses profitables** (anormalement élevé pour un marché 2-outcomes). 52 adresses perdent $10K-$100K+ (>$1,6M cumulé).

**Note méthodologique** : ZachXBT a reconnu avoir contacté Axiom et mené interviews avant publication — leak "probably inevitable". Le wallet `0x054e` a acheté simultanément "Yes" ET "No" comme **technique de camouflage classique insider** (split hedge).

**Source principale** : CoinDesk (https://www.coindesk.com/markets/2026/02/27/polymarket-bettors-appear-to-have-insider-traded-on-a-market-designed-to-catch-insider-traders) ; BeInCrypto ; Bubblemaps threads.

---

### Cas 5 — Biden pardons (décembre 2024 - janvier 2025)

**Marchés** : "Who will Biden pardon?" (sous-marchés : Hunter Biden, Fauci, Milley, Liz Cheney, Adam Schiff, Adam Kinzinger, Jim Biden).

**2 comptes Bubblemaps/NPR (16 avril 2026)** : perfect track record, **reliés par shared Kraken deposit wallet** (signature forensique clé selon Nicolas Vaiman/Bubblemaps).

**P&L agrégé** :
- ~$64 000 placés sur 4 pre-emptive pardons (Jim Biden, Liz Cheney, Schiff, Kinzinger) à implied prob "près de zéro"
- Profit séparé sur Hunter Biden pardon (1er décembre 2024 — charges gun & tax)
- **Total 5 bets : $316 346 profit** (chiffre Bubblemaps exclusif NPR)

**Adresses 0x complètes non publiées** — screenshot NPR masque l'adresse ; récupérable via polymarket.com/event/who-will-biden-pardon trader leaderboard.

**Citation Joshua Mitts (Columbia Law, advisor DOJ)** : *"The odds of this happening by random chance are virtually zero."* Hypothèse : White House insider. Cas phare pour l'argument légal que l'insider trading sur MNPI gouvernementale devrait tomber sous **wire fraud** même si CFTC Rule 180.1 est inapplicable.

**Sources** : NPR via KPBS (https://www.kpbs.org/news/politics/2026/04/16/a-polymarket-trader-made-300-000-betting-on-bidens-pardons-a-new-analysis-shows) ; Mitts & Ofir SSRN.

---

### Cas 6 — Nobel Peace Prize 2025 (Maria Corina Machado, 10 octobre 2025)

**Marché** : "2025 Nobel Peace Prize Winner" sur Polymarket. Machado cote ~3,6% (≈$0,08) pendant des mois.

**Contexte insider** : comité Nobel a décidé **le 6 octobre** ; annonce publique **10 octobre 11h00 CEST**. Fuite intervient à partir de **minuit norvégien du 9 octobre** (~11h avant annonce). Odds : 3,6% → 70%+ en heures.

**3 comptes identifiés (profits cumulés ~$90 000)** :

**(a) Compte "6741"** :
- Créé 24h avant le surge
- Mise $2 000 → **profit $53 000-$53 500**
- Petits contre-paris sur Navalnaya, Thunberg, Assange (tentative d'obfuscation)

**(b) Compte "dirtycup"** (whale) :
- Créé "quelques semaines" avant ouverture du marché, aucun historique
- **Bet $68 117-$70 000 YES Machado à 03:41 UTC le 10 octobre** (~5h20 avant annonce), cotes <15%
- Profit ~$30-34K
- Signalé par @PolyWhaleWatch le 9 oct (https://x.com/PolyWhaleWatch/status/1976499384373121488)

**(c) 3e compte** : profit ~$10-15K complémentaire.

**Adresses 0x complètes** : non publiées dans la presse norvégienne/internationale consultée.

**Enquête officielle ouverte** : Norwegian Nobel Institute (Erik Aasheim, porte-parole). Directeur Kristian Berg Harpviken : initial "prey to a criminal actor" → révisé à "**espionage highly likely**" (cyber-breach probable, pas fuite humaine). Premier reportage : Aftenposten + Finansavisen, repris par Bloomberg.

**Sources** : CoinDesk (https://www.coindesk.com/markets/2025/10/11/norwegian-officials-probe-major-polymarket-bets-on-nobel-peace-winner) ; The Block ; Blockworks.

---

### Cas 7 — Conclave / Pope Leo XIV (Robert Prevost, 8 mai 2025)

**Marché** : "Next Pope?" ($30M+ volume Polymarket + $10,6M Kalshi = $40M+ combiné). Prevost coté ~1% avant élection (12e-13e place).

**Timeline forensique (témoignage Paul Wood, The Spectator)** : vers 19h heure Rome, pendant que Prevost revêt la soutane blanche mais **avant son apparition physique au balcon**, les odds Polymarket explosent de ~1% à ~100%. Wood a placé un $20 bet sur Prevost et a vu son gain potentiel chuter de $6 776 → $5 911 → $4 704 → $3 900 → $2 800 → $2 100 → $1 700 en quelques minutes **avant** l'annonce publique. Son bet final résolu à +13 977%.

**Autres trades documentés** :
- **Domer** (@Domahhhh) : longshot Prevost, profit ~$100 000 (recherche via interviews cardinaux, sharp money pur — pas insider)
- Trader anonyme : $1 000 → $64 000 sur Prevost + $55 000 NO sur Parolin

**Hypothèse Wood** : le jamming électronique Sistine bloque communications depuis le conclave, mais une fois les portes ouvertes, personnel Vatican, Garde Suisse, ou observateur visuel peut avoir déclenché les gros ordres. **Adresses 0x non identifiées publiquement**.

**Sources** : The Spectator (https://thespectator.com/topic/who-made-money-from-the-new-pontiff-pope/) ; CNBC (https://www.cnbc.com/2025/05/10/online-bettors-spent-over-40-million-gambling-on-identity-of-next-pope.html) ; CNN ; CoinDesk.

---

### Cas 8 — Super Bowl LX halftime show (Bad Bunny, 8 février 2026)

**Marché** : série de contracts binaires "Will [artiste] perform at Super Bowl LX halftime?" (Lady Gaga, Ricky Martin, Chappell Roan, etc.).

**Wallet** : **`0x40d9ac81a425f14d2c490c41ac8969c0cbcfd472`** (alias "Anon")
- **Créé le 7 février 2026** (≈24h avant kickoff 8 février)
- Trading **exclusivement** sur SB LX halftime markets
- **$47 000 déployés** au flagging
- Plus gros holder Lady Gaga : **24 000 shares YES** (>90% malgré aucune confirmation officielle)
- **Track record : 17 correct sur ~20 paris** (Lady Gaga YES +25% / $4 940, Ricky Martin YES, etc.)
- **Profit total ~$17 000**
- Signalé par @JeongHaeju (Meta engineer) le 8 fév 2026 01:24 ET

**Autre signal** : Esoteric Catboy observe $500 000 slammés sur Lady Gaga par un autre participant juste après ses ordres NO (second cluster possible).

**Analyse** : guest list halftime show connue de centaines de personnes (production, talent, wardrobe, security, transport). Insider "production side" très plausible (pas forcément NFL insider).

**Sources** : Benzinga (https://www.benzinga.com/markets/prediction-markets/26/02/50471679/lady-gaga-ricky-martin-appearances-nailed-by-suspicious-insider-polymarket-trader-raises-questions-on-super-bowl-halftime-show-bets) ; Polymarket profile page (https://polymarket.com/profile/0x40d9ac81a425f14d2c490c41ac8969c0cbcfd472?tab=positions) ; Futurism ; Covers.

---

### Cas 9 — Google Year in Search 2025 / "AlphaRaccoon" (décembre 2025)

**Marché** : "Google Year in Search 2025 / Most Searched Person" + ~22 autres marchés Google Trends.

**Wallet** : **`0xafEe...`** (alias "AlphaRaccoon", renommé ensuite pour fuir attention)
- Dépôt **$3M USDC** sur Polymarket le vendredi précédent les résolutions
- **22/23 prédictions correctes**
- Trade phare : YES sur **d4vd** (chanteur 20 ans, coté 0,2% avant surge) → $10 647 → ~$200 000
- NO massif sur favoris (Pope Leo XIV, Bianca Censori, Donald Trump, Zohran Mamdani)
- YES Charlie Kirk "most searched passing" ; NO Sydney Sweeney "most searched actor"
- **Profit total ~$1 000 000 - $1 150 000 en 24h**
- Historique antérieur (novembre 2025) : ~$150 000 sur date release Google Gemini 3.0 Flash

**Mécanisme probable (Haeju, 4 déc 2025)** : *"Google accidentally pushed the results early, then removed them, but not before it revealed he went 22/23..."* — exploitation d'un **leak technique** via scraping staging API (cf. aussi cas Spotify infra). Alternative : insider Google avec accès données ranking pré-publication.

**Ironie** : **Polymarket Money account officiel** a amplifié le cas ("Who is AlphaRaccoon?"), soulevant des questions éthiques sur l'exploitation commerciale d'un cas d'insider présumé.

**Sources** : Yahoo Finance ; The Defiant ; Gizmodo (https://gizmodo.com/polymarket-user-accused-of-1-million-insider-trade-on-google-search-markets-2000696258) ; DefiRate.

---

### Cas 10 — Spotify Wrapped 2025 ("The Weeknd #3", 3 décembre 2025)

**Marché** : Top 10 Spotify Wrapped 2025, "Who will be #3 most-streamed artist?".

Stats publiques pré-annonce avaient **Drake #3**. Résultat réel : **The Weeknd #3**. Cote passe de ~40% à 99% quelques heures avant annonce.

**Trade signature** : fresh account, **$800 de shares YES à ~3¢** → gains majeurs à $1 (conversion ~33x).

**Total trades suspects identifiés** : **$3 162 695** (analyse Itay Yakobov, "The $3.16M Backend Heist").

**Mécanisme documenté (Yakobov + @fireplacegg)** : Spotify newsroom blog tourne sur **WordPress hébergé Google Cloud Storage bucket "pr-newsroom-wp"** ; les traders ont scrapé un **fichier staging API publiquement accessible** exposant les résultats réels avant publication. **Ce n'est pas insider au sens strict** — données techniquement publiques mais non publicisées. Exemple parfait de **sharp money via OSINT offensif**.

**Réaction Polymarket (X, 2 déc 2025)** : **célébration publique** de l'incident — "prediction markets work". Cadrage controversé.

**Sources** : https://x.com/Polymarket/status/1995918628689248596 ; DefiRate ; threads @fireplacegg.

---

### Cas 11 — Ricosuave666 / Israel strikes Iran

**Wallet** : **`0x0afc7ce56285bde1fbe3a75efaffdfc86d6530b2`** (adresse complète publiée)

**Track record** :
- Profits pre-2026 : **$155 699,12 sur bets Israel-related, 100% win rate**
- Actif lors des strikes israéliens **juin 2025** — profit ~$152K sur 4 bets (3 sur timing début + 1 sur timing fin)
- Après 7 mois d'inactivité : retour avec $8 198 sur "Israel strikes Iran" Jan 31 / Mar 31 2026, odds à l'entrée ~21%

**Indictment israélien (février 2026, confirmé)** : **IDF reservist + civilian** inculpés par Israel Security Agency pour "severe security offenses", bribery, obstruction. Profits ~$150K+ via info classifiée IDF. **Washington Examiner identifie ricosuave666 comme l'un des deux inculpés** — premier cas de prosecution effective pour insider trading via info gouvernementale classifiée sur Polymarket.

**Ricosuave666 est depuis deleted sur Polymarket** — concept drift en réponse à la détection publique.

**Sources** : Lookonchain (https://x.com/lookonchain/status/2008723345844662575) ; Dyutam (https://dyutam.com/news/polymarket-israel-iran-conflict-insider-trading/) ; Times of Israel (https://www.timesofisrael.com/two-indicted-for-using-classified-info-to-place-online-bets-on-military-operations/) ; Washington Examiner.

---

### Cas 12 — Taylor Swift / Travis Kelce engagement (27 août 2025)

**Marché** : "Taylor Swift and Travis Kelce engaged in 2025?" — ~$385K volume total avant résolution Yes.

**Wallet** : "romanticpaul"
- Activité totale : $1,61M volume cumulé sur 290 markets, **net lifetime -$4 885** avant ce trade
- Adresse 0x complète non publiée (récupérable via API)

**Trade** : achat aggressif "Yes" **15-24h avant l'annonce Instagram** ("Your English teacher and your gym teacher are getting married"). 5 180 shares rachetées → payout $5 180,42. **Profit >$3 000**. L'achat fait monter prix share de 25¢ à 40¢.

**Indices insider** : account avec historique de pertes nettes → trade isolé profitable sur event insider-plausible. Engagement réel ~2 semaines avant annonce selon David Muir/père Kelce — fenêtre info privée existait dans l'entourage. X users ont pointé **Paul Sidoti** (guitariste tour Swift, "closest Paul").

**Enjeu légal** : info non commerciale → **wire fraud fragile** (cf. Mitts/Ofir). Cas emblématique de l'ambiguïté juridique des prediction markets.

**Sources** : Benzinga (https://www.benzinga.com/crypto/cryptocurrency/25/08/47367927/) ; CoinDesk ; PokerScout (https://www.pokerscout.com/insider-trading-on-polymarket-foretold-taylor-swifts-engagement/).

---

### Cas 13 — Pope Francis decease (21 avril 2025)

**Marchés** : "New Pope in 2025?" (~$3M volume à résolution), "Will Pope Francis step down before July?", "Will Pope Francis remain Pope through June 30?".

**Wallet "syncope"** : 26 266 shares YES @ avg 56¢ sur "New Pope 2025?" → **profit >$11 500** (sharp money actuariel sur risque public, pas insider).

**Hoax post-résolution** : le 23 avril 2025, post @Yoxic sur X fausse rumeur "Vatican denounces Polymarket" fait grimper volume "Next Pope" de $2,5M → $6,4M en 48h (+152%). **Manipulation de sentiment** (pas insider au sens strict).

**Pas de cas d'insider documenté** sur l'annonce de décès elle-même — Salle de Presse Vatican communique rapidement.

**Source** : DL News (https://www.dlnews.com/articles/markets/pope-francis-passing-triggers-payout-for-polymarket-bettors/).

---

### Cas 14 — Derivative market manipulation Sethi (6 septembre 2024)

**Niveau de preuve : DÉMONTRÉ** (tentative forensique ratée)

**Marché dérivé** : "Favorite to win on Polymarket on Friday" — payait $1 si Harris majorité des 180 minutes 12h-15h EST le 6 sept.

**Mécanique** : acheter massivement Harris / shorter Trump dans primary market pour pousser Harris en tête artificiellement pendant fenêtre 3h, tout en détenant positions dérivées pré-constituées à ~3¢ (qui atteindraient >$0,20 si succès).

**Traces on-chain (@Dumpster_DAO, X)** :
- 1 trader unique : **~$2,5M dans primary market**
- 2e trader (lié) : ~$11 000 buying derivative contracts à avg 8¢, ~140 000 contrats
- P&L potentiel si réussi : ~$130 000 sur derivative + **6-figures net** sur $2,5M primary

**Outcome** : manipulation **échoue**. Le primary market rebound rapidement.

**Argument Rajiv Sethi** : *"I see no rationale for such derivative contracts. They serve no legitimate purpose and open up rather obvious strategies for manipulation."* → recommande suppression de ce type de contrats dérivés.

**Réaction Polymarket** : aucune. Contrats dérivés similaires continuent d'être listés.

**Source** : https://rajivsethi.substack.com/p/a-failed-attempt-at-prediction-market ; https://x.com/Dumpster_DAO/status/1832148090452898235.

---

### Cas 15 — XRP / a4385 (17 janvier 2026) — Cross-market "banging the close"

**Niveau de preuve : DÉMONTRÉ** (trader revendique stratégie)

**Marché** : "Will XRP rise or fall between 12:45 PM ET and 1:00 PM ET on Jan 17?"

**Wallet/pseudonyme** : @a4385 (X)

**Méthode (5 étapes)** :
1. Samedi soir (thin liquidity) : achat aggressif "UP" shares, push prix à 70¢ malgré XRP spot -0,3%
2. Market-making bots vendent plus de "UP" shares sans considérer spot
3. Accumulation : **77 000 UP shares @ avg 48¢**
4. **2 minutes avant settlement** : achat $1M XRP spot → push spot +0,5%
5. Marché settle "UP" → redemption $1/share ; revente XRP spot immédiatement

**P&L** : **~$233 000 profit net**. Cost opérationnel ~$6 200. Les bots AMM ont "perdu un an de profits en une nuit".

**Classification** : **cross-market manipulation / "banging the close"** — illégal en TradFi (CFTC/SEC prohibent). Zone grise offshore. **Technique réplicable** sur tous les thin weekend markets Polymarket. Chris Tremulis (Goldman Sachs, Global Head Commodities Compliance) : appel à "stronger rulebook enforcement".

**Source** : CoinMarketCap Academy (https://coinmarketcap.com/academy/article/polymarket-trader-nets-dollar233k-exploiting-weekend-liquidity).

---

### Cas 16 — Wash trading systémique (Chaos Labs + Inca Digital + Columbia 2024-2025)

**Niveau de preuve : DÉMONTRÉ à grande échelle** (3 études indépendantes convergentes)

**Chaos Labs + Inca Digital (octobre 2024, pré-élection)** : **~1/3 du volume de la présidentielle 2024 = wash trading**. Méthode : isoler high-volume traders, analyser ratios buy/sell et holdings/trading volume. Source : https://fortune.com/crypto/2024/10/30/polymarket-trump-election-crypto-wash-trading-researchers/.

**Columbia study (Sirolly et al., Nov 2025)** — https://gamblingharm.org/wp-content/uploads/2025/11/Polymarket-Wash-Trading-Study.pdf
- Dataset : **67,7M trades, 1,33M wallets, 102 532 markets, 45 732 events** (Nov 2022 → Oct 2025)
- **~25% de tout le volume historique = wash trading** suspect
- **~14% des 1,26M wallets actifs** montrent patterns suspects
- **Peak 60% du volume hebdomadaire en décembre 2024** (cohérent avec rumeurs token Polymarket et airdrop farming)
- Fall <5% en mai 2025, resurgence 20% en octobre 2025
- Certaines semaines : **>90% du volume** des marchés électoraux/sports flaggé
- **~$4,5 Mds trades** classifiés wash probables
- **Motivation principale : airdrop farming** (pas P&L direct — "many wash trading wallets made no real profits")

**Vulnérabilités structurelles identifiées** : aucun KYC, zero trading fees, self-custodied wallets anonymes, rumeurs token Polymarket futur.

**Réaction Polymarket** : "a single trader taking positions on both sides of a market is hardly unique to Polymarket and not in and of itself problematic". Harry Crane (Rutgers) : "the narrative about manipulation is an attempt by legacy media to discredit these markets".

**Enseignement détection** : **toute feature basée sur volume doit filtrer impérativement le wash trading** — sinon pollue entièrement le signal.

---

### Cas 17 — UMA oracle manipulation (Zelensky suit $237M, Ukraine mineral deal $7M, 2025)

**Marché Zelensky suit** : "Will Zelenskyy wear a suit before July?" ($160M → $237M volume). Zelensky à NATO Summit 24 juin 2025 en blazer noir — majorité médias + Grok AI : "suit" ; Derek Guy (menswear influencer) : "both a suit and not a suit", bet $3,6M "No" (gain potentiel $72K).

**Mécanique** : token UMA holders avec side-bet sur Polymarket votent **contre** le consensus visuel. Première résolution "Yes" → disputée → seconde "No" (~4 juillet 2025).

**Marché Ukraine mineral deal (25 mars 2025)** : ~$7M. Un whale a utilisé ~**5M UMA tokens via 3 comptes (~25% du vote total)**. Résolution "YES" malgré absence d'accord signé. Polymarket refuse refunds, promet améliorations. Profit attaquant estimé $100K-$300K.

**Contre-argument Hart Lambur (co-fondateur UMA)** : *"UMA token holders want the UMA token to go up in value, and if it's a broken or manipulated system, the UMA token becomes worthless"* — long-term incentive = bonne résolution.

**Faille structurelle** : token-weighted voting + side-bet incentive sur Polymarket = résolution manipulable sur marchés ambigus. Polymarket a acquis Brahma (mars 2026) pour infrastructure améliorée.

**Sources** : CoinDesk ; Decrypt (https://decrypt.co/329210/polymarket-rules-no-237m-bet-zelenskyys) ; Protos.

---

### Cas 18 — AI markets insider presumption (OpenAI GPT-5.x, décembre 2025)

**Niveau de preuve : Indices forts, pas de prosecution**

**Marchés** : "Will OpenAI release a new model by Dec 13?", "GPT-5.5 released by..."

**Patterns The Information (décembre 2025)** :
- 1 semaine avant GPT-5.2 release : **4 comptes Polymarket** placent bets "OpenAI releases new model by Dec 13" → **+$13 000 profit collectif**
- 1 compte : **+$1M en un jour** sur marché "Google 2025 search data" (possiblement lié à AlphaRaccoon, cf. Cas 9)

**Réactions industrie (KPMG, Conway Dodge)** : discussions avec corporate clients sur inclusion prediction markets dans insider trading policies ont au moins **doublé**. Coinbase et Robinhood ont mis à jour leurs policies pour traiter prediction markets comme insider trading-adjacent.

**Adresses 0x non publiées** par The Information.

---

## Partie II — Profils sharp money (non-insider)

### Domer (@Domahhhh) — le #1 all-time Polymarket

**Wallet primaire** : `0x9d84ce0306f8551e02efef1680475fc0f1dc1344`
**Usernames historiques** : JustKen, ImJustKen, Domer Stan, 🤺JustWakingUp, domahhh
**Identité** : pseudonyme, jamais révélé. Vit hors US. Ex-poker pro golden-era mid-2000s + stock trader. Trading prediction markets depuis **2007** (Intrade → PredictIt → Polymarket 2021).

**Track record cumulé (sources convergentes 2024-2026)** :
- **>$420M bets cumulés depuis registration 2022** (Marc Rubinstein Netinterest)
- **~10 000 prédictions, $2,5M+ net profit** (MetaMask Jan 2026)
- **$300M lifetime volume, >5 000 markets** tradés, #1 volume ET profit (On Chain Times Oct 2024)
- Largest single bet ~$1M (Taylor Swift album sales)
- Typical portfolio : hundreds of thousands sur hundreds of positions

**Trades marquants** :
- 2008 : deduce Sarah Palin VP de McCain via private jet tracking (origin story légendaire)
- 2024 : **$4-5K → $250K sur JD Vance VP** 5 mois avant (2% implied odds) — thèse "Trump prefère last names monosyllabiques (Pence→Vance)"
- 2024 : backing Kamala avant drop Biden — gros winner
- Sep 2024 : ~$150K sur Fed 50bp cut
- Mai 2025 : **$100K sur Prevost pape** (250:1 odds) — recherche via cardinal interviews
- Nov 2024 : **short Trump on election night** — gros loss
- Aide identifier le French Whale cluster (oct 2024)

**Philosophie** (Risk of Ruin podcast, ChinaTalk, CBS 60 Minutes, MetaMask livestream) :
- Manual trading, pas d'auto. Aims ~60% win rate
- Règle clé : *"Bet in accordance with your edge"*
- Warns subject-matter experts underperform (overweight own expertise)
- Pro-Polymarket, crypto-skeptical overall
- Critique UMA ("disinterested, cottage industry of schmoozing")

**Publications** : @Domahhhh X/Twitter (threads). Interviews : On Chain Times (Oct 2024), ChinaTalk, Risk of Ruin (Aug 2025), CBS 60 Minutes, MetaMask livestream (Dec 2025).

### Autres sharps identifiés

**Aenews** (@aenews, @aenews2, @aenews-r2) : actif depuis fin 2020, >5 000 markets, >$1M profits. 2e place Polymarket Invitational 2021. Self-identified #1 culture trader ($260K+ profit).

**Kickstand7** : respecté depuis 2021 (PolyNoob).
**gopfan2 / r_gopfan** : top weather-market trader.
**HolyMoses7** : $1 → ~$100K en challenge run.
**Beachboy4** : **$6,12M profit en un seul jour** sur sports (NFL/NBA), effaçant $687K de pertes.

**Market makers institutionnels** : **Wintermute** (profile @Wintermute), **Jump Trading** (equity stakes Kalshi ET Polymarket contre liquidité, Bloomberg fév 2026), **Susquehanna** (Kalshi).

**Commentateurs/chercheurs** : **Nate Silver** (advisory board Polymarket juillet 2024, equity) ; **Rajiv Sethi** (Barnard/Columbia, https://rajivsethi.substack.com/) ; **Pratik Chougule** (Star Spangled Gamblers podcast) ; **Robin Hanson** (GMU, inventeur LMSR) ; **Harry Crane** (Rutgers, "Fredi9999 Tracker") ; **Matt Levine** (Bloomberg Money Stuff).

---

## Partie III — Contexte régulatoire (résumé opérationnel)

**Settlement CFTC 2022** : **$1,4M le 3 janvier 2022** (Docket 22-09, https://www.cftc.gov/PressRoom/PressReleases/8478-22). Polymarket bloque US-persons par géofencing IP. J. Christopher Giancarlo (ex-CFTC Chair) rejoint advisory board mai 2022.

**Raid FBI Shayne Coplan** : **13 novembre 2024 ~6h ET**, appartement Soho Manhattan. Saisie téléphone + électronique. **Aucune charge**. Tweet Coplan : *"new phone, who dis?"* Brian Armstrong (Coinbase) : "This will backfire — they just made Polymarket even more powerful." **15 juillet 2025** : DOJ + CFTC ferment simultanément enquêtes sans charges (declination notices).

**Retour US** :
- **21 juillet 2025** : Polymarket acquiert **QCX + QC Clearing pour $112M** (licences CFTC)
- **3 septembre 2025** : CFTC no-action letter (Staff Letter 9113-25)
- **7 octobre 2025** : **ICE (NYSE parent) investit jusqu'à $2Mds**, valorisation $8-9B post-money
- **25 novembre 2025** : CFTC Amended Order of Designation
- **2 décembre 2025** : relaunch US officiel
- Autres financements : Founders Fund ($70M Series B mai 2024 @ $1B valo ; $200M juin 2025 @ $1,2B avec Polychain, Coinbase Ventures, Blockchain Capital, Point72, Ribbit, 1789 Capital de Trump Jr.)

**Partenariats** : **X × xAI** (6 juin 2025, Official Prediction Market Partner). Intégration Grok.

**Blocages juridictions** :
- 🇫🇷 **ANJ 22 novembre 2024** (pas AMF) — base légale loi 12 mai 2010, sanctions 3 ans/90K€
- 🇸🇬 **GRA Singapour 12 janvier 2025** (pas MAS) — Gambling Control Act 2022
- 🇹🇭 **Thaïlande 14 janvier 2025** — Cyber Crime Investigation Bureau
- 🇹🇼 **Taïwan** — raids décembre 2023, renforcement 2025
- 🇧🇪 **Kansspelcommissie 30 janvier 2025** (pas FSMA)
- 🇦🇺 **ACMA 13 août 2025** — trigger : promotion élection fédérale australienne via influenceurs
- 🇬🇧 UK : auto-géoblocage depuis 2021 (pas d'action formelle UKGC)
- Autres : Suisse (Gespa nov 2024), Pologne, Ukraine, Bulgarie (2 fév 2026), Portugal (17 mars 2026)

**Market Integrity Rules Polymarket (23 mars 2026)** — https://www.businesswire.com/news/home/20260320997513/en/
- **3 catégories interdites** : (1) trading on stolen confidential information, (2) trading on illegal tips, (3) trading by those who can influence outcome
- Interdictions additionnelles : spoofing, wash trading, self-dealing, front-running
- Surveillance : partnerships trade surveillance specialists + control desk temps réel + **Regulatory Services Agreement avec NFA**
- Neal Kumar (Chief Legal Officer) : *"Markets thrive on clarity"*

**Législation US en cours** : H.R. 7004 "Public Integrity in Financial Prediction Markets Act of 2026" (Rep. Ritchie Torres), BETS OFF Act (Sen. Murphy), DEATH BETS Act (Sen. Schiff). CFTC ANPR mars 2026.

**Kalshi v. CFTC** : 12 septembre 2024, US District Court DC (Judge Cobb) tranche en faveur Kalshi ; 2 octobre 2024 DC Circuit refuse stay ; 7 octobre 2024 Kalshi liste election markets légalement. Victoire ouvre voie régulatoire pour Polymarket.

---

## Partie IV — Synthèse transversale : signatures on-chain et méthodologie de détection

### Taxonomie des cas (18 documentés)

| Typologie | Cas | Proportion |
|---|---|---|
| **Insider pur** (MNPI gouvernementale/corporate confidentielle) | Biden pardons, Nobel Peace, Iran strikes, Maduro, Axiom predictorxyz, Super Bowl halftime, AlphaRaccoon, Ricosuave666, Taylor Swift | 9/18 |
| **Sharp edge** (info publique exploitée avec skill) | Domer (Prevost, JD Vance), syncope (Pope Francis) | 2/18 |
| **Sharp via OSINT offensif** (données techniquement publiques non-publicisées) | Spotify Wrapped, possiblement AlphaRaccoon | 2/18 |
| **Manipulation avérée** | Sethi derivative manip, XRP a4385, UMA oracle (Zelensky), wash trading systémique | 4/18 |
| **Mixte / ambigu** | French Whale Théo (edge réel + impact narratif) | 1/18 |

### Patterns on-chain classés par fiabilité empirique

**Niveau A — Signaux forts (faux positifs faibles)** :
1. **Wallet age <30 jours** combiné à trade >$10K sur niche market (observé : Iran 6 wallets, Maduro 3 wallets, Nobel "dirtycup", SB halftime 0x40d9) — seuil critique **<24h avant event**
2. **Concentration ratio >90%** sur un outcome (observé : tous cas insiders purs)
3. **Timing delta <4h avant annonce publique** (Magamyman 71min, Maduro 5h, dirtycup 5h20)
4. **Shared CEX deposit address** entre plusieurs wallets (Chainalysis Théo 9→11 wallets, Bubblemaps Biden pardons 2 wallets Kraken, Bubblemaps cluster Iran via Binance)
5. **One-shot behavior** : <3 markets traded, 1 outcome (Maduro, Nobel 6741, Iran 6 wallets)

**Niveau B — Signaux modérés** :
- Funding source type (CEX direct = signal ; bridging = signal atténué ; mixer post = signal fort mais rare)
- Market impact >2% du orderbook depth
- Pre-trade wallet activity score bas + gros trade
- Sweeping orders multi-levels dans même tx

**Niveau C — Signaux faibles** :
- Niche market (<$50K daily volume)
- Cross-market win rate anormal
- Sniper entry dans minutes suivant création du marché

### Techniques d'obfuscation classées par efficacité

**Haute efficacité contre analystes publics** : CEX comme tumbler involontaire (retrait CEX → fresh wallet — échoue sur subpoena) ; multiplication wallets (4-11 observés chez Théo ; 6 chez cluster Iran) ; Railgun correct avec gap temporel et amount mismatch.

**Efficacité moyenne** : bridging cross-chain (Arkham Ultra réconcilie) ; Tornado Cash (anonymity set Polygon faible + flagging CEX) ; timing splitting (Théo 71 bets/min) ; camouflage par activité organique (Magamyman actif depuis oct 2024).

**Faible efficacité** : fresh wallet + CEX direct (signature triviale) ; réutilisation deposit addresses CEX (**c'est ce qui a fait tomber Théo** via Chainalysis et Biden pardons via Bubblemaps) ; proxy trading avec payout convergent.

### Features quantitatives extractibles pour un modèle (recommandation)

```
# Wallet-level
wallet_age_days, funder_age_days, funder_nonce_at_funding
proxy_lifetime_tx_count, distinct_markets_traded, distinct_outcomes_traded
concentration_ratio, hhi_outcomes, portfolio_diversity_entropy
win_rate_cross_market

# Funding chain
funding_source_type ∈ {CEX, bridge, fresh_EOA, TC, Railgun, OTC, internal}
num_hops_to_CEX, cex_deposit_address_shared, bridge_used
funding_amount_USDC, funding_round_number_flag
time_from_funding_to_first_trade_seconds
cofunding_cluster_size (proxies funded ±600s from same upstream)

# Timing / event
time_to_resolution_hours, time_to_public_news_hours
trade_in_pre_event_window ∈ {<1h, 1-4h, 4-24h, 24-48h, >48h}
first_trade_implied_probability, realized_vs_implied_edge

# Market microstructure
market_share_of_trade, orderbook_impact, sweeping_levels_count
maker_taker_ratio, wash_trade_flag, niche_market_flag

# Cluster / sybil
shared_deposit_address_cluster_id
temporal_cofunding_cluster_id, cashout_address_shared
behavior_similarity_score
```

### Seuils empiriques recommandés (consensus des cas 2024-2026)

| Feature | Flag | Alerte critique |
|---|---|---|
| wallet_age_days | <30 | <7 |
| funder_nonce | <20 | <5 |
| concentration_ratio | >0,70 | >0,90 |
| distinct_markets_traded | <5 | =1 |
| trade_size_USDC | >$5K | >$25K |
| time_to_event_hours | <48 | <4 |
| orderbook_impact | >0,02 | >0,05 |
| num_cluster_wallets | >2 | >5 |

### Pipeline de détection recommandé

1. **Ingestion temps réel** : Polymarket CLOB WebSocket + Goldsky/Allium stream → filtrer trades >$1K
2. **Wallet profiling** : Polygon RPC (nonce, first tx, balance history) + Arkham/Nansen API enrichment + shortest-path-to-CEX
3. **Cluster expansion** : pour chaque wallet flaggé, clustering par (a) shared deposit address, (b) co-funding ±10min, (c) common upstream à ≤3 hops
4. **Scoring hybride 3 tiers** :
   - Rule-based (unambiguous) : fresh_wallet + concentration >80% + trade >$10K + niche → HIGH ALERT
   - Unsupervised : Isolation Forest/DBSCAN sur features
   - Supervised (quand labels Bubblemaps/Chainalysis disponibles) : gradient boosting
5. **Event correlation** : cross-ref news feeds (GDELT, Reuters, Bloomberg) pour `time_to_public_news_hours`
6. **False positive reduction** : exclure market makers (maker/taker >0,7), arbitragistes cross-platform (Kalshi, Limitless), wallets PnL cumulé négatif significatif

### Limites structurelles — faux négatifs attendus

1. **Bonnes OpSec restent indétectables** : Railgun bien utilisé (deposit-amount ≠ withdraw-amount, gap temporel, token-swap interne), mules KYC distinctes, OTC avec settlement off-chain, micro-positions réparties sans ré-agrégation payout.
2. **Ambiguïté fondamentale sharp vs insider** : le pattern on-chain ne distingue pas conviction informée légitime (Théo avec YouGov neighbor polling) de MNPI pure. Le post-mortem (outcome) est souvent le seul arbitre.
3. **Concept drift après exposure** : ricosuave666 deleted post-Lookonchain exposure ; AlphaRaccoon renamed post-Haeju thread. Chaque publication d'heuristique améliore l'adversary.
4. **Wash trading pollution** : ~25% du volume historique est wash (Columbia), monte à 60-90% certaines semaines — filtrage impératif avant tout feature volume-based.
5. **"Ghost Clusters" Chainalysis/Arkham** (USENIX 2025) : fusion sur co-spending seul produit faux positifs — exiger **≥2 heuristiques convergentes** pour attribution.
6. **Enforcement gap** : offshore exchange (<10% volume passe par entité US régulée) + pas de KYC sur Polymarket international = même détection certaine n'aboutit pas systématiquement à action.

### Trois recommandations méthodologiques finales

**D'abord**, **ne jamais publier l'heuristique complète** — toute publication détaillée accélère le concept drift adversarial. Publier signaux génériques, garder seuils précis et features privilégiées en interne.

**Ensuite**, **privilégier l'explicabilité par cluster plutôt que la détection wallet unique** — un wallet suspect seul peut être ambigu (Théo), mais un cluster de 6 wallets avec shared deposit address et funding synchronisé laisse peu de doute (Iran strikes). La puissance analytique vient de la **fusion multi-heuristiques** (Chainalysis Théo = 3 vecteurs conjoints).

**Enfin**, **adopter le terme "informed trading" plutôt qu'"insider trading"** (pratique Mitts & Ofir, Bubblemaps) — juridiquement plus robuste (CFTC Rule 180.1 est plus étroite que SEC 10b-5 et nécessite preexisting duty), et reflète honnêtement l'incertitude d'attribution sur information non publique.

---

## Conclusion — ce que le corpus révèle

Les 18 cas forensiques documentés ici dessinent un **marché de prédiction biologiquement saturé d'asymétrie d'information**. Les $143M de profits anomaux estimés par Mitts & Ofir (210 000+ wallet-market pairs analysés, 69,9% win rate, >60 écarts-type au-dessus du hasard) ne sont pas une anomalie — c'est la **norme opérationnelle** d'un marché où l'absence de KYC, la liquidité des contrats géopolitiques, et la résolution sur événements détenus par de petits cercles d'initiés (comités Nobel, staff Vatican, personnel halftime NFL, exchanges crypto avant reveal ZachXBT, officials gouvernementaux avant strike Iran) produit des rentes structurelles capturables par quiconque a accès à la fois à l'info et à un wallet Polygon.

**Le benchmark "French Whale Théo" est un mauvais benchmark pour un détecteur** : ses patterns (multiplication wallets, concentration extrême, funding CEX structuré) sont identiques à ceux des insiders purs, mais l'attribution post-mortem a basculé sur "edge légitime" grâce à (a) méthodologie polling public défendable, (b) outcome favorable, (c) absence d'accès évident à MNPI. Les cas plus instructifs pour la détection sont **Biden pardons et Iran strikes** — shared CEX deposit + timing < quelques heures + concentration 100% + niche market + victory rate parfait sur événements exclusivement détenus par governement officials.

**La frontière entre sharp et insider devient poreuse à mesure que Polymarket mature** : Spotify Wrapped via scraping WordPress, AlphaRaccoon via Google staging leak, Axiom via leaks ZachXBT pre-interview — ces cas ne sont ni purement sharp (exploit info publique) ni purement insider (MNPI stricte), mais un continuum qu'aucune régulation actuelle ne capture proprement. Les Market Integrity Rules de mars 2026 et les propositions législatives Torres/Murphy/Schiff tentent de rattraper ce gap, mais l'enforcement offshore reste structurellement limité.

**Pour un détecteur on-chain pragmatique**, le ground truth de ce corpus pointe vers une architecture 3-tiers : (1) alertes automatiques sur la signature "fresh cluster + shared CEX deposit + niche market + pre-event <4h + concentration >90%" (taux faux positifs très faible, ~Iran/Maduro/Nobel/Biden), (2) scoring probabiliste Niveau B pour cas ambigus (Théo-like), (3) filtrage systématique wash trading (25% pollution) avant tout feature volume-based. L'indétectable (bonne OpSec via Railgun + mules KYC + OTC) doit être explicitement acknowledged comme faux négatifs attendus — prétendre le contraire serait malhonnête scientifiquement.