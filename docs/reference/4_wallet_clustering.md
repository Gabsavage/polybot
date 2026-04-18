# Détection de trading informé et clustering de wallets sur Polymarket — État de l'art technique

**Bottom line up front.** Sur un marché de prédiction binaire on-chain comme Polymarket, trois techniques dominent nettement le rapport effort/valeur et devraient être construites en premier : (1) **l'edge réalisé post-résolution et le Closing Line Value (CLV)** adossés à un contrôle FDR de Benjamini-Hochberg, (2) **le clustering par deposit-address-reuse de Victor (2020)** couplé au mapping déterministe proxy↔EOA via les events `ProxyCreation` des factories Polymarket, et (3) **les tests d'event-study pré-résolution avec CAR** sur la fenêtre précédant les news publiques. À l'inverse, les implémentations canoniques de **PIN et VPIN** empruntées à la microstructure actions sont techniquement adaptables mais cassent sur plusieurs hypothèses-clés (prix bornés, mint/burn, cross-contract dependency) et rendent peu pour l'effort consenti. La quasi-totalité des "découvertes" d'insider trading publiées sur X/Twitter sont statistiquement vides faute de contrôle du multiple testing — le cas médiatique "Fredi9999" (~$85M de gains, 11 wallets clustérisés par Chainalysis) a été classifié après enquête comme *skillful modeler* avec sondages privés, pas insider. La détection d'**insider au sens légal** par les seules données on-chain est **impossible** : on produit au mieux un *suspicion score* probabiliste qui impose une investigation manuelle. Le rapport ci-dessous détaille huit axes, formule chaque technique avec équations, pseudo-code et stacks d'implémentation, et termine par une matrice de priorisation globale.

---

## 1. Littérature académique sur le trading informé

### 1.1 Fondamentaux des prediction markets

Les papiers fondateurs sont **Wolfers & Zitzewitz (JEP 2004)** qui taxonomise les contrats en winner-take-all, index contracts et spread betting — Polymarket relève du premier — et **Wolfers & Zitzewitz (NBER WP 12200, 2006)** qui prouve que sous utilité log et budgets identiques, le prix $p$ coïncide avec la croyance moyenne $\bar{q} = E_F[q]$. **Manski (2004, 2006)** apporte la critique décisive : avec traders risk-neutral et croyances hétérogènes, $p$ n'est qu'un *quantile budget-pondéré* et ne révèle que des bornes sur $\bar{q}$ ; pour $p<0.5$, $\bar{q} \in [p^2, 2p-p^2]$. Les prix extrêmes sur-estiment mécaniquement l'écart à 0.5 — **biais directement pertinent pour Polymarket** où de nombreux contrats résident dans les queues. **Arrow et al. (Science 2008)** pose les prediction markets comme mécanisme d'agrégation hayékien.

Côté empirique récent, **Tsang & Yang (2026, arXiv:2603.03136, 2603.03152)** fournit la première analyse on-chain transaction-level de Polymarket (élection 2024), avec une décomposition exchange-equivalent volume / net inflow / gross activity et mesure d'un **Kyle's λ déclinant d'un ordre de grandeur** sur la vie du marché. **Ng, Peng, Tao & Zhou (SSRN 5331995, 2026)** compare price discovery cross-platform (Polymarket, Kalshi, PredictIt, Robinhood). **Rasooly & Rozzi (arXiv:2503.03312, 2025)** montre par expérience de terrain que la manipulation sur prediction markets produit des **effets détectables jusqu'à 60 jours** après les trades, résultat contraire à **Rhode & Strumpf (JEP 2004, 2007/2008)** qui documentait une résistance à la manipulation au-delà de quelques heures (field experiment IEM 2000, attaque TradeSports 2004 sur Bush). Le cas **Fredi9999/Théo** (octobre–novembre 2024, documenté par Bloomberg, WSJ, Cointelegraph) illustre le problème d'identification central : 11 wallets clustérisés par Chainalysis via *funding patterns + timing + cash-out deposit addresses communes*, ~$85M de profit, classifié *non-manipulation* après enquête Polymarket. Chaos Labs/Inca Digital estiment par ailleurs ~30 % du volume 2024 comme wash trading — chiffres non pair-reviewed.

### 1.2 Détection d'insider trading sur marchés traditionnels

