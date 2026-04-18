# Mapping de l'écosystème analytics et trading Polymarket

**Synthèse directionnelle (BLUF).** L'écosystème analytics autour de Polymarket est déjà **dense, fragmenté et en phase de saturation** sur les couches les plus évidentes (copy-trading bots, whale alerts Telegram, dashboards de leaderboards, agents IA "research"). Plus de **170-230 outils tiers** sont listés dans les directories Polymark.et, PolyCatalog et Awesome-Prediction-Market-Tools. Les opportunités réelles se trouvent sur cinq fronts peu servis : **(1) wallet-clustering / entity labelling façon Arkham-Nansen**, **(2) tax & compliance stack post-relaunch US (CFTC/QCEX)**, **(3) resolution/UMA dispute intelligence**, **(4) terminal sports-book-grade pour Polymarket US + Kalshi**, **(5) produit newsroom/journaliste**. Trois dynamiques structurent le marché en avril 2026 : (a) l'investissement de $2 Md d'ICE (NYSE parent) avec distribution exclusive des données Polymarket aux clients institutionnels ; (b) l'audit Polymarket des startups copy-trading lancé le **14 avril 2026** (Polycool et Kreo visés) qui augmente le risque réglementaire ; (c) la création en mars 2026 du premier fonds VC dédié aux prediction markets (**5c(c) Capital**, backé par les CEOs de Polymarket et Kalshi, un PM de Millennium et a16z).

---

## 1. Plateformes analytics dédiées à Polymarket

L'inventaire exhaustif se décompose en **quatre couches** : (a) dashboards officiels et semi-officiels, (b) dashboards Dune communautaires, (c) web-apps standalone, (d) directories/agrégateurs. Aucune des URLs listées n'était défunte lors de la recherche ; la churn est toutefois élevée (nombreux lancements 2025-2026).

### 1.1 Dashboards officiels et Dune communautaires

| Outil | URL | Type | Créateur | Feature clé |
|---|---|---|---|---|
| Polymarket Docs — Data Resources | docs.polymarket.com/resources/blockchain-data | Officiel | Équipe Polymarket | Index canonique des dashboards recommandés |
| Polymarket Activity (Dune) | dune.com/polymarket/polymarket-activity | Semi-officiel | Équipe Polymarket sur Dune | Volume, users, markets |
| rchen8 — Polymarket | dune.com/rchen8/polymarket | Dune | rchen8 | Le dashboard le plus cité dans la presse depuis 2022 |
| Dune Data — Polymarket Overview | dune.com/datadashboards/polymarket-overview | Dune (curated by Dune) | Équipe Dune | Vue curatée officielle Dune |
| Dune Data — Prediction Markets | dune.com/datadashboards/prediction-markets | Dune | Équipe Dune | Multi-venue : Polymarket + Kalshi + Limitless + Myriad |
| filarm — Polymarket Activity & Volume | dune.com/filarm/polymarket-activity | Dune | filarm | Activité et volume détaillés |
| seoul — Address Tracker | dune.com/seoul/poly | Dune | seoul | Eligibilité airdrop |
| lifewillbeokay — CLOB Stats | dune.com/lifewillbeokay/polymarket-clob-stats | Dune | lifewillbeokay | Statistiques orderbook |
| Austin W — Polymarket Analysis | (lié Medium tuto 13ajw12) | Dune + tuto | Austin W | Tutoriel de référence |
| Artemis — Prediction Markets | app.artemisanalytics.com/sectors?tab=prediction_markets | Dashboard pro | Artemis | Intégration B2B |
| Blockworks Analytics Polymarket | blockworks.com/analytics/polymarket | Media | Blockworks | Dashboard éditorial |
| Parsec Polymarket | parsec.fi/polymarket | Widget pro | Parsec | Intégration dans terminal DeFi |

### 1.2 Web-apps standalone (analytics, leaderboards, terminaux)

Plus de **40 produits distincts** identifiés. Les plus notables :