Le **modèle PIN** (Easley, Kiefer, O'Hara & Paperman, *JF* 1996) est un modèle génératif bayésien du flux d'ordres. Chaque jour, probabilité $\alpha$ d'événement informationnel ; conditionnellement, prob $\delta$ de mauvaise nouvelle. Les informés arrivent en Poisson d'intensité $\mu$ ; les non-informés en Poisson indépendants $\varepsilon_B, \varepsilon_S$. La probabilité de trading informé est :

$$\text{PIN} = \frac{\alpha \mu}{\alpha \mu + \varepsilon_B + \varepsilon_S}$$

La likelihood journalière avec $B_i$ buys et $S_i$ sells est la somme des trois régimes pondérés par $(1-\alpha)$, $\alpha\delta$, $\alpha(1-\delta)$. L'estimation par MLE est **notoirement instable** : floating-point underflow pour actions actives (Lin & Ke 2011), solutions de bord fréquentes, multi-optima (grid search sur starting values obligatoire), jusqu'à 42 % de la market cap NYSE non-estimable dans Yan & Zhang (2012). Sur Polymarket, la définition de "jour" sur une blockchain 24/7 est ambiguë, la classification aggressor nécessite une heuristique Lee-Ready adaptée, et la **dépendance cross-contract** (YES + NO, marchés enfants/parents) viole l'hypothèse de Poissons indépendants.

Le **VPIN** (Easley, López de Prado, O'Hara, *RFS* 2012) abandonne le MLE et opère en volume-clock. Pour chaque bucket de volume $V$ fixe :

$$V^B_\tau = V \cdot \Phi\!\left(\frac{\Delta P_\tau}{\sigma_{\Delta P}}\right), \quad V^S_\tau = V - V^B_\tau, \quad \text{VPIN} = \frac{\sum_{\tau=1}^n |V^B_\tau - V^S_\tau|}{n V}$$

où $\Phi$ est la CDF normale standard (bulk volume classification). **Andersen & Bondarenko (JFM 2014)** démontrent que VPIN a picé *après* le Flash Crash et pas avant, et qu'en contrôlant pour volume et volatilité, son pouvoir prédictif est nul. Sur Polymarket, BVC avec $\Phi$ gaussien est **inadapté près des bornes** où $\Delta P$ est tronqué ; une adaptation via transformation logit $\ell_t = \log(p_t/(1-p_t))$ ou distribution Student-t asymétrique est indispensable.

**Kyle (1985)** fournit le modèle canonique d'adverse selection. À l'équilibre linéaire $p = p_0 + \lambda y$ avec $y = x + u$, on a $\lambda = \sigma_v/(2\sigma_u)$. Empiriquement, Hasbrouck (2009) estime $\lambda$ par régression $r_t = \lambda \cdot \text{sign}(Q_t)\sqrt{|\text{volume}_t|} + \epsilon_t$. **Sur Polymarket, $\sigma_v$ est borné par 0.5** (variance Bernoulli) : $\lambda$ est mécaniquement compressé, interpréter avec prudence. Tsang & Yang (2026) l'appliquent déjà en travaillant en log-odds.

**Glosten-Milgrom (*JFE* 1985)** est en réalité le modèle **le plus naturellement adapté à Polymarket** : valeur binaire $v \in \{v_L, v_H\}$ correspond exactement au payoff $\{0,1\}$ d'un outcome token. Le spread pur adverse-selection est $a-b = \alpha(v_H - v_L)$, décomposé à la Huang-Stoll (*RFS* 1997) en $\pi_{AS} + \pi_{IH} + \pi_{OP}$. Sur l'AMM/CLOB hybride Polymarket, $\pi_{IH} \approx 0$ : focus sur le split AS/OP. **Hasbrouck Information Share (*JF* 1995)** s'applique directement pour comparer price discovery entre Polymarket, Kalshi, PredictIt, Betfair sur contrats identiques — déjà fait par Ng et al. (2026).

### 1.3 Betting markets — littérature directement transposable

**Levitt (*EJ* 2004)** montre que les bookmakers NFL maximisent profit en exploitant les biais des bettors plutôt qu'en balançant le book — Polymarket en CLOB est plus proche des marchés financiers. **Thaler & Ziemba (*JEP* 1988)** documente le **favorite-longshot bias** : longshots sous-performent, favoris sur-performent ; Saguillo et al. (2025) suggèrent une présence similaire sur Polymarket ("buy NO" structurellement profitable). **Brown (*Applied Economics* 2012)** sur Betfair tennis teste l'insider via ratio $\sigma^2_{pre}/\sigma^2_{post}$ autour d'événements publics — méthodologie idéale pour Polymarket. **Schnytzer, Lamers & Makropoulou (2008, *IJF* 2010)** estiment 20–30 % du volume horse racing australien comme informé via Shin (1991, 1993) et fournissent le gold-standard méthodologique. **Dubow & Monteiro (FSA 2006)** formalise l'APPM (Abnormal Pre-announcement Price Movement) — directement implémentable.

### 1.4 Récapitulatif Axe 1

| Technique | Formule-clé | Difficulté | Robustesse FP | Transposabilité PM |
|---|---|---|---|---|
| PIN (EKOP 1996) | $\alpha\mu/(\alpha\mu+\varepsilon_B+\varepsilon_S)$ MLE | 4/5 | Moyenne | **Adaptation majeure** |
| VPIN (ELO 2012) | $\sum\|V^B-V^S\|/(nV)$ via BVC | 2/5 | **Faible** (AB 2014) | Adaptation majeure |
| Kyle's λ | $\lambda = \sigma_v/(2\sigma_u)$ ; OLS | 2/5 | Moyenne | Adaptation mineure |
| Glosten-Milgrom | $a-b = \alpha(v_H-v_L)$ | 3/5 | Élevée | **Directe ⭐** |
| Huang-Stoll 3-way | GMM sur $\Delta P = (S/2)(\pi_{AS}+\pi_{IH})Q_{t-1}+\ldots$ | 3/5 | Bonne | Adaptation mineure |
| Hasbrouck IS | VECM + Cholesky | 4/5 | Modérée | Directe |
| Event-window σ² (Brown 2012) | $\sigma^2_{pre}/\sigma^2_{post}$ | 2/5 | Excellente | **Directe ⭐** |
| Favorite-longshot test | ROI calibration | 1/5 | Élevée | Directe |

---

## 2. Détection d'anomalies de trading

### 2.1 Techniques statistiques

Le **z-score robuste sur sizing** est la primitive la plus fondamentale. La version classique $z = (x-\mu)/\sigma$ est dominée par la version MAD (Leys et al. 2013) :

$$z_{rob} = \frac{x - \text{median}(X)}{1.4826 \cdot \text{MAD}(X)}$$

avec MAD = $\text{median}(|x_i - \text{median}(X)|)$. Les distributions de `size` Polymarket étant power-law, seule la version MAD (ou log-transform préalable) tient debout. **Deux variantes à distinguer** : intra-wallet (vs historique du wallet lui-même, détecte un wallet qui "change de régime") et cross-wallet (vs distribution sur le marché, détecte outliers absolus). Seuils usuels $|z_{rob}| \geq 3.5$ conservateur, $\geq 5$ très anormal.

La **détection de conviction trades** est le *killer feature* des marchés binaires. Un trader achetant YES à $p_m = 0.30$ avec taille $S$ révèle une croyance $p_b \geq p_m$ et un edge relatif $e_{rel} = (p_b - p_m)/p_m$. Règle pratique :

```python
def classify_conviction(trade, ctx, fair_price_fn, th):
    p_m, S = trade["price"], trade["size_usdc"]
    p_hat = fair_price_fn(trade["market_id"], trade["ts"])
    edge_abs = max(0, p_hat - p_m) if trade["side"]=="BUY_YES" else max(0, p_m - p_hat)
    edge_rel = edge_abs / max(p_m, 1e-6)
    ev_dollar = S * edge_abs / max(p_m, 1e-6)
    size_ratio = S / ctx["median_trade_size"]
    return ev_dollar >= th["tau_abs"] or (size_ratio >= th["k_S"] and edge_rel >= th["tau_e"])
```

avec typiquement $\tau_{abs} \in [500, 2000]$ USD, $k_S = 10$, $\tau_e = 0.20$. Le proxy $\hat{p}$ pour $p_b$ peut être une moyenne pondérée des marchés corrélés, un oracle externe (Pinnacle devigué), ou un modèle maison.

L'**event study** (MacKinlay 1997) mesure le CAR pré-événement : $AR_t = r_t - E[r_t]$ estimé par market model sur fenêtre d'estimation, $CAR(t_1, t_2) = \sum AR_t$, test $\theta = CAR/\hat\sigma(CAR) \sim \mathcal{N}(0,1)$. Sur Polymarket, les events sont les résolutions UMA, annonces externes, et timestamps de proposition/dispute. Un $CAR$ pré-événement anormalement grand dans la direction correcte de résolution = **signal de leak**.

Le **clustering temporel via Hawkes process** modélise l'intensité conditionnelle self-exciting :

$$\lambda^*(t) = \mu + \sum_{t_k < t} \alpha e^{-\beta(t-t_k)}$$

avec branching ratio $n = \alpha/\beta < 1$. Un $n$ élevé sur un side d'outcome = clustering anormal. La version multivariée détecte la **cross-excitation** entre wallets (wallet A trade ⇒ wallet B trade) — signature de coordination. Librairies : `tick`, `hawkeslib`.

Le **change point detection** se décline en trois classiques. CUSUM one-sided : $S_n^+ = \max(0, S_{n-1}^+ + (x_n - \mu_0) - k)$, alarme quand $S_n^+ > h$, calibration via ARL cible (ex. ARL0=500, ARL1=7 ⟹ $k \approx 0.60\sigma, h \approx 3.80\sigma$). **BOCPD** (Adams & MacKay 2007) maintient online la distribution de la run length via message-passing avec conjugate updates — approche Bayesian exacte. **PELT** (Killick et al. 2012) offre la détection multi-changepoints en $O(n)$ via pruning, objectif $\min \sum \mathcal{C}(y) + \beta m$. **GARCH(1,1)** classique détecte les spikes de volatilité pré-résolution, mais sur Polymarket il faut utiliser les logit-returns sinon il casse aux bornes.

### 2.2 Machine Learning

L'**Isolation Forest** (Liu, Ting, Zhou 2008) domine sur features tabulaires modérées. Score $s(x,\psi) = 2^{-E[h(x)]/c(\psi)}$ avec $c(\psi) = 2H(\psi-1) - 2(\psi-1)/\psi$. Features Polymarket pertinentes : `log(size)`, `price_deviation_from_vwap_60m`, `time_to_resolution`, `wallet_age_days`, `wallet_nb_trades_prior`, `outcome_imbalance_5min`, `gas_price_percentile`, `market_liquidity_depth`. Scalable, robuste aux features non pertinentes, calibrer `contamination` à 0.01 puis seuiller au quantile 99.5 %.

Les **autoencoders** (loss MSE sur reconstruction) conviennent mieux en haute dimension et sur séquences (LSTM-AE sur trajectoires wallet). **One-Class SVM** (Schölkopf 2001) avec $\nu \in [0.01, 0.05]$ impose l'approximation Nystroem au-delà de ~50k trades. **LOF** (Breunig 2000) est particulièrement adapté aux populations hétérogènes (retail vs pro coexistent), $k \in [10,50]$.

Le **supervised learning avec ground truth post-résolution** labelise un trade comme "prescient" ssi (a) côté gagnant, (b) edge réalisé significatif $(r-p_m)/p_m \geq 0.5$, (c) placé pré-événement informationnel. **Règle absolue** : aucune feature encodant l'outcome ne doit entrer dans $X$ ; split train/test temporel strict sur $t_{résolution}$. Modèles : XGBoost/LightGBM avec `scale_pos_weight` élevé, calibration isotonic post-hoc.

Le **self-supervised contrastive learning** (SimCLR-style, Chen et al. 2020) produit des embeddings de wallets sans labels via NT-Xent loss :

$$\ell_{i,j} = -\log \frac{\exp(\text{sim}(z_i,z_j)/\tau)}{\sum_{k \neq i} \exp(\text{sim}(z_i,z_k)/\tau)}$$

Augmentations temporelles : temporal cropping, jitter des timestamps, masking, feature dropout. Transformer encoder avec time2vec embedding sur séquences `(price, size, Δt, market_id, side)`. Exploite les millions de trades on-chain sans labels — coût MLOps élevé. Les **Temporal GNN (TGN, TGAT)** sur graphe hétérogène (wallet, market, trade) sont la frontière actuelle pour détecter Sybils et coordination (Rossi et al. 2020, Xu et al. 2020).

### 2.3 Récapitulatif Axe 2

| Technique | Difficulté | Données | FP | PM |
|---|---|---|---|---|
| Z-score MAD intra/cross | 1/5 | Mo | Bonne | Directe |
| Conviction trades | 2/5 | Mo + fair price | Moyenne | **Directe ⭐** |
| Event study CAR | 3/5 | Go | Bonne | Adaptation mineure |
| Hawkes self/cross-excitation | 4/5 | Mo–Go | Moyenne | Directe |
| CUSUM | 2/5 | Mo | Bonne | Directe |
| BOCPD | 4/5 | Mo | Bonne | Directe |
| PELT | 3/5 | Mo | Bonne | Directe |
| GARCH logit | 3/5 | Mo | Moyenne | Adaptation mineure |
| Isolation Forest | 2/5 | Mo | Bonne | **Directe ⭐** |
| Autoencoder / LSTM-AE | 3/5 | Go | Moyenne | Directe |
| One-Class SVM | 3/5 | Mo | Moyenne | Adaptation mineure |
| LOF | 2/5 | Mo | Moyenne | Directe |
| Supervised GBM | 3/5 | Go | Bonne si no leak | **Directe ⭐** |
| Contrastive SSL | 5/5 | 10+ Go | Variable | Adaptation majeure |
| Temporal GNN | 5/5 | 100 Go | Variable | Adaptation majeure |

---

## 3. Clustering et attribution de wallets

### 3.1 L'architecture proxy Polymarket change la donne

Presque aucun utilisateur Polymarket n'interagit directement avec le CTFExchange depuis un EOA : **chaque utilisateur possède un proxy wallet** (smart contract) qui détient les positions ERC-1155 et le collatéral USDC. Deux factories distinctes selon l'authentification :

| Auth | Factory | Wallet | Signature |
|---|---|---|---|
| MetaMask / EOA externe | Safe Proxy Factory `0xaacFeEa03eB1561C4e67d661e40682Bd20E3541b` | Gnosis Safe 1-of-1 | sig type 2 |
| Magic.link (email/Google) | Polymarket Proxy Factory `0xaB45c5A4B0c941a2F231C04C3f49182e1A254052` | EIP-1167 CREATE2 déterministe | sig type 1 |

Pour les wallets Magic, `proxyAddress = getCreate2Address(factory, keccak256(abi.encode(eoa)), initCodeHash)` — **l'adresse du proxy est une fonction déterministe de l'EOA owner**. Pour les Safe wallets, l'`owner` est lisible via `getOwners()` et l'event `ProxyCreation`. La conséquence est radicale : la table `(proxy_address, eoa_owner, factory, block)` est du **ground truth on-chain gratuit** qu'il faut construire en premier, avant toute analyse Polymarket. Sans cette table, on double-compte les users uniques et on sous-compte l'activité réelle par humain.

Ceci ne résout que la moitié du problème. Un utilisateur peut avoir **plusieurs proxies** en se loggant via MetaMask *et* Magic avec des EOA différents — 2 proxies, 2 EOA, rien sur la chaîne ne les lie directement. Pour les relier il faut les heuristiques classiques appliquées au niveau EOA owner.

### 3.2 Heuristiques transposables EVM

**Co-spending Meiklejohn (IMC 2013)** est strictement inapplicable en EVM (account model, pas d'UTXO). On en garde la méthodologie abstraite : "des adresses liées signent ensemble" se reporte sur les patterns same-tx et contract-creator.

**Common Funding Source (CFS)** est l'heuristique la plus productive à volume. Deux wallets financés initialement par la même adresse source $S$ sont candidats au même cluster si $S$ a fundé moins de $N_{max} \approx 20$ wallets dans une fenêtre $T_{max} \approx 30$ jours. Sources CFS typiques Polygon : Polygon PoS Bridge, Across (`0xc186fA9...`), Stargate, Circle CCTP, Moonpay/Transak/Ramp, retraits de CEX. **Faux positif majeur** : hot wallets Binance (`0xF977814e90dA44bFA03b6295A0616a897441aceC`) qui fund des millions d'adresses — il faut filtrer les addresses de service et utiliser les **deposit addresses** par client, pas les hot wallets. Implémentable en 30 lignes de SQL Dune.

**La deposit-address-reuse heuristic de Victor (FC 2020, LNCS 12059)** est **de très loin la technique la plus puissante sur Polymarket**. Les exchanges créent une deposit address unique par client qui forward vers une hot wallet. Si deux wallets envoient à la même deposit address forwardant à un exchange connu, ils sont présumés appartenir au même client. Algorithme : pour chaque chemin $v_u \to v_d \to v_e$ avec $v_e \in V_{exch}$, ajouter un edge $(v_u, v_d)$ conditionné sur `amount_diff ≤ a_max` et `block_diff ≤ t_max` ; composantes faiblement connexes = clusters. Paramètres typiques : $a_{max} = 0.01$ ETH, $t_{max} = 3200$ blocs. **C'est littéralement l'heuristique utilisée par Chainalysis** dans le cas Fredi9999, où 10 des 11 proxies cashaient vers les **mêmes 2 deposit addresses CEX**.

Les autres heuristiques Victor (self-authorization via `approve` + `transferFrom`, airdrop multi-participation, contract creator-deployer) sont utiles mais secondaires sur Polymarket. **GraphSense** (Graz, arXiv:2102.13613) implémente open-source l'ensemble, avec un adapter Ethereum portable vers Polygon mais une infrastructure Cassandra+Spark lourde (~2–4 TB, 128+ GB RAM).

Les heuristiques **temporal correlation** (Béres et al., IEEE DAPPS 2021, arXiv:2005.14051) construisent un vecteur 168 bins (7j × 24h) d'activité par wallet et mesurent la similarité cosine, idéalement avec distance Wasserstein ou KL. Seuil usuel $\theta = 0.8$ après normalisation et filtre $\sum v_w \geq 50$ tx. **Faux positifs massifs** : bots 24/7 (distribution uniforme), activité news-driven (tous concentrés). À n'utiliser qu'en combinaison. **Gas price fingerprinting** (Béres et al.) est quasi-inutile sur Polymarket car les proxies utilisent le Gas Station Network — les tx sont relayées, la fingerprint reflète le relayer. **Same-tx interaction** via Disperse (`0xD152f549545093347A162Dce210e7293f1452150`) est utile pour détecter distributions de sybils. **ENS / Farcaster / Lens reverse-resolve** est du gratuit et directement exploitable.

### 3.3 Détection de self-matching sur CTFExchange

Un insider fragmenté avec proxies $P_1, \ldots, P_k$ peut se matcher lui-même via un `OrderFilled(maker=P_i, taker=P_j)`. Construire le graphe `(maker, taker, count, volume)` puis crosscheck avec les clusters CFS/Victor détecte le wash-trading. Estimation Columbia 2025 : ~25 % du volume Polymarket serait wash-trading entre comptes liés — à recomputer avec méthodologie propre.

### 3.4 Outils commerciaux

**Arkham Intelligence** (freemium web, API enterprise sur devis) : 300M+ labels, couverture Polygon excellente, bounty system ARKM, proxy Polymarket souvent déjà tagué avec EOA lié. **Nansen Smart Money** ($49–$69/mo depuis oct. 2025) : Wallet Profiler + labels, pas de clustering explicite wallet-to-wallet. **Chainalysis Reactor** (~$40k/seat/an LE, enterprise $100k–$500k+) : l'outil qui a produit l'analyse Fredi9999 publique ; méthodologie black-box, erreur non-publiée (admis par lead investigations en cour). **TRM Labs** (~$10k+/seat) : meilleur cross-chain bridges, "glass box attribution". **Elliptic** : compliance fintech. **Breadcrumbs.app** ($49/mo+) : coverage Polygon limitée. **Dune + Allium/Zettablock** ($399/mo à $50k+) : le sweet spot pour implémenter les heuristiques soi-même à coût modique — les tables `polymarket_polygon.*` sont déjà décodées.

### 3.5 Récapitulatif Axe 3

| Heuristique | Difficulté | Coût data | FP typique | PM |
|---|---|---|---|---|
| Co-spending UTXO | — | — | — | Impossible |
| **CFS** | 2/5 | Bas (Dune) | Hot wallets CEX partagées | **Directe ⭐** |
| Temporal correlation 168 bins | 3/5 | Moyen | Bots 24/7 | Mineure→Majeure |
| Gas fingerprinting | 2/5 | Bas | — | Mineure (GSN masque) |
| Same-tx / Disperse | 2/5 | Bas | Payroll services | Majeure |
| Behavioral fingerprint | 4/5 | Moyen-Haut | Users dApps identiques | Majeure |
| ENS/Farcaster/Lens | 2/5 | Bas | ENS transféré | Directe |
| **Victor deposit-address-reuse** | 3/5 | Moyen | Deposit partagé (rare) | **Directe ⭐⭐** |
| Self-authorization | 3/5 | Moyen | Vaults légitimes | Mineure |
| Airdrop multi-participation | 3/5 | Moyen | Power-user | Indirecte |
| **Proxy↔EOA via ProxyCreation** | 2/5 | Bas | — (ground truth) | **Directe, essentielle** |
| Bridge depositor linking | 3/5 | Moyen | Relayers intermédiaires | Directe |
| Cash-out reuse (Chainalysis style) | 3/5 | Moyen | Coïncidence gros CEX | **Directe ⭐** |
| Self-matching CTFExchange | 4/5 | Moyen | Market-makers légitimes | Directe |

---

## 4. Détection de sharp wallets et copy-trading

### 4.1 PnL on-chain : formule canonique et pitfalls

Trois events Conditional Tokens sont au cœur : `PositionSplit` (mint d'un full set YES+NO contre 1 USDC), `PositionsMerge` (inverse), `PayoutRedemption`. Formule robuste en flux nets USDC :

$$\text{PnL}_{w,c} = \text{USDC}_{in}(w,c) - \text{USDC}_{out}(w,c) - \text{fees} - \text{gas}$$

où `USDC_in` = ventes + merges + redemptions, `USDC_out` = achats + splits. Cette formulation évite la modélisation explicite du cost basis. **Pitfalls majeurs** : (a) positions héritées via transferts ERC-1155 directs — politique *strict* (exclure les `conditionId` concernés) ou *clustering* (agréger les wallets liés) ; (b) marchés en cours : mark-to-market au VWAP fenêtre courte avec **liquidity haircut** pour les marchés à profondeur < $10k ; (c) splits/merges sont de la création d'inventaire, **jamais des signaux directionnels** — $PositionSplit.amount$ n'est pas un achat de conviction ; (d) redemptions jamais appelées = payout virtuel à comptabiliser ; (e) fees Polymarket ont évolué de 0 % en 2024 à des taker fees dynamiques en 2025–2026 (~1.8 % Crypto, 0.75 % Sports, 0 % Geopolitics, en formule $\text{fee}(p) = \text{fee}_{peak} \times 4p(1-p)$ typiquement), tout backtest multi-année doit appliquer le schedule daté ; (f) gas Polygon négligeable (\<$0.05/trade) sauf pour bots HFT où cela cumule à ~$500.

### 4.2 Métriques de skill, de la moins à la plus robuste

Le **Sharpe ratio** $\text{SR} = (\bar{R}-R_f)/\hat\sigma$ est fragile sur Polymarket (distributions leptokurtiques, returns non-i.i.d., skewed). Le **Probabilistic Sharpe Ratio** de Bailey & López de Prado (2012) corrige :

$$\text{PSR}(SR^*) = \Phi\!\left(\frac{(\widehat{SR}-SR^*)\sqrt{T-1}}{\sqrt{1-\hat\gamma_3 \widehat{SR}+(\hat\gamma_4-1)\widehat{SR}^2/4}}\right)$$

Le **Deflated Sharpe Ratio** (2014) pousse plus loin en corrigeant le selection bias lié au multiple testing : $SR^* = \sqrt{\text{Var}(SR_s)} \cdot [(1-\gamma)\Phi^{-1}(1-1/N) + \gamma\Phi^{-1}(1-1/(N e))]$ avec $\gamma \approx 0.5772$.

Mais **la métrique la plus naturelle sur Polymarket est l'edge réalisé post-résolution** :

$$\text{edge}_i = s_i \cdot (o_i - p_{\text{entry},i})$$

avec $s_i \in \{+1, -1\}$ pour long YES / long NO et $o_i \in \{0,1\}$. Moyenne sur $N$ trades, $t$-stat $= \bar{\text{edge}} \cdot \sqrt{N}/\sigma(\text{edge})$. **C'est l'alpha pur post-résolution que DeFi perps ne fournit pas** : le ground truth binaire donne un signal propre. Conjointement, les **proper scoring rules** :

$$\text{BS} = \frac{1}{N}\sum(p_i - o_i)^2, \quad \text{LS} = -\frac{1}{N}\sum[o_i\log p_i + (1-o_i)\log(1-p_i)]$$

Le skill score normalisé $\text{BSS} = 1 - \text{BS}_{wallet}/\text{BS}_{market}$ est positif ssi le wallet bat la sagesse des prix en contemporain des trades. Le **Kelly fit** teste la rationalité de sizing : pour un BUY YES, $f^*_{YES} = (p^*-p_m)/(1-p_m)$ ; un coefficient $\alpha \approx 0.3$ constant sur centaines de bets (Kelly fractionnel prudent) signe un trader rationnel, tandis qu'un bet constant ou $\alpha > 1$ signe non-skill.

Le **Closing Line Value (CLV)** est standard en sports betting, trivial à calculer ($CLV = p_{close} - p_{buy}$ pour un BUY YES), et très bon prédicteur du skill long-terme. À Polymarket, la résolution même est le meilleur "closing price" : $p_{close} \in \{0,1\}$. **Limite** : le CLV est trivial si $p_{close}$ converge juste parce que l'outcome devient public — préférer $CLV = p(T-\delta) - p_{buy}$ avec $\delta$ choisi selon type de marché. Et surtout, **CLV ne distingue pas skill, insider et manipulator** — tous trois ont CLV > 0.

### 4.3 Filtres anti-luck obligatoires

**Sample size**. Sous Lo (2002), $\text{Var}(\widehat{SR}) \approx (1 + SR^2/2)/T$. Pour détecter $SR=1$ à puissance 80 %, $T \approx 30$ ; pour $SR=0.5$, $T \approx 100$ ; avec kurtose Polymarket, multiplier par 2–3. **Règle empirique : $N \geq 100$ trades résolus**.

**Diversification**. $K \geq 20$ marchés distincts, $L \geq 3$ catégories, HHI < 0.2. Un wallet "one-hit wonder" sur Trump 2024 n'est pas un sharp.

**Multiple testing correction**. Sur $M = 10^5$ wallets testés à $\alpha = 5\%$, **5000 faux positifs** attendus sous $H_0$ global. **Bonferroni** trop conservateur, **Benjamini-Hochberg FDR** recommandé : trier $p_{(1)} \leq \ldots \leq p_{(M)}$, trouver max $i$ tel que $p_{(i)} \leq (i/M) q$, rejeter les $p_{(j)} \leq p_{(i)}$. **Non-négociable** pour toute production de leaderboard. **White's Reality Check** et **Hansen's SPA** pour data snooping stratégique — coût compute élevé.

**Survivorship bias**. On n'observe que les wallets actifs aujourd'hui. **Cohortes fixées à $t_0$** puis tracking forward incluant les wallets qui blow-up à zéro. **Selection bias "N trades min"** : filtrer ≥30 trades exclut systématiquement les sharps à basse fréquence → utiliser IPW ou Heckman two-step.

### 4.4 Copy-trading DeFi et transposition

**Nansen Smart Money** identifie <0.01 % des wallets comme Smart DEX Trader via filtres PnL + win rate + holding duration. **Arkham watchlists, DeBank, Zerion, Dune dashboards** couvrent le reste. Littérature académique : Barbon & Ranaldo (2023), Columbia 2025 sur wash trading Polymarket (25 %), a16z crypto et Flashbots sur toxicity LP Uniswap. **Copy-trading DeFi perp** : Perpy Finance (GMX), STFX, Kwenta. Lags d'exécution mempool ~2s Polygon + détection + soumission = fenêtre de front-running MEV. Capacity decay au-delà d'un seuil d'AUM suivant.

La transposition prediction markets présente **avantages nets** : ground truth explicite, pas de leverage, outcome binaire, horizon fini. **Inconvénients** : marchés éphémères, pas de continuité, liquidité fragmentée. Le **proper scoring rule leaderboard** (BSS + edge t-stat + DSR + Kelly fit, agrégés en z-scores pondérés) est la construction naturelle.

### 4.5 Récapitulatif Axe 4

| Métrique | Difficulté | Robustesse | PM |
|---|---|---|---|
| PnL on-chain résolu | 3/5 | — | Directe |
| Sharpe simple | 2/5 | Faible | Mineure |
| Sortino / Calmar | 2/5 | Moyenne | Directe |
| Hit rate | 1/5 | Faible (petits bets) | Directe |
| **Edge vs market entry** | 2/5 | **Haute** | **Directe ⭐⭐** |
| **Brier / BSS** | 2/5 | Haute (proper) | **Directe ⭐⭐** |
| **Log score** | 2/5 | Haute (proper) | **Directe ⭐** |
| Kelly fit | 4/5 | Haute | Directe |
| t-stat alpha | 2/5 | Moyenne | Directe |
| PSR / DSR | 4–5/5 | Haute → Très haute | Mineure |
| Bootstrap Ledoit-Wolf | 3/5 | Haute | Directe |
| **FDR Benjamini-Hochberg** | 2/5 | Haute | **Directe ⭐** |
| Reality Check / SPA | 5/5 | Très haute | Majeure |
| Cohort fixing | 3/5 | Haute | Directe |
| Wash-trading filter | 4/5 | Haute | Directe |

---

## 5. Graph analytics

### 5.1 Échelle et construction

Polymarket compte approximativement **1–3M wallets historiques** (dont dust), **200–500k wallets actifs significatifs** (≥10 trades), **30–60k marchés** (Neg Risk multi-outcomes démultipliés), **50–150M trades** on-chain `OrderFilled`. À cette échelle NetworkX est inutilisable en production — il faut **igraph, graph-tool, cuGraph ou Kuzu**.

Le graphe naturel est **hétérogène** : nœuds `{wallet, market, outcome, token}`, arêtes `{trade, transfer_erc1155, funding, control}`. La **projection wallet-wallet** via co-trading crée artificiellement des cliques sur marchés populaires (500 wallets sur Trump 2024 = $C(500,2) \approx 125000$ arêtes majoritairement bruit). Filtrer par p-value contre null model (Erdős-Rényi ou configuration model de mêmes degrés) ou par TF-IDF (pénaliser marchés populaires) est indispensable.

### 5.2 Techniques

**Community detection**. Louvain maximise la modularité $Q = \frac{1}{2m}\sum[A_{ij} - k_ik_j/(2m)]\delta(c_i,c_j)$ en $O(n \log n)$ greedy. **Leiden (Traag et al. 2019) à préférer systématiquement** : corrige le bug de communautés mal-connectées de Louvain, garantie connexité. Label Propagation rapide mais très instable. Infomap (flow-based) pertinent pour les graphes de transferts USDC. **Tous produisent des communautés même sur bruit** — toujours reporter $Q_{obs}/Q_{null}$, pas $Q$ seul.

**Centralité**. Degree trivial mais utile. Betweenness $O(VE)$ prohibitif au-delà de 100k nœuds, utiliser sampling. **PageRank** $PR(u) = (1-d)/N + d \sum PR(v)/L(v)$ en $O(k(V+E))$ avec $k \approx 50$ et damping $d=0.85$. **Personalized PageRank** biaisé sur un wallet seed = technique éprouvée pour remonter un insider ring.

**Similarity**. Jaccard sur ensembles de marchés, mais all-pairs $O(N^2)$ impraticable — utiliser **MinHash + LSH** (datasketch) pour scale. Corriger par TF-IDF pour neutraliser marchés populaires. Cosine sur vecteurs d'activité. SimRank trop coûteux.

**Graph Neural Networks**. GCN $H^{(l+1)} = \sigma(\tilde{D}^{-1/2}\tilde{A}\tilde{D}^{-1/2}H^{(l)}W^{(l)})$ transductif full-batch. **GraphSAGE** inductif avec sampling+aggregation — indispensable pour Polymarket (nouveaux wallets quotidiens). GAT pour attention sur voisins hétérogènes. **TGN / TGAT** (Rossi 2020, Xu 2020) maintiennent mémoire par nœud + attention temporelle — **state of the art pour fraud on-chain** (cf. BERT4ETH, TTAGN, EPAD sur Ethereum phishing).

**Motifs**. Enumération sous-graphes de taille 3–5 (ESU, FANMOD, orca). Motifs pertinents : *star funder* 1→N (airdrop farming), *chain transfer* A→B→C→D (layering), *triangular co-trading* synchrone (collusion), *back-and-forth ERC-1155* (wash trading pour leaderboard gaming). **Strongly Connected Components** (Tarjan $O(V+E)$) = marqueur robuste de wash-trading via cycles.

**Random walk embeddings**. DeepWalk, node2vec (params $p,q$ BFS/DFS), metapath2vec pour graphes hétérogènes. Alimentent un XGBoost ou HDBSCAN downstream.

### 5.3 Outils

**Kuzu** (embedded graph DB, columnar, Cypher, interop Parquet/Arrow, scale centaines de millions de nœuds single-machine) est le choix 2026 optimal pour analytics locales. **Neo4j Community GPLv3** (single-instance limité) pour exploration Cypher, Enterprise payante. **igraph** (C backend, GPL attention) domaine compromis 10M–100M arêtes. **graph-tool** (C++/OpenMP) le plus rapide mais install pénible via conda. **cuGraph** GPU pour >100M arêtes. **PyG / DGL** pour GNN. **NetworkX uniquement pour prototypes**.

### 5.4 Applications crypto et transposition

**Sybil airdrops** : Hop Protocol (10253 sybils sur 43058 éligibles), Arbitrum (~150k sybils, 21.8 % des tokens, 4000+ communautés Louvain), Optimism (17k retirés, 14M OP récupérés). Méthodologie : funding graphs star/chain + Louvain + scoring behavioral. **Directement transposable** à tout futur programme incitatif Polymarket. **Wash trading NFT** : Liu et al. (arXiv:2305.01543), Tošić et al. (arXiv:2312.16603), Wachter et al., SCC + règles wash sale IRS. **Phishing Ethereum** : Chen et al. (ACM TOIT 2020), Trans2vec, TTAGN (WWW 2022), BERT4ETH (WWW 2023), EPAD (2025) — playbook ML+graphe directement réutilisable.

**Questions business Polymarket**. (1) Insider rings : identifier marchés à gap anormal pré-résolution → top-holders du côté gagnant → sous-graphe wallet-wallet (co-trading + funding + transferts) → Leiden → scoring sur récurrence multi-événements. (2) Copy-trading / disciples : lead-lag score $P(\text{B trade } m | A \text{ a tradé } m \text{ dans } [t-\tau,t]) / \text{baseline}$ avec $\tau \in [30s, 10min]$, idéalement via TGN en link-prediction. (3) Déanonymisation proxy↔EOA : triviale via `ProxyCreation`. (4) EOA↔EOA : GNN link-prediction sur graphe hétérogène `(EOA, Proxy, Market, Token, Bridge, CEX)`. (5) Propagation d'info : cascade models (Goldenberg) pour mesurer lift d'activité chez les "contacts" graphiques après un trade insider.

### 5.5 Récapitulatif Axe 5

| Technique | Complexité | Difficulté | PM |
|---|---|---|---|
| **Leiden** | $O(n\log n)$ | 2/5 | **Directe ⭐** |
| Louvain | $O(n\log n)$ | 2/5 | Directe |
| Label Propagation | $O(m)$ | 1/5 | Mineure (instable) |
| Infomap | $O(m\cdot \text{iter})$ | 3/5 | Directe (flux USDC) |
| PageRank / **PPR** | $O(k(V+E))$ | 2/5 | **Directe ⭐** |
| Betweenness | $O(VE)$ | 3/5 | Mineure (sampling) |
| Jaccard / **MinHash-LSH** | $O(Np)$ | 2/5 | **Directe** |
| SimRank | $O(V^2 d)$ | 4/5 | Mineure |
| GCN / GraphSAGE / GAT | $O(LEd)$ | 4/5 | Majeure |
| **TGN / TGAT** | $O(Ed)$ | 5/5 | **Majeure (idéal copy-trading)** |
| node2vec / DeepWalk | $O(rlV+Vdk)$ | 3/5 | Directe |
| **SCC + cycle detection** | $O(V+E)$ | 2/5 | **Directe (wash trading)** |
| DBSCAN/HDBSCAN sur embeddings | $O(N\log N)$ | 2/5 | Directe |

---

## 6. Techniques spécifiques aux prediction markets

### 6.1 Cohérence probabiliste et arbitrage

La structure même des prediction markets impose des inégalités vérifiables. Pour deux marchés liés par inclusion $A_i \subseteq A_j$, on doit avoir $P(A_i) \leq P(A_j)$. Pour deux marchés mutuellement exclusifs, $P(A_i) + P(A_j) \leq 1$. Sur Neg Risk markets, $\sum_i P(\text{YES}_i) = 1$ à la résolution. Un **graphe de contraintes probabilistes** (DAG) permet de formuler un LP minimisant les violations :

$$\min \sum_v \epsilon_v \quad \text{s.c.} \quad p_v - \epsilon_v \leq p_w + \epsilon_w \ \forall (v,w) \in E,\ 0 \leq p_v \pm \epsilon_v \leq 1$$

Toute $\epsilon_v$ persistante au-delà des fees est soit une opportunité d'arbitrage, soit un signal d'asymétrie d'information. **Détection du wallet initiateur** de la divergence = candidat primaire.

L'**étude IMDEA Networks** (Saguillo, Ghafouri, Kiffer, Suarez-Tangil, AFT 2025, arXiv:2508.03474) documente sur 86M bets Polymarket d'avril 2024 à avril 2025 **$39.59M d'arbitrage extractible**, dont **$29M (73 %) via rebalancing Neg Risk** — 29× l'efficacité capitalistique des binaires pour seulement 8.6 % des opportunités. Détecter $S_{ask} = \sum_i \text{ask}(\text{YES}_i) < 1 - 2\text{fee}$ = arb pur. Quand le déséquilibre est durablement sur un $\text{YES}_i$ spécifique, identifier le wallet qui pousse.

Le **cross-platform signal** contre Pinnacle devigué (via Shin 1993 ou power method) est particulièrement robuste : $z(t) = (P_{PM} - P_{\text{Pinn,devig}})/\sigma_{\text{spread}}$ ; si $|z| > 2.5$ persistant ET la résolution confirme le côté Polymarket, les wallets qui ont poussé la divergence sont des candidats smart money. Frictions réelles (KYC Kalshi, on-ramp, geofencing) expliquent que des spreads persistent sans être exploitables.

### 6.2 UMA comme signal rétroactif

L'approche canonique est le **labeling ex-post** : pour chaque `conditionId` résolu, calculer la position nette de chaque wallet sur fenêtre $[T-\Delta, T_{résolution}]$, edge réalisé $(\text{payout}-\text{cost})/\text{cost}$, moyenner, $t$-tester. **Horizons par type** : 7–14j événements news (élection, Fed), 2–24h sport, 60–180j long-run, 1–15min crypto intraday. **Règle anti-leakage absolue** : aucune feature construite post-résolution ne doit entrer dans un modèle pré-résolution — walk-forward CV avec split par `resolution_ts`, purged k-fold avec embargo autour des frontières (López de Prado).

Les **marchés disputés UMA** sont un signal de second ordre. Le cas **Ukraine minerals (mars 2025)** — volume $7M, P passé de 9 % à 100 %, résolution YES malgré absence factuelle de deal, un whale UMA vote 5M tokens via 3 adresses (25 % du vote) en ayant position longue YES — illustre la governance attack. Polymarket a refusé les refunds et UMA a migré vers **MOOV2 via UMIP-189 (août 2025)** whitelistant les proposers. **Signal structurel** : calculer $\text{Jaccard}(\text{voters\_UMA}, \text{traders\_gagnants\_marché\_disputé})$ + clustering via heuristiques Axe 3 = red flag collusion.

**Skill vs info privée vs manipulation** : problème d'identification central. Un wallet avec MeanEdge > 0 significatif peut être (i) skillful (Théo avec sondages privés), (ii) insider, (iii) manipulator (UMA voter influençant sa résolution). Tests discriminants : edge persistant sur marchés aléatoires = skill ; edge concentré niche = insider ; timing <1h avant news publique = insider fort ; activité UMA voting + position PM = manipulation. **Identification légale impossible sans off-chain + KYC**.

### 6.3 News flow et APPM

L'**Abnormal Pre-announcement Price Movement** (Dubow & Monteiro, FSA 2006) formalise ce que les régulateurs UK utilisent pour equity insider detection : $AR_t = p_t - p_{t_{news}-\Delta}$, $CAR[t_{news}-2h, t_{news}-5min]$, test $t = CAR/(\sigma_{AR}\sqrt{N})$. **Directement transposable** Polymarket. Sources de $t_{news}$ : Twitter/X API (comptes officiels, wires), GDELT 2.0 (15-min latency, gratuit), Reuters/Bloomberg si accès, mempool monitoring crypto. NLP direction via FinBERT ou LLM prompt `"Does this news make this market more likely? Return ±1 score."`

Le **cas documenté yellow.com (fév. 2026)** : avant frappes iraniennes, 6 wallets Polymarket neufs (<72h, pas d'historique) achètent YES "Iran strike" à 17 % implied, gagnent ~$1.2M. Signature classique : wallets frais + dépôts USDC juste avant trade + direction correcte sur fenêtre pré-news < 30min. Détection via volume z-score + filtrage wallet age.

### 6.4 Sports betting — transposable

**Levitt (EJ 2004)** confirme que Polymarket en CLOB est plus proche des markets financiers que des sportsbooks — donc détection style Kyle/PIN pertinente plus que Shin. **Schnytzer-Shilony (EJ 1995), Crafts 1985, Asch-Malkiel-Quandt 1982** documentent que sur horse racing l'insider "plonge" en dernière minute — signal classique. **Paul-Weinbach (2011)** montre l'inverse sur NFL : late money = récréatif. **Polymarket hérite donc du régime selon le type de marché** : news-driven (politique, Fed, crypto) = late informé, sentiment-driven (grand public) = late square. **Steaming detection** multi-plateforme : $|\Delta p| > 3\sigma$ + volume spike = signal de pilonnage. **Favorite-longshot bias** à retirer du signal pour ne pas imputer le biais structurel à skill.

### 6.5 Récapitulatif Axe 6

| Technique | Difficulté | FP typique | PM |
|---|---|---|---|
| **Cohérence probabiliste DAG** | 3/5 | Latence, liquidité asymétrique | **Directe** |
| Arbitrage Neg Risk | 2/5 | Non-atomicité | Directe |
| Cross-platform Pinnacle | 4/5 | Frictions KYC | Directe |
| YES + NO parity | 1/5 | Spreads illiquides | Directe |
| Longshot + large bet | 2/5 | Tail chasers | Directe |
| TWAP conviction | 2/5 | MM directionnels | Directe |
| Late money | 3/5 | NFL inverse | Directe |
| Kyle λ pré-news | 4/5 | MMs absorbent flux | Directe |
| **Edge réalisé ex-post** | 2/5 | Skill pur | **Directe ⭐⭐** |
| **APPM event study** | 3/5 | News amont leak | **Directe ⭐** |
| Pre-news volume z-score | 3/5 | News internes précoces | Directe |
| NLP direction news | 4/5 | Ambiguïté | Directe |
| Steaming detection | 3/5 | Réaction saine post-news | Directe |
| Sharp vs square | 3/5 | Variance échantillon | Directe |
| FLB correction | 3/5 | — | Directe |
| **CLV (closing line value)** | 1–3/5 | N'identifie pas insider seul | **Directe ⭐** |
| Pump & dump | 3/5 | Scalping légitime | Directe |
| UMA oracle manipulation | 5/5 | Voters légitimes cohérents | Directe |

---

## 7. Limites et faux positifs

### 7.1 Trois archétypes confondus avec les insiders

**Les market makers professionnels** (bots Wintermute-like, props bot) affichent gros notional cumulé, hit rate > 50 %, entrées bien timées. Distinction : **signature bilatérale** (bid ET ask sur même conditionId sous 60s), net inventory proche de 0 sur horizons roulants 1h/4h, histogramme positions nettes symétrique. Métrique *net-to-gross ratio* = $|\sum \text{signed notional}| / \sum |\text{notional}|$ : MM propre < 0.10, insider directionnel > 0.80.

**Les arbitrageurs** (intra-marché Yes+No, Neg Risk, cross-platform) ont PnL positifs sans info. Signature : ordres quasi-simultanés sur marchés corrélés (delta < 10s), positions hedgées (deltas nets ≈ 0), realized vol PnL très basse. Test : corrélation entrées sur paires marchés redondants ≈ 1.0.

**Les skillful modelers** sont le faux positif **le plus dangereux**. Un trader avec bon modèle électoral (538-like), sondages privés (cas Théo/Fredi9999), ou modèle NBA win-probability a edge réel, mathématiquement indistinguable d'un insider sur features on-chain seules. Le cas Fredi9999 — 11 comptes, ~$85M profit, positions fragmentées en increments de $500 — a été classifié *conviction personnelle + modèle neighbor effect*, pas insider. **Conséquence méthodologique critique : ne jamais produire de label binaire "insider" sur seules métriques on-chain**, seulement des suspicion scores probabilistes dont la calibration est elle-même incertaine.

### 7.2 Biais statistiques à corriger obligatoirement

**Survivorship** : seuls wallets actifs observés ; corriger par cohortes fixées à $t_0$ et tracking forward incluant les zéros. **Selection par threshold** : "≥N trades" biaise vers wallets actifs, corriger par IPW ($\pi(x) = P(\text{inclus}|X=x)$ via logistic, pondérer par $1/\hat\pi$) ou Heckman two-step (inverse Mills ratio en régresseur). **Look-ahead / leakage** : trois formes, par subtilité croissante — grossier (outcome comme label), classique (CLV comme benchmark), subtil (présence même d'une activité = signal de popularité post-hoc). Règle : pour chaque feature $f_k(t)$, vérifier $f_k(t) \in \sigma(I(t))$ où $I(t)$ = info disponible à $t$. Point-in-time snapshots, replay tick-by-tick.

**Multiple testing** est le piège n°1. Sur $M = 10^5$ wallets à $\alpha = 5\%$ : 5000 FP sous $H_0$. À $Z > 3$ : toujours 135 FP. Bonferroni $\alpha/M = 5\times 10^{-7}$ trop conservateur, **BH FDR recommandé**. PSR, DSR (cf. §4.2), **Harvey & Liu 2015 haircut Sharpe** non-linéaire, **White Reality Check** et **Hansen SPA** via bootstrap stationnaire. **Data snooping / p-hacking** : pré-enregistrer protocole, holdout strict ≥30 %. **Regression to mean** : top-décile P1 régresse en P2, rank correlation souvent $\rho < 0.3$, shrinkage bayésien ou James-Stein.

### 7.3 Manipulation, sybils, visibilité limitée

**Sybils** (Fredi9999 = 11 comptes) : heuristiques Axe 3 en combinaison. **Pump & dump** : burst volume + price move >20 % + retracement >80 %. **Wash trading** : cycles `maker↔taker` courts, fills sans spread. **Spoofing** : **point critique** — Polymarket a un order book off-chain, seuls les fills sont on-chain. Les ordres placés/annulés ne sont visibles qu'en live WebSocket API, pas historisés. **Effective spread, order book imbalance, quote-to-trade ratio, cancel rate = non calculables rétroactivement**. Cette limite doit être reportée explicitement dans tout livrable — c'est un écart fondamental avec marchés centralisés traditionnels. **Collusion inter-wallets sans funding partagé** : lead-lag cross-correlation, Granger causality.

### 7.4 Ground truth quasi-impossible

La définition légale d'insider (info matérielle non-publique + effet de marché) est en droit US swap-qualified mais peu testée pour prediction markets. Polymarket officiellement off-limits US depuis settlement CFTC 2022, fraction non-négligeable d'utilisateurs via VPN. Proxy labels tous imparfaits : wallets bannis (peu, opaque), identifiés publiquement (biais médiatique, ironie Fredi9999 blanchi = mauvais label), post-resolution windows (circulaire). **Modèles supervisés inutilisables en pratique faute de labels propres**. Seule voie raisonnable : anomaly detection non-supervisée + **investigation qualitative manuelle** des top-k scores.

### 7.5 Spécifiques Polymarket

**Finalité Polygon** : avant Heimdall v2 (juillet 2025), ~1–2min + checkpoints 30min ; post-Heimdall v2, ~5s avec reorg cap 2 blocs. Attendre finalité "milestone" avant backtest. **USDC.e vs USDC natif vs Polymarket USD** (migration 2025) : pipeline multi-asset normalisé en USD. **Proxy wallets** rendent clustering non-optionnel. **UMA disputes** : exclure/censurer fenêtres instables.

### 7.6 Métriques robustes vs fragiles

| Métrique | Statut |
|---|---|
| Sharpe simple | 🔴 Fragile |
| Hit rate brut | 🔴 Fragile |
| PnL cumulé absolu | 🔴 Fragile |
| PSR | 🟢 Robuste |
| DSR | 🟢 Robuste |
| Brier + bootstrap CI | 🟢 Robuste |
| Edge vs CLV size-contrôlé | 🟢 Robuste |
| Hit rate Bonferroni | 🟡 Acceptable |
| Max drawdown | 🟡 Acceptable |

**Règle** : toujours reporter `(métrique, CI bootstrap 95 %, p-value FDR-corrigée)`. Un Sharpe nu sans IC ni haircut est information vide.

### 7.7 Baseline rigoureuse

$H_0$ : trade aux prix de marché, $E[\text{edge}]=0$, Sharpe $\approx 0$. **Permutation tests** : garder timing, randomiser directions, répéter $B=10000$, p-value empirique. **Synthetic control** : wallet moyen synthétique avec mêmes covariables via propensity matching ou Abadie. **Splits temporels stricts** train/val/test avec purge + embargo.

---

## 8. Stack outils open-source

### 8.1 Ingestion

**web3.py** (Apache 2.0) reste le standard Python avec middleware POA obligatoire pour Polygon. `ethers-py` stagne, éviter. **eth-brownie officiellement non-maintenu** depuis 2024 (README GitHub l'indique explicitement) — utiliser **ApeWorX (ape)** comme successeur spirituel ou Foundry/Hardhat via JSON-RPC pour forking. **py-clob-client** (MIT) est le SDK officiel Polymarket (REST + WebSocket, auth L0/L1/L2), branche v2 en refonte mais v1 reste production. **subgrounds** wrap les subgraphs Goldsky avec retour DataFrame. **multicall.py** indispensable pour batcher `balanceOf` ERC-1155 sur milliers de positions.

Pour les backfills, **cryo (Paradigm, Rust + bindings Python)** est le choix 2026 : extract direct vers Parquet partitionné, filter par event signature, range syntax riche. Exemple :

```bash
cryo logs --rpc $POLYGON_RPC \
  --contract 0x4bFb41d5B3570DefD03C39a9A4D8dE6Bd8B8982e \
  --event-signature "OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)" \
  --blocks 55_000_000:60_000_000 --requests-per-second 50 \
  --output-dir ./data/polymarket/orderfilled
```

**Goldsky** (subgraphs + Mirror streaming vers Postgres/ClickHouse/S3) est en prod chez Polymarket — subgraph public `Polymarket/polymarket-subgraph` déjà maintenu. **The Graph hosted est legacy** à sunsetter. **Subsquid** alternative EU plus rapide sur gros backfills. **ethereum-etl / polygon-etl** éprouvé mais daté. **BigQuery public dataset** `bigquery-public-data.crypto_polygon` avec 1 TB/mo gratuit = raccourci sans indexer. Providers RPC : **Alchemy, QuickNode, Chainstack** (free tier généreux, enhanced APIs). Self-hosted **Erigon / bor** Polygon (archive 3–5 TB NVMe, sync jours/semaines) seulement à gros volume.

### 8.2 Analyse locale

**pandas** limite ~5 GB RAM. **polars** (Rust, lazy, 5–20x plus rapide, streaming Parquet) remplace pandas à scale. **DuckDB** (MIT, embedded OLAP, columnar, lit Parquet/CSV/Arrow/Iceberg/Delta, extensions `httpfs` pour S3) est le killer tool : query direct sur Parquets locaux ou S3. Pattern canonique :

```python
import duckdb
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
df = con.execute("""
  SELECT date_trunc('hour', to_timestamp(block_timestamp)) AS h,
         maker_asset_id, SUM(maker_amount_filled)/1e6 AS usdc_volume, COUNT(*) AS n
  FROM read_parquet('s3://bucket/polymarket/orderfilled_*.parquet')
  WHERE block_number BETWEEN 55000000 AND 60000000
  GROUP BY 1,2
""").pl()
```

**PyArrow** transparent mais indispensable pour streaming. **Dask** moins pertinent face au combo polars + DuckDB.

### 8.3 ML / Stats / Graph

**scikit-learn** (IsolationForest, LOF, DBSCAN, PCA), **HDBSCAN** séparé, **PyOD** unified anomaly library 40+ modèles, **XGBoost/LightGBM/CatBoost**, **statsmodels + arch** pour GARCH/cointégration, **PyMC/NumPyro** (JAX) pour Bayesian, **ruptures** pour change point, **PyTorch** pour DL custom.

Graph : **NetworkX (<1M arêtes)**, **igraph (C, GPL, 10–100M)**, **graph-tool (C++, install pénible)**, **cuGraph (GPU)**, **PyG / DGL** pour GNN, **Neo4j + driver Python + Cypher** (GPL Community vs Enterprise payante), **Kuzu embedded (MIT)** comme "DuckDB du graph" — **choix 2026 optimal** pour analytics locales.

### 8.4 SQL / Warehouses

**DuckDB** comme cœur local. **ClickHouse** columnar OLAP distribué : self-hosted OSS gratuit, Cloud Dev $1–$193/mo, Prod depuis ~$500/mo (prix augmentés janvier 2025 avec egress $115/TiB). **CryptoHouse** public datasets Ethereum/Solana gratuit, suivre Polygon. **Dune Analytics v2** Free (2500 credits) / Plus $399/mo / Premium $999/mo / Enterprise — non-OSS mais indispensable pour démarrer : tables `polymarket_polygon.*` déjà décodées. **MotherDuck** DuckDB cloud hybride. **BigQuery crypto_polygon** 1 TB/mo gratuit. **Snowflake/Databricks overkill** pour équipe crypto <10 personnes.

### 8.5 Orchestration et storage

**Airflow** standard mais lourd. **Dagster** moderne asset-based (recommandé équipe data). **Prefect** léger Python-native. **Temporal** pour workflows ordres durables. **dbt Core** incontournable pour transformations SQL avec tests/docs/lineage. **SQLMesh** alternative dbt récente. **Scripts cron / GitHub Actions** pour MVP ($0 infra).

**Parquet + S3/R2** (Cloudflare R2 à $0.015/GB-mo avec egress gratuit — très pertinent crypto). **Apache Iceberg** (PyIceberg, DuckDB natif), **Delta Lake** pour lakehouse ACID. **SQLite** prototypes uniquement. **HDF5** legacy à éviter.

### 8.6 Stacks par budget

**Solo chercheur (<$100/mo)** : py-clob-client + subgrounds + cryo sur Alchemy free + Parquet local/R2 + DuckDB+polars + Dune Free/BigQuery + sklearn + Kuzu + GitHub Actions. **Équipe small ($500–2000/mo)** : cryo + RPC payant + Goldsky Scale + Dune Plus $399 + ClickHouse Cloud Dev/MotherDuck + dbt + Dagster OSS + PyG si GNN + Kuzu/Neo4j Community. **Fonds quant (>$5k/mo)** : Erigon self-hosted + Goldsky Mirror + ClickHouse cluster + dbt + SQLMesh + Dagster Cloud + PyTorch+PyG sur GPU + Neo4j Enterprise + Temporal pour trading workflows.

### 8.7 Récapitulatif Axe 8 (synthétique)

| Catégorie | Recommandation 2026 |
|---|---|
| Ingestion RPC | cryo + Alchemy/QuickNode |
| Subgraph | Goldsky (subgraph public Polymarket) |
| SDK Polymarket | py-clob-client (v1 prod) |
| Storage | Parquet + Cloudflare R2 |
| Analyse locale | polars + DuckDB |
| SQL managé (démarrage) | Dune Plus $399 |
| DB OLAP (scale) | ClickHouse self-host ou Cloud |
| ML anomaly | PyOD + scikit-learn + XGBoost |
| Graph embedded | Kuzu |
| GNN | PyTorch Geometric + TGN |
| Orchestration | Dagster + dbt |
| Dev framework | ApeWorX (successor Brownie) |

---

## 9. Matrice globale et priorisation suggérée

Le tableau suivant agrège les ~75 techniques des 8 axes en une matrice décisionnelle. Les scores ne sont pas directifs — ils signalent où se trouve le rapport effort/valeur le plus favorable pour un nouveau projet Polymarket.

### 9.1 Tier 1 — à construire en premier (ROI très élevé, effort modéré, robustesse testée)

| Technique | Axe | Difficulté | Données | Ce que ça donne |
|---|---|---|---|---|
| **Mapping proxy↔EOA via ProxyCreation** | 3 | 2/5 | Bas | Ground truth on-chain, table pivot essentielle |
| **PnL canonique en flux nets USDC** | 4 | 3/5 | Moyen | Mesure de base, pré-requis à tout leaderboard |
| **Edge vs market entry + BSS + log score** | 4,6 | 2/5 | Moyen | Alpha pur post-résolution, killer feature binaires |
| **CLV (closing line value)** | 4,6 | 1–3/5 | Faible | Filtre initial rapide, bon pré-trieur |
| **Z-score MAD intra/cross + conviction trades** | 2 | 1–2/5 | Faible | Couche rules-based temps réel |
| **FDR Benjamini-Hochberg sur leaderboards** | 4,7 | 2/5 | Faible | Filtre indispensable contre inflation significativité |
| **CFS — Common Funding Source** | 3 | 2/5 | Bas | Clustering scalable via Dune SQL |
| **Victor deposit-address-reuse** | 3 | 3/5 | Moyen | Heuristique la plus puissante (cas Fredi9999) |
| **Event study CAR + APPM pré-résolution** | 2,6 | 3/5 | Moyen | Détecte info leak, méthodologie régulatrice UK |
| **Isolation Forest + LOF** | 2 | 2/5 | Moyen | Couche anomaly detection non-supervisée |
| **PageRank / Personalized PageRank** | 5 | 2/5 | Moyen | Exploration depuis un seed suspect |
| **Leiden community detection** | 5 | 2/5 | Moyen | Détecte sybil rings, coordination |
| **Arbitrage Neg Risk detection** | 6 | 2/5 | Moyen | $29M documentés (Saguillo 2025) |
| **Cohérence probabiliste DAG inter-marchés** | 6 | 3/5 | Moyen | Signal natif prediction markets |

### 9.2 Tier 2 — à construire ensuite (ROI élevé, effort plus significatif)

| Technique | Axe | Difficulté | Ce que ça apporte en plus |
|---|---|---|---|
| Glosten-Milgrom spread decomposition | 1 | 3/5 | Modèle binaire natif, AS quantifié |
| PSR + DSR + Harvey-Liu haircut | 4,7 | 4–5/5 | Classement wallets corrigé multiple testing |
| Kelly fit sur sizing | 4 | 4/5 | Discrimine skill de luck |
| Wash-trading detection via SCC + maker/taker cycles | 5 | 4/5 | Filtrage avant tout scoring |
| CUSUM / BOCPD / PELT sur prix et volume | 2 | 2–4/5 | Change point detection par marché |
| Supervised learning avec labels post-résolution (XGBoost) | 2 | 3/5 | Meilleure precision si split temporel strict |
| Cross-platform Pinnacle devig + smart money detection | 6 | 4/5 | Signal de divergence informative |
| UMA dispute + voter/trader overlap | 6 | 5/5 | Governance attack detection |
| Event-window σ² (Brown 2012) | 1 | 2/5 | Test d'insider simple et robuste |
| Kyle's λ pré-news | 1,6 | 4/5 | Attribution quantitative du price impact |
| Hasbrouck Information Share Polymarket/Kalshi/Betfair | 1 | 4/5 | Qui price-discovers quoi |
| Hawkes self + cross-excitation | 2 | 4/5 | Coordination inter-wallets quantifiée |
| Bootstrap Ledoit-Wolf CI sur Sharpe | 4 | 3/5 | IC robustes non-normaux |
| Cohort fixing + IPW selection correction | 7 | 3–4/5 | Corrige biais survivorship |

### 9.3 Tier 3 — à considérer seulement avec équipe et budget

| Technique | Axe | Difficulté | Caveats |
|---|---|---|---|
| Temporal GNN (TGN/TGAT) pour copy-trading | 5 | 5/5 | Etat de l'art, coût MLOps élevé |
| Contrastive SSL embeddings wallets | 2 | 5/5 | Design augmentations non trivial |
| White Reality Check / Hansen SPA | 4,7 | 5/5 | Bootstrap sur M stratégies corrélées |
| GraphSense adapter Polygon | 3 | 5/5 | Infra Cassandra+Spark lourde |
| PIN formelle sur contrats Polymarket | 1 | 4/5 | Adaptation majeure, hypothèses cassent |
| VPIN avec BVC logit-adapté | 1 | 3/5 | Fragile par construction (AB 2014) |

### 9.4 Techniques à éviter ou traiter comme gadgets

- **Gas price fingerprinting sur Polymarket** : quasi-inutile à cause du Gas Station Network (tx relayées masquent la fingerprint user).
- **PIN/VPIN appliqués naïvement** : bien plus d'effort de calibration qu'ils ne rendent ; préférer Glosten-Milgrom et event-window σ².
- **Temporal correlation 168 bins seule** : faux positifs massifs (bots 24/7, news-driven concurrence), à n'utiliser qu'en combinaison.
- **NetworkX en production** : inutilisable au-delà de 1M arêtes, basculer Kuzu/igraph.
- **Spoofing detection rétroactif** : impossible, l'order book complet Polymarket n'est pas on-chain. Reporter explicitement.
- **Sharpe nu, hit rate brut, PnL cumulé** sans correction FDR et haircut : information vide.
- **Label binaire "insider"** produit sur seules features on-chain : méthodologiquement indéfendable.

### 9.5 Trois vérités inconfortables à poser ouvertement

Premièrement, **il n'y a pas de ground truth**. Les exemples médiatiques les plus cités (Fredi9999 et consorts) ont été classifiés après enquête comme skillful modelers, pas insiders. Tout modèle supervisé reproduira les biais du labeling. La seule approche défendable est **anomaly detection non-supervisée + investigation manuelle top-k**, avec production de suspicion scores probabilistes et non de labels binaires.

Deuxièmement, **le multiple testing détruit la plupart des claims**. Un univers de $10^5$–$10^6$ wallets et une quinzaine de features produit, sous $H_0$, des dizaines de milliers de "signaux" aléatoires. La littérature Bailey–López de Prado–Harvey–Liu impose des haircuts sévères systématiquement ignorés par les threads X. Toujours reporter PSR/DSR, toujours appliquer BH FDR.

Troisièmement, **Polymarket a des limites structurelles de visibilité** que l'écosystème sous-estime. Order book off-chain → spoofing, order book imbalance, cancel rate invisibles historiquement. Proxy wallets → clustering obligatoire pour toute métrique per-user. Geoblocking US → biais d'échantillon. Migration USDC.e → USDC → PUSD → pipeline multi-asset obligatoire. Finalité Polygon probabiliste → attendre milestone/checkpoint.

### 9.6 Séquence d'implémentation suggérée (sans être directive)

Une équipe qui démarre rationnellement ferait approximativement : (1) stack d'ingestion minimal Dune $399 + py-clob-client + cryo pour backfills → Parquet R2 → DuckDB+polars, (2) table `proxy↔EOA` via ProxyCreation events comme première brique analytique, (3) PnL canonique flux nets USDC + CLV + edge post-résolution + Brier/BSS = couche métriques, (4) FDR Benjamini-Hochberg systématique sur tout leaderboard, (5) z-score MAD + conviction trades + CFS clustering + Isolation Forest en monitoring continu, (6) event study APPM pré-résolution piloté par catalogue de news externes, (7) Leiden + PageRank sur graphe wallet-wallet filtré (MinHash-LSH pour similarity), (8) enfin supervised GBM sur labels post-résolution et TGN/contrastive SSL si ressources MLOps dédiées. À chaque étape, investigation manuelle top-50 avant diffusion publique de quelque scoring que ce soit.

## Conclusion

La détection de trading informé et le clustering de wallets sur Polymarket ne sont pas des problèmes techniquement insolubles, mais ils sont **épistémiquement fragiles** dans leur formulation naïve. Les données on-chain sont riches, les outils OSS (DuckDB, polars, cryo, Kuzu, PyG, scikit-learn) permettent de construire rapidement des pipelines sérieux, la littérature existe (Victor 2020, Bailey-López de Prado, Saguillo et al. 2025) et fournit des primitives réutilisables. Mais la combinaison *absence de ground truth + multiple testing massif + limites structurelles de visibilité* impose une discipline méthodologique que la plupart des analyses publiques ignorent. Le livrable rigoureux n'est pas une liste de "X insiders identifiés" ; c'est un système de suspicion scores probabilistes avec CI bootstrap, correction FDR, cohortes fixées pour contrer survivorship, investigation qualitative manuelle des top-k, et documentation explicite des limites. Les techniques du Tier 1 suffisent à produire un système qui bat 95 % des analyses disponibles aujourd'hui — le Tier 2 et 3 ajoutent de la precision et de la nuance, pas de la crédibilité fondamentale. La barrière n'est pas la sophistication des algorithmes ; elle est dans la rigueur statistique et la maintenance des labels de services (CEX, bridges, MEV, MMs) qui évitent les faux positifs. C'est là le vrai moat que Chainalysis, Arkham et Nansen ont construit, et que toute équipe sérieuse sur Polymarket devra reconstruire pour sa propre surface.