| Produit | URL | Économie | Audience estimée | Date lancement | Feature différenciante |
|---|---|---|---|---|---|
| **PolymarketAnalytics.com** | polymarketanalytics.com | Gratuit | Cité par WSJ/CoinDesk ; 1M+ wallets trackés (self-reported) | 2024 | Distinction sharp money / dumb money, refresh 5 min |
| **Predicting.top** | predicting.top | Gratuit | Petite mais active | Sept. 2025 | "Kolscan de Polymarket", cross-Kalshi |
| **Polymark.et** | polymark.et | Gratuit (directory) | Aggrégateur | 2024 | 180+ outils classés |
| **PolyCatalog** | polycatalog.io | Gratuit (directory) | — | 2025 | Classification alternative |
| **Prediction Index** | predictionindex.xyz | Gratuit | — | 2025 | 140+ projets |
| **pm.wiki** | pm.wiki | Gratuit | — | 2025 | 350+ projets, outil de comparaison |
| **HashDive** | hashdive.com/polymarket | Gratuit | — | 2025 | Dashboards simples |
| **Polywhaler** | polywhaler.com | Gratuit | — | 2024 | Tracker $10K+ temps réel |
| **Whale Tracker Livid** | whale-tracker-livid.vercel.app | Freemium ($29/mo Pro) | — | 2025 | Delay 1h gratuit, temps réel payant |
| **PolyInsider** | polyinsider.io | Gratuit | — | 2024 | Fresh wallets $5K+ |
| **PolyTrack** | polytrack.cash | $9.99/semaine | — | 2025 | **Seul produit à revendiquer le "cluster detection"** (détection de wallets liés d'un même trader) |
| **MobyScreener** | mobyscreener.com/predictions-feed | Gratuit | — | 2025 | Live feed top-traders |
| **Nevua Markets** | nevua.markets | Gratuit | — | 2025 | Alerts Telegram/Discord/webhook |
| **FirePolymarket** | firepolymarket.com | Gratuit | — | 2025 | Smart/Whale classification, "Fire Score" |
| **Prediedge** | — | Gratuit | — | 2025 | Cross-venue Polymarket+Kalshi |
| **PolyScan** | polyscan.bet | Gratuit | — | 2025 | Terminal top-traders |
| **Polysights** | app.polysights.xyz | Freemium | — | 2025 | 30+ métriques, AI summaries |
| **polymarket-whales.xyz / polymarket-bot.xyz** | — | Freemium (payé en USDC) | — | 2025 | Top 100 wallets (Theo4, swisstony…) |

### 1.3 Terminaux de trading professionnels

| Produit | URL | Modèle | Positionnement |
|---|---|---|---|
| **Stand.trade** | stand.trade | Freemium | Aggrégateur Polymarket+Kalshi, copy-trade, TP/SL, featured dans le blog Oracle de Polymarket |
| **Verso** | verso.trading | Payant | "Bloomberg-style" pour prediction markets, YC-backed |
| **TradeFox** | thetradefox.com | Institutionnel | Prime brokerage ; backed Alliance DAO, CMT Digital |
| **Converge** | converge.market | Freemium | Cross-venue + détection arb |
| **Sharpe Terminal** | beta.sharpeterminal.com | Beta | Ordres avancés, social feed |
| **Polyburg** | polyburg.com | Payant | AI + smart wallets |
| **Polymtrade** | polym.trade | App | Premier terminal mobile complet |
| **TREMOR** | tremor.live | Payant | SQL + AI sur 140K markets |
| **Pigeon** | pigeon.trade | Tiered | Multi-plateforme, chat-based |
| **Oddpool** | oddpool.com | Freemium/inst. | "Bloomberg for prediction markets", orderbook + API historique |
| **Based** | app.based.one/predict | Gratuit | Intégration Hyperliquid + Polymarket |
| **Rainmaker (Cloud9)** | rainmaker.fun | Tiered | AI-powered arb + copy-trading |
| **Elastics** | — | Beta | "AI OS" pour prediction markets |

### 1.4 Extensions navigateur

| Extension | URL | Feature |
|---|---|---|
| Polymarket Whale Tracker (Chrome) | chromewebstore.google.com (onhhaghaecempnnodenjjlhkobgpkkfj) | Panel latéral, seuil $10K-$100K |
| Polyteller | polyteller.com | Countdowns, notifications |
| PolyTimer | polytimer.fun | Countdowns multi-timezone |
| Polyprophet | polyprophet.com | Overlay AI de prédictions |
| PolyPulse | polypulse.tech | Analyse news Perplexity-powered |
| PMs4X | Chrome Web Store | Polymarket intégré dans le timeline X |

**Point important sur la popularité des dashboards Dune** : Dune n'expose pas publiquement les view-counts, donc le ranking est inféré des citations presse. **rchen8** et le **Dune Data Team** dominent les citations (WSJ, Bloomberg, The Block). Le dashboard multi-venue de Dune Data sur prediction markets est probablement l'outil le plus consulté par analystes institutionnels depuis fin 2024.

---

## 2. Comptes Twitter/X et newsletters influents

La cartographie Twitter s'articule autour de six catégories. Deux faits structurants : (a) la plupart des top-traders du leaderboard Polymarket sont **pseudonymes on-chain sans compte X correspondant** (WindWalk3, HyperLiquid0xb, Erasmus, S-Works, etc.) — ils sont suivis via les whale-bots plutôt que sur Twitter ; (b) **le compte officiel @Polymarket a un problème de crédibilité éditoriale** — le NYT a documenté des centaines de posts trompeurs, Jeff Bezos a démenti l'un d'eux publiquement en janvier 2026.

### 2.1 Traders (positions et PnL publics)

| Handle | Followers est. | Contenu | Données originales |
|---|---|---|---|
| @Domahhhh (Domer) | ~150K | #1 all-time trader Polymarket, threads profondes (SBF, Altman, Pope) | Oui — positions + raisonnement |
| @flip_pidot (Flip Pidot) | ~20-40K | Vétéran PredictIt/Polymarket, cité par médias sur les chiffres de volume | Oui, mixte |
| @thewinner2875 | ~10K | SSG Title Belt Champion, markets politiques | Oui |
| @benwfreeman1 (Ben Freeman) | ~10K | SSG regular, political markets | Oui |
| @ianlazaran (Alex Chan) | ~5-10K | SSG challenger | Mixte |
| @talophex (Dr. Lucas) | ~5K | Markets santé/politique (Biden health) | Oui |
| @tradeandmoney (Doug Campbell) | ~5K | Macro-oriented ; gagnant du concours Astral Codex 2023 | Oui |

### 2.2 Analystes

| Handle | Followers est. | Contenu |
|---|---|---|
| @NateSilver538 (Nate Silver) | ~260K+ | **Advisor Polymarket payé** ; compare Silver Bulletin à Polymarket |
| @robinhanson (Robin Hanson) | ~80K | L'économiste OG des prediction markets, theorie futarchy |
| @pjchougule (Pratik Chougule) | ~15K | Host de Star Spangled Gamblers, analyse légale/CFTC |
| @MickBransfield | ~5K | Research Director Coalition for Political Forecasting |
| @nathanpmyoung (Nathan Young) | ~10K | Intersection forecasting/EA/AI |
| @MapleLeafCap (Jason Kam) | **49.4K (confirmé)** | Fondateur Folius Ventures, analyses DeFi/prediction markets (voir §5 pour la mise au point : **ce n'est PAS un whale Polymarket**, malgré la mention dans la demande initiale) |

### 2.3 Comptes data/viz et whale-trackers

| Handle | Followers est. | Contenu |
|---|---|---|
| @PolyInsider_ | ~10-30K | Whale alerts temps réel, built par @caneleo55 |
| @polytrackerbot | ~5-15K | Bot automatisé, filtre sports, focus buy-side (par @alfiethecrypto) |
| @polymarketanalytics | ~5K | Dashboards Goldsky-powered, cité par WSJ/CoinDesk |
| @ArkhamIntel | ~400K+ | Intel on-chain général, mais surface régulièrement des whales Polymarket (larpas, Fredi9999) |
| @alfiethecrypto | ~5-10K | Dev polytrackerbot |
| @caneleo55 | <5K | Builder PolyInsider |

### 2.4 Journalistes sur le beat Polymarket

| Handle | Média | Followers est. | Spécialité |
|---|---|---|---|
| @yaffebellany (David Yaffe-Bellany) | NYT | 7,592 (✓) | Couverture NYT lead : Coplan, FBI raid, wash-trading |
| @aosipovich (Alexander Osipovich) | WSJ | ~15K | Broke Fredi9999 ; investissement ICE $2B |
| @eleanor_mueller (Eleanor Mueller) | Semafor | ~20K | Régulation CFTC, Congrès |
| @fsalmon (Felix Salmon) | Axios | ~100K+ | Chroniques régulières Polymarket, Axios Visuals |
| @anniemassa (Annie Massa) | Bloomberg | ~10K | Co-auteur du feature Coplan/Sprecher (nov. 2025) |
| @KDohertyNYC (Katherine Doherty) | Bloomberg | ~5-10K | Co-couverture prediction markets |
| @LydiaBeyoud | Bloomberg | ~10K | CFTC/régulatoire |
| @teddyschleifer | Puck/NYT | ~30K | Argent tech-politique |
| @Tina_Nguyen | Puck | ~50K | Trump-Polymarket/Kalshi |
| @DustinGouker | Event Horizon | ~10K | **Le plus cité indépendamment** (Columbia Journalism Review) |
| @fmaglione_ | Bloomberg | ~5K | Personal finance |

### 2.5 Officiel et team Polymarket

| Handle | Followers est. | Rôle |
|---|---|---|
| @Polymarket | ~500K+ | Officiel (crédibilité contestée par NYT) |
| @shayne_coplan | ~150K+ | CEO, plus jeune milliardaire self-made après le deal ICE |
| @PolymarketIntel | ~200K+ | "Community-run" geopolitics/breaking news |
| @PolymarketTrade | **45.6K (✓)** | Official-adjacent, features top traders |
| @willlegate (Will LeGate) | ~40K | Head of Growth |
| @modabber (Matt Modabber) | ~10K | CMO |

### 2.6 Agrégateurs / bots

| Handle | Followers est. |
|---|---|
| @PolymarketIntel (aggregator) | ~200K |
| @polytrackerbot | ~10K |
| @PolyInsider_ | ~15K |
| @PredictionNews_ | **2,647 (✓)** |
| @ssgamblers (Star Spangled Gamblers) | ~10K |
| @fliprbot | ~20K (trade-via-tweet) |

### 2.7 Newsletters

| Newsletter | Auteur | URL | Abonnés | Prix |
|---|---|---|---|---|
| **The Oracle by Polymarket** | Polymarket (officiel) | news.polymarket.com | **69,000+ (✓ Substack)** | Gratuit |
| **Event Horizon** | Dustin Gouker | nexteventhorizon.substack.com | **3,419 (✓)** | Free + paid |
| **The Closing Line** | Dustin Gouker | closingline.substack.com | ~5K | Free + paid |
| **Silver Bulletin** | Nate Silver | natesilver.net | "Tens of thousands" ; Silver a dit $1M+/an | $20/mo ou $200/an |
| **Star Spangled Gamblers** | Pratik Chougule | starspangledgamblers.com | ~5K | Gratuit |
| **Prediction News** | @PredictionNews_ | predictionnews.com | ~2-5K | Gratuit |
| **Forecasting Newsletter** | Nuño Sempere | forecasting.substack.com | ~5K | Gratuit |
| **Risk of Ruin** | (podcast + newsletter) | riskofruinpod.substack.com | ~3K | Gratuit |
| **ChinaTalk** | Jordan Schneider | chinatalk.media | ~50K | Free + paid |

Le partenariat **Substack × Polymarket de janvier 2026** a rendu les données Polymarket embed-ables en natif dans les newsletters Substack : **1 sur 5 des top 250 publications Substack** utilise désormais des embeds Polymarket, donc le volume de couverture est beaucoup plus large que les newsletters strictement dédiées.

---

## 3. Copy-trading et bots existants

**Verdict : le segment copy-trading est SATURÉ et sous scrutin réglementaire.** Plus de **40 produits live** couvrent copy-trading, whale alerts et signaux. L'évolution clé — **l'audit Polymarket lancé le 14 avril 2026** sur les startups du Builders Program (Polycool et Kreo visés nommément pour avoir marketé "find insiders before the rest" et un "guide to Polymarket insider trading"). Cet audit élève significativement le risque réglementaire pour tout nouvel entrant.

### 3.1 Bots publics Telegram (les plus significatifs)

| Bot | URL | Pricing | Feature |
|---|---|---|---|
| **Polycule** ($PCULE) | polycule.trade | Free + token (~$14.75M mcap) | **Levé $560K d'AllianceDAO (juin 2025)** ; copy trading + bridge Solana→Polygon |
| **PolyxBot** | polyxbot.org | Free + $PLX | AI analysis, cross-chain, applicant Builders Program |
| **KreoPoly (Kreo)** | kreopoly.app | Free + commission | Copy-trading via enclaves Privy — **en audit Polymarket avril 2026** |
| **Polycool** | polycool.live | 1% par trade, 3K+ users revendiqués | Top 0.5% wallets — **en audit Polymarket avril 2026** |
| **PolyAlertHub** | polyalerthub.com | Free + paid | Whale/insider/price alerts, pas de connexion wallet |
| **PolyIntel** | t.me/PolyIntel_bot | Free | Whale+insider alerts 10 min |
| **PolyTracker** | t.me/polytracker0_bot | Free | Tracking wallet-spécifique (par @nlabplay) |
| **Polylerts** | t.me/Polylerts_bot | Free | Track jusqu'à 15 wallets |
| **YN Signals** | t.me/YNSignals | Free | Cross-venue aggregator |
| **PolyCop** | t.me/PolyCop_BOT | 0.5% fees | Sub-second copy, non-custodial |
| **Polytrage** | t.me/polytrage | Free | Arb alerts 15 min |
| **Predictify** | t.me/Predictify_bot | Free | On-chain aggregator |
| **okbet** | tryokbet.com | Free | Terminal Telegram Polymarket+Kalshi |
| **PolyFocus** | t.me/polyfocusbot | Free | Multi-chain, copy-trading |

### 3.2 Services payants de copy-trading

Il n'existe **aucune fonctionnalité native** de copy-trading sur Polymarket. Tous les produits sont tiers, reposant sur la CLOB API publique + données Polygon on-chain.

| Service | URL | Pricing | Statut |
|---|---|---|---|
| **Stand.trade** | stand.trade | Freemium | Le plus institutionnel ; featured dans blog Oracle Polymarket (sept. 2025) |
| **Polycool** | polycoolapp.com | 1% par trade | **Audit Polymarket actif** |
| **KreoPoly** | kreopoly.app | Free + commission | **Audit Polymarket actif** |
| **Polycule** | polycule.trade | Free + token | Levé $560K |
| **Polycop** | t.me/PolyCop_BOT | 0.5% | Sub-second |
| **polycopytrade.net** | polycopytrade.net | $99/mo (Starter) | **Claims de 10K+ users et $50M volume non vérifiables — probable marketing affiliate** |
| **Rainmaker** | rainmaker.fun | Tiered | AI arb + copy |
| **PolyTrack** | polytrack.cash | $9.99/semaine | Cluster detection, copy "coming soon" |
| **Polymarket Bros** | brosonpm.trade | Free | One-click copy trades >$4K |

### 3.3 Groupes de signaux payants

**Segment étonnamment peu développé par rapport à la demande** — les quelques offres existantes sont soit gratuites soit à faible crédibilité de track record.

| Groupe | URL | Pricing | Réputation |
|---|---|---|---|
| **PolyOdds** | polyodds.store | Abonnement Discord (prix à la signup) | "Ex-IB et hedge fund analysts", indépendant |
| **BBB (Big Boy Bets)** | docs.bbb.community | Invite-only, **capped 150 membres** | Exclusif, boutique |
| **Binary Alpha** | DISBOARD | Gratuit (serveur signal) | Filtré, cross Polymarket+Kalshi |
| **polycopytrade.net** | — | $99/mo | **Low trust** |
| **MarktQuant** | whop.com/core-essentials | $29.99-79.99/mo | Crypto-focused, inclut prediction |

### 3.4 Whale alert tools (les plus notables)

Voir §1.2 pour le panorama complet. Points critiques : Polywhaler, Whale Tracker Livid, PolyInsider, PolyTrack, polymarket-whales.xyz. **Aucun compte Twitter dédié ne joue le rôle de "@WhaleAlert pour Polymarket"** — @polytrackerbot est le plus proche mais reste petit.

### 3.5 Open-source frameworks (GitHub)

Le code est essentiellement **commodity** : tutoriels QuickNode, framework officiel Polymarket/agents, OctoBot-Prediction-Market, Poly-Tutor, ent0n29/polybot, warproxxx/poly-maker, MrFadiAi, amadeusprotocol, direkturcrypto/polymarket-terminal, BSCsmartdev, Railway 1-click deploy. Les deux répertoires de référence : **harish-garg/Awesome-Polymarket-Tools** et **aarora4/Awesome-Prediction-Market-Tools** (le plus complet, 111 stars).

**Implication stratégique** : construire *juste un bot copy-trading* est désormais un produit à zéro différenciation. Les open-source repos permettent un déploiement en heures.

---

## 4. Produits crypto analogues dont s'inspirer

| Plateforme | Lancement | Funding total | Valorisation | Entry price | Différenciateur clé | Transposabilité Polymarket |
|---|---|---|---|---|---|---|
| **Nansen** | 2020 | $88.2M | $750M (2021) | $49/mo (Pro unique tier depuis sept. 2025) | Smart Money wallet labels + 300M labels | ⭐⭐⭐⭐⭐ |
| **Arkham** | 2020 | ~$14M + ICO | $150M pré-token | Core gratuit ; ARKM pour Intel Exchange | Entity deanonymization + Intel Exchange | ⭐⭐⭐⭐⭐ |
| **Lookonchain** | 2021 | Undisclosed (petit) | N/A | Gratuit + app freemium | Storytelling narratif, 1.5M+ followers X | ⭐⭐⭐⭐⭐ |
| **DeBank** | 2018 | $25M | $200M (2021) | Gratuit ; $96 DeBank ID | Social layer + leaderboards | ⭐⭐⭐⭐⭐ |
| **Zerion** | 2016 | $22.5M | Non divulgué | $99/an Premium | Wallet + portfolio unifiés, watch-wallet | ⭐⭐⭐⭐ |
| **Dune** | 2018 | ~$80M | $1B (2022) | Gratuit / Plus $399/mo / Ent custom | SQL + UGC dashboards, 500K+ analysts | ⭐⭐⭐⭐ |
| **Messari** | 2018 | $61M | $300M (2022) | Lite $10, Pro $29.99, Ent $6-34K/an | Institutional research + AI | ⭐⭐⭐ |

### 4.1 Nansen — Leçons clés

Le **pivot pricing de Nansen en septembre 2025** (suppression des tiers Pioneer $129 et Professional $999-$1,299, remplacés par un tier Pro unique à **$49/mo**) est un signal macro fort : le prix du prosumer crypto-analytics a été **compressé de 95%**. Tout nouveau produit Polymarket doit se caler dans le $10-$50/mo. Leur Smart Money → se transpose directement en cohortes "Smart Bettors", "Political Sharps", "Sports Edge". Le Token God Mode → "Market God Mode" par marché (top holders, flux, whale entry prices).

### 4.2 Arkham — Le modèle le plus transposable

Trois features directement applicables : **(1) l'entity deanonymization** (mapping multi-wallets → un trader, exactement le problème Théo/11 wallets du 2024) ; **(2) l'Intel Exchange** — bounty marketplace pour labels crowdsourcés ("ce wallet = @handle Twitter") ; **(3) le Visualizer** — graph fund-flow. Le token ARKM est à -97% de l'ATH — la leçon est que **l'utilité doit précéder la spéculation**.

### 4.3 Lookonchain — Le plus replicable pour la croissance

1.5M+ followers X avec une équipe minuscule et peu de funding. **Le modèle "storytelling whale-trades" est probablement le meilleur ratio ROI pour un nouveau produit Polymarket** : chaque marché a une narrative native ("A wallet bet $2M on Trump at 43¢ two weeks before debate, now $4.7M unrealized"). Un compte "Polymarket Lookonchain" pourrait se construire pour <$500K/an.

### 4.4 DeBank — Le playbook social

DeBank est le seul à avoir craqué la social layer sur wallets. **DeBank ID à $96 one-time** = revenue driver de vanité + identité. "Hi" priced messaging monétise l'accès aux whales. Stream feed. TVF leaderboards. **Sur Polymarket, les top traders sont déjà des célébrités** (Théo, Fredi9999, Domer) — le modèle DeBank est taillé pour cet écosystème.

### 4.5 Zerion, Dune, Messari — Angles complémentaires

**Zerion** apporte le primitif "watch-wallet" (tracker sans clés) et le CSV export / tax (essentiel pour les bettors >$50K volume). **Dune** montre que la couche UGC SQL + dashboards pays des analystes ("Wizards") crée un effet de réseau et un funnel B2B via embeds. **Messari** est le modèle institutionnel : asset profiles → market profiles, research reports → "State of Election Markets Q1 2026", enterprise API à $6-34K/an/siège.

### 4.6 Feature playbook consolidé (15 features prioritaires)

**Tier 1 — indispensables** : (1) Leaderboards traders multi-dimensions, (2) Smart Money cohort labels, (3) Follow + real-time alerts, (4) Trader profile pages, (5) Market God-Mode per-market deep-dive.

**Tier 2 — haute valeur** : (6) Wallet clustering / Theo detection, (7) Compte Twitter narratif façon Lookonchain, (8) Polymarket ID/vanity handles, (9) Activity feed social, (10) CSV export + tax reports.

**Tier 3 — différenciation et monétisation** : (11) SQL playground + UGC dashboards, (12) Alerts engine configurable, (13) Enterprise API & DataShare, (14) Priced DMs paid-access-to-whales, (15) Research reports hebdomadaires AI-assisted.

---

## 5. Acteurs institutionnels et hedge funds sur Polymarket

### 5.1 Domer — le #1 all-time trader

Trader individuel, ancien joueur de poker online mid-2000s, puis stock trader, puis prediction-markets sur Intrade/PredictIt/Polymarket depuis 2008 (arrivé sur Polymarket début 2021). **Twitter : @Domahhhh.** Handles Polymarket : "JustKen" puis "🤺JustWakingUp". Wallet public : `0x9d84ce0306f8551e02efef1680475fc0f1dc1344` (polymarket.com/profile/0x9d84ce0306f8551e02efef1680475fc0f1dc1344). **Méthodes : trading 100% manuel, research-driven, grinder à coups de limit orders.** Cite explicitement Kahneman/Tversky (ancrage, dotation, disponibilité). Dans ses mots : "slow motion poker hands where you can out-research your opponents."

Scale fin 2024 : **~$300M de volume lifetime, ~5,000 markets tradés, +$700K net profit sur trois ans** (DL News juin 2024). Notable : a identifié publiquement le premier le cluster Fredi9999/Théo le 16 octobre 2024. Wins notoires : SBF 25 ans prison (+$50K), Altman firé OpenAI (+$50K), Kamala Harris achetée avant le drop Biden. Loss notoire : short Trump la nuit de l'élection 2024.

**Interviews/podcasts** : OnChainTimes (oct. 2024), ChinaTalk "Betting on Chaos", Risk of Ruin (août 2025), Foot Guns Pod #58 (juin 2024), DL News profile. Semi-inactif depuis peak 2024/2025 selon PolyNoob.

### 5.2 Maple Leaf Capital — MISE AU POINT CRITIQUE

**@MapleLeafCap N'EST PAS un whale Polymarket.** Le handle correspond à **Jason Kam** (金秋), Chinois élevé à Hong Kong, ex-Deutsche Bank / 40 North / Briarwood Chase (emerging-markets PM), fondateur de **Folius Ventures** (sept. 2021), fonds hybride VC + liquid hedge en APAC backé par ParaFi, Dragonfly, Galaxy, Framework. Suivi par **49.4K followers**. Il publie des analyses longues DeFi/GameFi/crypto-apps (STEPN early backer, TON/Catizen). Runs également BidClub.io.

**Aucune preuve publique qu'il trade directionnellement sur Polymarket** — sa couverture prediction markets est sporadique sur Twitter, pas une stratégie dédiée. La demande initiale conflate probablement deux personnalités crypto distinctes.

### 5.3 Théo — le "French Whale"

**L'affaire institutionnelle Polymarket #1.** Identifié par Polymarket, WSJ et NYT DealBook comme un trader français single, prénom Théo, background banque/finance. **Accounts contrôlés : au minimum 4 publics (Fredi9999, Theo4, PrincessCaro, Michie), étendu par Chainalysis post-élection à ~11 accounts** (incluant RepTrump). **Capital déployé : $30M initial → ~$45M final. Profit final : ~$85M sur l'élection 2024** (Chainalysis/Bloomberg 7 nov. 2024). Theo4 et Fredi9999 ont fini #1 et #2 all-time profit Polymarket.

**Méthodes** : thèse du "neighbor polling" (a commandé son propre polling firm pour mesurer "qui votera votre voisin" — effet Trump caché) + fragmentation HFT des ordres à travers les comptes pour ne pas bouger les prix. Pics de 1,600+ trades / 24h, 450+ bets en 10h sur Theo4.

Conséquence politique : enquête du régulateur français ANJ, **Polymarket bloqué en France et Belgique** (toujours le cas avril 2026). Le 24 oct. 2024, Polymarket a officiellement conclu qu'il s'agissait d'un seul trader, pas de manipulation, trader a accepté "ne pas ouvrir d'autres comptes sans notice".

### 5.4 Autres whales notables

| Nom | Profil | Profit 2024 | Méthodes |
|---|---|---|---|
| **zxgngl** | Anonyme, funded via Binance ($14.2M USDC dès 11 oct. 2024) | **+$11.4M** | Pure directionnel Trump, $18.3M peak position |
| **walletmobile** | Anonyme | **+$5.94-6.1M** | Pure directionnel Trump |
| **RN1, swisstony, gmanas, GamblingIsAllYouNeed** | Probablement bots/arbs sophistiqués | $4-7M each | $400M-$653M volume chacun |
| **GCottrell93** | Nommé médias 2024 | Multi-million Trump | Identité non établie |
| **larpas** | Anonyme | Sold $3.15M Trump 20h avant election | — |
| **KeyTransporter, BetTom42, mikatrade77, alexmulti, Jenzigo, DrPufferfish, RepTrump** | Top-20 profit all-time | $4-7M lifetime | Plusieurs probables bots (IMDEA étude) |
| **romanticpaul** | Individuel | — | Poussé le marché Taylor Swift engaged de 25→45% |
| **BuckMySalls** | Individuel depuis 2021 | — | Profil bas, respecté |
| **defiance_cr** | Bot operator public | ~$700-800/jour peak | AMM deux côtés via liquidity rewards |

### 5.5 Market makers et infrastructure institutionnelle

| Firme | Statut Polymarket | Statut Kalshi | Notes |
|---|---|---|---|
| **Susquehanna (SIG/SGP)** | OTC via partenariat **BitGo** (2026) | **Premier MM officiel Kalshi (3 avril 2024)** | Desk dédié event-contracts |
| **Jump Trading** | **Oui — stake equity contre MM** (Bloomberg début 2026) | Oui — MM + equity stake (fin 2025) | Ex-desk Betfair sports (arrêté 2023) |
| **Wintermute** | **Oui — profil officiel** polymarket.com/@Wintermute ; wallets liés identifiés on-chain | Non confirmé | HFT crypto, Londres, fondé 2017 |
| **DRW (Cumberland)** | Build desk actif, **salaires traders jusqu'à $200K base** pour arb Polymarket/Kalshi (FT/Business Insider 2026) | Même | HFT quant géant |
| **Citadel Securities** | Non rapporté | Non confirmé | En attente |
| **GSR** | Non | Non | — |
| **Tyr Capital** | Hiring actif prediction desk | — | — |

### 5.6 Structures dédiées et investisseurs institutionnels

**5c(c) Capital** — **Premier fonds VC explicitement dédié à l'écosystème prediction market** (lancé mars 2026). Fondé par deux ex-Kalshi. Backers initiaux : Shayne Coplan (CEO Polymarket), Tarek Mansour (CEO Kalshi), **un PM Millennium Management**, Marc Andreessen (via Moneta Luna avec Chris Dixon et Elena Silenok), Jeremy Levine (CEO Underdog Fantasy), Jacob Fortinsky (CEO Novig). Objectif : **jusqu'à $35M levés, ~20 startups**, focus data tools / liquidity / compliance. Source : Bloomberg 23 mars 2026.

**ICE (NYSE parent)** — $2 Md investissement Polymarket annoncé oct. 2025, complété ~mars 2026, valorisation ~$8-9 Md. **Critique : ICE est distributeur exclusif des données événementielles Polymarket aux clients institutionnels.** CEO Jeffrey Sprecher (Goldman Sachs conf. déc. 2025) : **>50% (~5,000) des ~10,000 clients institutionnels ICE ont exprimé un intérêt** pour le data stream.

**Autres canaux institutionnels** : Bloomberg Terminal intègre les données Polymarket. Partenariat Dow Jones/WSJ Q1 2026. BitGo OTC via Susquehanna (collateral USD/stablecoin/BTC, contrats $100K+).

**Saba Capital (Boaz Weinstein)** observe mais ne trade pas encore — citant à FT/Cryptopolitan des opportunités de pair-trade (ex. probabilité récession 50% sur Polymarket vs 2% dans le crédit).

### 5.7 Dynamiques plateforme institutionnelle

- **KYC** : Polymarket International (Polygon) = email + wallet auto-généré, pas de KYC. **Polymarket US (QCX LLC, DCM CFTC, opérationnel depuis 2 déc. 2025)** = KYC complet.
- **Programmes MM** : Liquidity Rewards program ($5M+/mois, fonction quadratique spread-to-midpoint inspirée dYdX). **Permissionless market-reward sponsorship lancé 17 février 2026** — n'importe qui peut déposer USDC pour sponsor un marché. RFQ API pour MMs (mm@polymarket.com). Builder Tiers (Unverified/Verified/Partner).
- **Pas de "Polymarket Pro" branded** — l'accès institutionnel passe par Builder Tiers + BitGo/Susquehanna OTC + RFQ direct.
- **Acquisitions** : Brahma (mars 2026, infra DeFi pour simplifier UX).
- **Arbitrage extraction** (IMDEA Networks, arXiv août 2025) : ~$40M arb extrait d'avril 2024 à avril 2025 sur 86M bets ; top 3 wallets = 10,200+ bets et $4.2M. **Fenêtre d'arb comprimée de 12.3s (2024) à 2.7s, 73% capturé par bots sub-100ms** sur RPC Polygon dédiés.
- **Base utilisateurs** : 1.35M+ traders ; **seulement 0.51% ont un profit net >$1,000** ; top 1.74% sont "whales" (>$50K volume).

---

## 6. Gaps identifiés et opportunités de positionnement

### 6.1 Top features demandées / sous-construites (avec évidences)

1. **Tax reporting automatisé complet, surtout post-relaunch US dual-reporting.** Polymarket n'émet pas de 1099. Seulement 2-3 spécialistes existent (PolyTax polymarket.tax, PolyTaxReport polytaxreport.com, Camuso CPA). **Aucun ne gère Polymarket US CFTC (1099-B probable) + Polygon/USDC global en un seul produit.** Gap massif Q1 2027.

2. **Wallet clustering / entity labelling "Arkham-Nansen-for-Polymarket".** Seul PolyTrack revendique de la "cluster detection". L'affaire Théo (11 wallets) prouve la demande. Aucun produit ne fait vraiment l'entity labelling labelé (hedge fund X, staffer Congrès Y).

3. **Agrégation cross-venue avec exécution unifiée.** Beaucoup de data-aggregators (FinFeedAPI, PolyRouter, Oddpool, Poly520, Matchr, TRUEiGTECH). **Quasi-aucun exécute réellement sur toutes les venues depuis une UI avec smart order routing.** Stand et Matchr s'en approchent.

4. **Historical orderbook/tick data à prix raisonnable.** CLOB Polymarket expose seulement le recent depth ; historique L2 est vendu par Telonex et PolymarketData.co à prix institutionnels. Quants backtest et chercheurs académiques sous-servis.

5. **Terminal institutionnel avec portfolio/risk management.** Verso (YC) et Elastics early. Bullpen, Stand, Betmoar sur pro retail. Gap : VAR, exposure-by-category, FIX connectivity pour desks institutionnels.

6. **Resolution/UMA dispute early-warning et archive.** Controverses répétées : résolution erronée $7M, marché ressources ukrainiennes, redéfinition "invasion" ($10.5M), gouvernance Zelenskyy. **Aucun produit dédié** ne track les disputes UMA, la concentration des voters whales, et alerte les holders avant settlement. Seul Betmoar a un dashboard UMA basique.

7. **Sports vertical analytics pour Polymarket US beta.** Polymarket US lancé sports-only janvier 2026 ; Kalshi ~90% volume en sports. Les outils existants sont politique/crypto-centric. **Manquent : player-props edges, line shopping vs DraftKings/FanDuel, arb +EV incluant Polymarket US sous règles CFTC, équivalents Build-Your-Combo.**

8. **Qualité app mobile (Android surtout) + search de markets secondaires.** Polymarket iOS 4.7-4.8⭐, Android 2.5-3.8⭐. Complaint récurrent : "impossible de trouver les smaller markets" sur mobile. Polymtrade seul terminal tiers mobile complet.

9. **Charting avancé natif.** Chart natif Polymarket = ligne basique. Demandes récurrentes : candlesticks, indicateurs techniques, drawing, multi-market overlay.

10. **Customer service / dispute resolution.** Trustpilot saturé de plaintes (withdrawals bloqués $30K, $8K, support non-réactif, hacks Magic Labs auth déc. 2025, Google login drains sept. 2024). Aucun ombudsman tiers.

11. **Widgets journalist/newsroom.** Partenariat WSJ/Dow Jones signale la demande. Manquent : probability widgets embed-ables avec historical provenance, screenshot one-click citable, story-lead detection from price moves, Polymarket-vs-polling reconciliation.

12. **Wrapper international/compliance pour juridictions restreintes.** Bloqué France, Belgique, Ukraine, Singapore, Pologne, UK. Aucun information-only aggregator legal-by-design.

13. **Responsible gambling / self-exclusion.** Sportsbookreview et CryptoSlate flaggent l'absence de deposit limits, self-exclusion, phone support.

14. **Dataset académique reproductible.** Journal of Prediction Markets actif, Coalition Greenwich confirme appétit quant. Mais pas de dataset curatisé versioné citable (CRSP for stocks). Dune queries + Goldsky subgraphs requièrent effort engineering.

15. **Security/insurance layer.** Post-hacks Magic Labs/Google OAuth. Pas d'insurance tiers, pas de "Polymarket safe mode" hardware-wallet-native.

### 6.2 Segments utilisateurs sous-servis

- **Retail US post-relaunch waitlist** — tax/sports-book/education ont tous shipped pour crypto-native global, la surface CFTC US est fresh, backlog captif.
- **Bettors sportifs sérieux** — CLV, closing-line value, EV prop-bets, parlay n'existent quasi pas en format prediction-market.
- **Desks macro pro / quant funds** — Coalition Greenwich flash-survey janvier 2026 (53 spécialistes market-structure) confirme intérêt montant mais concerns data. FIX, compliance audit trail, VAR sous-servis.
- **Rédactions / journalistes** — Dow Jones/WSJ partnership actif. Pas de produit embed + story-lead + auto-alert éditorial.
- **Académiques** — Polymarket Microgrants nomme explicitement "data analysis for academic purposes" comme gap qu'ils veulent remplir.
- **Casual/mainstream non-crypto** — onboarding, withdrawal, "que s'est-il passé" sont brutaux. Énorme gap pour un produit concierge-style.
- **International non-EU (LATAM, SEA ex-Singapour, Afrique)** — fiat on-ramps thin, analytics en langues locales quasi-inexistant.
- **Hedge funds exploring prediction markets comme alt-data** — appétit confirmé, pipelines data SOC2-compliant nascents.
- **CPAs et professionnels du fisc** — 2-3 boutiques ; opportunité white-label API pour CoinTracker, Koinly, TurboTax, H&R Block.

### 6.3 Opportunités de positionnement — synthèse ranked

**Tier A — Plus gros gisements, défendables**

1. **"Arkham/Nansen for Prediction Markets" — wallet clustering + entity labelling + smart-money signals.** Tous les traders veulent, personne ne livre proprement. Graph-analysis Polygon + Solana, clustering heuristique (funding, timing, gas patterns), labels crowdsourcés, alerts payantes. Moat data + effets de réseau. Difficulté : moyenne-haute.

2. **Tax + compliance stack pour Polymarket US (B2B + B2C).** Time-critical (première filing season Q1 2026 sur 2025, bien plus gros Q1 2027). Dual-reporting Polymarket US CFTC 1099-B + USDC global on-chain ; section 1256 vs. ordinary income ; wash-sale ; white-label API pour TurboTax/Koinly. Concurrents boutiques non scalés. Difficulté : moyenne.

3. **Resolution intelligence / UMA dispute tracker + insurance.** Tout gros bettor déteste le problème ; NYT/WSJ/ibtimes ont couvert. Pending-dispute alerts, UMA voter concentration, reversal rates par market type, option insurance. Difficulté : moyenne.

**Tier B — Solides opportunités mid-size**

4. **Terminal sports-book-grade pour Polymarket US beta + Kalshi.** Sports = 90% Kalshi, 100% Polymarket US. Les bots sports existants sont AI-prediction, pas sportsbook-pro (CLV, line-shop vs DK/FD/bet365, arb cross). Difficulté : moyenne.

5. **Produit newsroom/journaliste — "Probability press kit".** Premium pricing. Widgets embed-ables, citations auto ("as of…"), alert feeds pour éditeurs. Vise newsrooms non-Bloomberg. Difficulté : basse-moyenne.

6. **Smart order router d'exécution cross-venue.** Data aggregators crowdés, l'exécution reste vide. Intégration CLOB + Kalshi + Limitless. Matchr et Stand touchent, space ouvert. Difficulté : haute.

**Tier C — Niches atteignables**

7. **Data subscription institutionnelle mid-market** (compétiteur Bloomberg Terminal à prix non-Bloomberg). Verso positionné, catégorie ouverte. FinFeedAPI normalized + Oddpool-style streaming + audit exports. Nécessite SOC2.

8. **Security/insurance layer pour comptes Polymarket.** Recurring revenue sticky post-Magic Labs hacks. Hardware-wallet "safe mode", anomaly detection, small insurance.

### 6.4 Zones saturées à éviter

- **Copy-trading bots** (Polycule, Okbet, Stand, BetMoar, SOL Decoder, Polycool, KreoPoly…) — et risque accru audit Polymarket
- **Whale-alert Telegram bots** (15+ : PolyxBot, DropsBot, PolyAlertHub, Polywhaler, PolyIntel, PolyTracker, Polylerts, polymarket-whales.xyz, MobyScreener)
- **Agents IA "research" génériques** (20+ : Polysights, Alphascope, PolyBro, Polyseer, Astron, PolyOracle, PolyRadar, Billy Bets, PolyMaster, Jatevo, Polytrader, Rainmaker, Semantic 42, Inside Edge, Predly, Forcazt, PolyPulse, Polyprophet, PolyTale, Polymarket Tips, Polyfactual)
- **Dashboards leaderboard basiques** (PolymarketAnalytics.com, HashDive, Parsec, Polymtrade)

### 6.5 Risques à anticiper pour tout nouvel entrant

- **Audit Polymarket du 14 avril 2026** (Polycool, Kreo) — Builders Program sous scrutin, marketing "insider"-adjacent va déclencher enforcement. Consultez : financefeeds.com/polymarket-probes-startups-offering-copy-trading-tools-linked-to-insider-activity
- **Edge decay rapide** — Stand.trade fondateur : "old strategies don't apply; markets adapt". Whales évadent activement copy-trading via multi-wallets (blog Oracle Polymarket sept. 2025).
- **Commoditization** — GitHub open-source + tuto QuickNode = base product sans moat.
- **Régulatoire** — Polymarket US CFTC règles strictes, ICE oversight, copy-trading peut glisser en investment advisor / fund territory si exécuté, pas seulement signalé.
- **Défensabilité vs Polymarket in-house** — tout produit doit supposer que Polymarket shippe un v1 "good-enough" en 6-12 mois et se différencier sur la verticale.

---

## Conclusion

L'écosystème analytics Polymarket est entré en **phase de maturité fragmentée** : les couches de base (leaderboards, whale alerts, copy-bots) sont commodity, l'infrastructure institutionnelle vient de s'installer (ICE, Jump, Wintermute, Susquehanna via BitGo, 5c(c) Capital, Millennium), et le régulatoire se durcit (audit Polymarket, CFTC DCM). Pour un projet de data exploitation, **trois voies stratégiques se détachent nettement** : la **déanonymisation-labelling** (Arkham playbook), la **compliance/tax dual-reporting** (timing crucial post-US relaunch), et la **resolution intelligence** (UMA disputes, un gap émotionnel de la communauté). Deux voies secondaires offrent du *revenue* ciblé : **produit journaliste** (capitaliser sur Dow Jones/WSJ/Substack partnerships) et **terminal sports-book** (tirer profit du pivot US sports-first). Le compte Twitter narratif façon Lookonchain est probablement le canal d'acquisition le plus rentable à court terme quel que soit le produit build. La leçon macro du pricing Nansen 2025 est sans appel : la fenêtre prosumer vit entre **$10 et $50/mo**, le premium institutionnel passe par **APIs à $5-50K/an** — pas de SaaS confusing tiers entre les deux.