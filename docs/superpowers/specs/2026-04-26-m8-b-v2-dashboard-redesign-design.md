# M8-B v2 Design — Dashboard Web Refonte Complète

## Overview

Refonte complète du frontend du dashboard Polybot, avec un design "trading terminal" haut de gamme inspiré de deux références Dribbble (palette sombre, accents orange + violet, glass effect subtil, typographie Inter). Le backend FastAPI existant est conservé ; on ajoute 3 nouveaux endpoints (wallet detail, wallet trades, clusters) et on modifie `/api/markets/hot` pour ranker par score C2 plutôt que par volume.

Cette refonte succède au M8-B v1 (`docs/superpowers/specs/2026-04-26-m8b-dashboard-design.md`) qui a livré un MVP fonctionnel mais visuellement basique.

## Architecture

```
Browser (VPN US) → Caddy (:3000, basicauth)
  ├── /api/* → reverse_proxy → uvicorn embarqué dans polybot-bot.service (:8000, 127.0.0.1)
  └── /*     → static files (dashboard/dist/)
```

L'API dashboard est embarquée dans le process `polybot-bot.service` (commit `bcf5987` — résolution conflit lock DuckDB). Pas de service systemd dédié pour la dashboard API. Frontend = static files servis par Caddy après `npm run build` local + rsync.

### Ce qui est conservé

- `src/polybot/dashboard/api.py` (8 endpoints existants)
- `dashboard/package.json`, `dashboard/vite.config.js`, `dashboard/index.html` (avec ajout `<link>` Inter)
- Caddy config + systemd service (inchangé)
- Tests backend `tests/unit/test_dashboard_api.py` (étendus)

### Ce qui est ajouté

**Backend** : 3 nouveaux endpoints + modification de `/api/markets/hot`.

**Frontend** : tout `dashboard/src/` est wipé et reconstruit autour de SWR + Tailwind v4 (`@theme` directive) + lucide-react + Inter.

### Ce qui est supprimé

- Tout `dashboard/src/` actuel (App.jsx, main.jsx, main.css, components/, pages/, hooks/) — wipe complet, on repart de zéro.

### Workflow d'exécution

- Worktree git isolé : `worktrees/m8-b-v2-dashboard`, branche `m8-b-v2-dashboard`
- Commits per-brique selon le plan d'implémentation
- Vérif locale `npm run dev` au fil des sections visibles
- Deploy VPS en fin de chantier (rsync `dist/`)

## Module — Backend (FastAPI)

Fichier : `src/polybot/dashboard/api.py`

### Endpoint 1 — `GET /api/wallets/{address}`

Détail complet d'un wallet : info de base, métriques agrégées, série P&L cumulé, infos CEX et cluster.

**SQL** (5 blocs distincts dans la même fonction) :

```sql
-- Bloc 1 : info wallet + métriques trades
SELECT w.address, w.notes AS name, w.tier, w.active, w.tier_a_confidence,
       w.honeypot_flag, w.added_at, w.source,
       COUNT(t.transaction_hash) AS trades_total,
       MAX(t.timestamp_ts) AS last_trade,
       AVG(t.size_usd) AS avg_trade_size,
       COALESCE(SUM(t.size_usd), 0) AS total_volume
FROM tracked_wallets w
LEFT JOIN trades t ON w.address = t.proxy_wallet
WHERE w.address = ?
GROUP BY w.address, w.notes, w.tier, w.active, w.tier_a_confidence,
         w.honeypot_flag, w.added_at, w.source

-- Bloc 2 : alertes résolues + win rate + Shadow P&L
SELECT
  COUNT(*) FILTER (WHERE ao.resolution_outcome NOT IN ('PENDING')) AS resolved,
  COUNT(*) FILTER (WHERE ao.was_direction_correct = TRUE) AS correct,
  SUM(ao.shadow_pnl_simulated) FILTER (WHERE ao.resolution_outcome NOT IN ('PENDING')) AS pnl
FROM alerts a
LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
WHERE a.wallet_address = ?

-- Bloc 3 : pnl_series (Shadow P&L cumulé par jour, 90j)
-- CTE pour agréger par jour avant cumul (évite les doublons si plusieurs alertes/jour)
WITH daily AS (
  SELECT DATE_TRUNC('day', a.emitted_at)::DATE AS day,
         SUM(ao.shadow_pnl_simulated) AS daily_pnl
  FROM alerts a
  JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
  WHERE a.wallet_address = ?
    AND ao.resolution_outcome NOT IN ('PENDING')
    AND a.emitted_at >= CURRENT_DATE - INTERVAL '90 DAY'
  GROUP BY day
)
SELECT day, SUM(daily_pnl) OVER (ORDER BY day) AS cum_pnl
FROM daily
ORDER BY day

-- Bloc 4 : cex_funding (LEFT JOIN — null si pas tracé)
SELECT cex_source, deposit_address, confidence, method
FROM cex_funding_map
WHERE wallet_address = ?

-- Bloc 5 : cluster info (LEFT JOIN — null si pas dans cluster)
SELECT m.cluster_id, c.size, c.funded_by, c.cex_source
FROM wallet_cluster_members m
JOIN wallet_clusters c ON m.cluster_id = c.cluster_id
WHERE m.wallet_address = ?
```

**Réponse** :

```json
{
  "address": "0xd1acd3925d895de9aec98ff95f3a30c5279d08d5",
  "name": "Kickstand7",
  "tier": "A", "active": true, "tier_a_confidence": 0.9,
  "honeypot_flag": false, "added_at": "2026-04-15T...", "source": "sharps_positive.csv",
  "trades_total": 125, "last_trade": "2026-04-26T...", "avg_trade_size": 86.4,
  "total_volume": 10800.0,
  "resolved": 34, "correct": 21, "win_rate": 0.617, "pnl": 1247.32,
  "pnl_series": [{"day": "2026-04-01", "cum_pnl": 12.5}, ...],
  "cex_funding": {"cex_source": "Binance", "deposit_address": "0x...", "confidence": 0.95, "method": "deposit_address_match"},
  "cluster": {"cluster_id": "abc-uuid", "size": 12, "funded_by": "0x...", "cex_source": "Binance"}
}
```

`cex_funding` et `cluster` valent `null` si non applicables.

**Erreurs** : 404 si wallet inexistant dans `tracked_wallets`.

### Endpoint 2 — `GET /api/wallets/{address}/trades?limit=100`

Derniers trades du wallet, joints aux alertes pour décorer avec resolution.

```sql
SELECT t.transaction_hash, t.timestamp_ts, t.condition_id,
       t.market_title, t.market_slug, t.side, t.outcome,
       t.size_usd, t.price,
       m.resolved, m.active,
       ao.resolution_outcome, ao.was_direction_correct
FROM trades t
LEFT JOIN markets m ON t.condition_id = m.condition_id
LEFT JOIN alerts a ON a.wallet_address = t.proxy_wallet
                  AND a.condition_id = t.condition_id
LEFT JOIN alert_outcomes ao ON a.alert_id = ao.alert_id
WHERE t.proxy_wallet = ?
ORDER BY t.timestamp_ts DESC
LIMIT ?
```

**Dédup** : le `LEFT JOIN alerts` peut produire des doublons si plusieurs alertes existent pour le même `(wallet, market)`. À traiter côté Python : `dict[transaction_hash → row]` en gardant la première rencontrée (la plus récente puisque ORDER BY est appliqué).

**Paramètres** : `limit` (default 100, max 500).

**Réponse** : array de `{transaction_hash, timestamp_ts, condition_id, market_title, market_slug, side, outcome, size_usd, price, resolved, active, resolution_outcome, was_direction_correct}`.

### Endpoint 3 — `GET /api/clusters`

Liste des clusters de wallets co-fundés par même CEX deposit (issu de M10-2).

```sql
SELECT c.cluster_id, c.funded_by, c.cex_source, c.size, c.created_at,
       COUNT(m.wallet_address) AS member_count,
       COUNT(*) FILTER (WHERE w.tier = 'A') AS tier_a_count
FROM wallet_clusters c
LEFT JOIN wallet_cluster_members m ON c.cluster_id = m.cluster_id
LEFT JOIN tracked_wallets w ON m.wallet_address = w.address
GROUP BY c.cluster_id, c.funded_by, c.cex_source, c.size, c.created_at
ORDER BY tier_a_count DESC, c.size DESC
LIMIT 100
```

**Réponse** : array de `{cluster_id, funded_by, cex_source, size, created_at, member_count, tier_a_count}`.

### Modification — `GET /api/markets/hot`

**Breaking change** : on bascule du ranking par `volume_24h` vers ranking par `MAX(score) C2` sur les alertes des 7 derniers jours. Comme on wipe le frontend existant, l'impact est nul. À mentionner dans le commit message.

```sql
SELECT m.condition_id, m.title, m.slug,
       MAX(a.score) AS c2_score_max,
       MAX(a.features_passed) AS features_last,
       COUNT(a.alert_id) AS c2_alerts_7d,
       MAX(a.emitted_at) AS last_alert_at,
       m.volume_24h, m.end_date
FROM markets m
JOIN alerts a ON m.condition_id = a.condition_id
WHERE a.component = 'C2'
  AND a.emitted_at >= CURRENT_DATE - INTERVAL '7 DAY'
GROUP BY m.condition_id, m.title, m.slug, m.volume_24h, m.end_date
ORDER BY c2_score_max DESC, c2_alerts_7d DESC
LIMIT 10
```

**Note** : `features_last` est un JSON stocké tel quel dans `alerts.features_passed` ; le frontend parse pour afficher les features actives en tags colorés. À sécuriser avec un parse safe (try/except → null).

`MAX(features_passed)` n'est pas sémantiquement le features de l'alerte la plus récente — c'est le max lexicographique du JSON string. Si on veut vraiment le features de l'alerte la plus récente, il faut un sous-select :

```sql
(SELECT a2.features_passed FROM alerts a2
 WHERE a2.condition_id = m.condition_id AND a2.component = 'C2'
 ORDER BY a2.emitted_at DESC LIMIT 1) AS features_last
```

À utiliser. Le `MAX()` est gardé seulement pour `score` (où la sémantique "score max sur 7j" est correcte).

## Module — Frontend (React + SWR)

Directory : `dashboard/`

### Stack

- React 19 (existant) + Vite 6 (existant)
- React Router 7 (existant)
- **Tailwind CSS v4** avec `@theme` directive (pas de `tailwind.config.js`)
- **SWR** (nouveau) — fetcher + caching + auto-refresh
- **Recharts** 2.15 (existant) — graphes
- **Lucide React** (nouveau) — icônes
- **Inter** font via Google Fonts (`<link>` dans `index.html`)

### Tokens design (Tailwind v4 `@theme`)

Dans `dashboard/src/index.css` :

```css
@import "tailwindcss";

@theme {
  --color-bg-primary: #0a0a0f;
  --color-bg-card: #12121a;
  --color-bg-card-hover: #16161f;
  --color-bg-sidebar: #0e0e14;
  --color-accent-orange: #f97316;
  --color-accent-violet: #a855f7;
  --color-pnl-positive: #22c55e;
  --color-pnl-negative: #ef4444;
  --color-text-primary: #f1f1f4;
  --color-text-secondary: #6b7280;
  --color-text-tertiary: #4b5563;
  --font-sans: "Inter", system-ui, sans-serif;
  --radius-card: 16px;
}

@layer base {
  body { background: var(--color-bg-primary); color: var(--color-text-primary); }
}

@layer utilities {
  .glass-card {
    background: linear-gradient(135deg, #12121a 0%, #0e0e18 100%);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: var(--radius-card);
  }
  .glass-hero {
    backdrop-filter: blur(20px);
    background: rgba(18, 18, 26, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: var(--radius-card);
  }
}
```

Usage : `className="bg-bg-card text-text-primary rounded-card border border-white/[0.06]"` ou `className="glass-card"`.

### Typographie

- **Hero** (P&L) : `text-4xl font-bold tracking-tight` (~2.5rem, 700)
- **Titres sections** : `text-xl font-semibold` (~1.25rem, 600)
- **Body / tables** : `text-sm` (~0.875rem, 400)
- **Labels / captions** : `text-xs font-medium uppercase tracking-wider text-text-secondary` (~0.75rem)
- Adresses wallet : font monospace (`font-mono` Tailwind, qui est typiquement JetBrains Mono ou similaire ; fallback à `monospace`).

### Arborescence

```
dashboard/
├── index.html              ← + <link rel="preconnect" + Inter>
├── package.json            ← + lucide-react, swr
├── vite.config.js          ← inchangé
└── src/
    ├── main.jsx            ← StrictMode + SWRConfig + RouterProvider
    ├── App.jsx             ← shell layout (Sidebar + TopBar + <Outlet/>)
    ├── index.css           ← @import tailwindcss + @theme + utilities
    ├── api.js              ← fetcher + helpers d'URL
    ├── lib/
    │   ├── format.js       ← formatUSD, formatPct, formatRelative, truncateAddr, copyToClipboard
    │   └── colors.js       ← helpers couleur (P&L, status, side YES/NO)
    ├── components/
    │   ├── layout/
    │   │   ├── Sidebar.jsx
    │   │   └── TopBar.jsx
    │   ├── primitives/
    │   │   ├── GlassCard.jsx
    │   │   ├── KpiCard.jsx
    │   │   ├── StatusBadge.jsx
    │   │   ├── FilterPills.jsx
    │   │   ├── AddressDisplay.jsx
    │   │   ├── EmptyState.jsx
    │   │   ├── ErrorState.jsx
    │   │   └── SkeletonList.jsx
    │   ├── charts/
    │   │   ├── ChartArea.jsx
    │   │   ├── ChartLine.jsx
    │   │   ├── ChartDonut.jsx
    │   │   ├── ChartBar.jsx
    │   │   └── Sparkline.jsx
    │   └── domain/
    │       ├── AlertCard.jsx
    │       ├── WalletCard.jsx
    │       ├── IndexerRow.jsx
    │       └── HotMarketRow.jsx
    └── pages/
        ├── Overview.jsx
        ├── Alerts.jsx
        ├── Wallets.jsx
        ├── WalletDetail.jsx
        ├── Performance.jsx
        └── System.jsx
```

### Découpage de composants

- **`primitives/`** : atomes réutilisables, sans connaissance domaine, sans fetch.
- **`domain/`** : composants métier, prennent une `prop` typée (alert, wallet, indexer), pas de fetch. Pas de logique réseau.
- **`charts/`** : wrappers Recharts pré-stylés (couleurs accent, gradients, axis labels gris).
- **`pages/`** : composent primitives + domain + charts. Font les `useSWR`. Aucune logique visuelle bas niveau.
- **`App.jsx`** : shell uniquement (Sidebar + TopBar + `<Outlet/>`).

### Sidebar

- Largeur : 240px (desktop), 64px (tablet, icônes only), hidden sur mobile (overlay via hamburger).
- Logo "POLYBOT" en haut : `font-extrabold text-2xl tracking-widest`.
- Items : icône Lucide + label. Active = `border-l-3 border-accent-orange text-accent-orange`. Hover = `bg-white/5`.
- Items : Overview (`Activity`), Alerts (`Zap`), Wallets (`Users`), Performance (`TrendingUp`), System (`Settings`).

### TopBar

- Barre horizontale en haut du content.
- Pills live (chacune `bg-white/5 rounded-full px-3 py-1 text-xs`) :
  - Shadow P&L cumulé (couleur P&L positif/négatif)
  - Alertes 24h (compte)
  - Win Rate (%)
  - Indexers status (`6/6 ✓` vert si tous OK, `5/6 ⚠` orange si 1 failed, `X/6 ✗` rouge si plusieurs)
- Bouton refresh global à droite (icône `RefreshCw`, animé pendant fetch).
- Source data : `/api/status` + `/api/performance` (refresh 30s).

### Routing

```jsx
const router = createBrowserRouter([{
  path: "/", element: <App/>,
  children: [
    { index: true,                element: <Overview/> },
    { path: "alerts",             element: <Alerts/> },
    { path: "wallets",            element: <Wallets/> },
    { path: "wallets/:address",   element: <WalletDetail/> },
    { path: "performance",        element: <Performance/> },
    { path: "system",             element: <System/> },
  ]
}]);
```

## Pages — détail

### Overview (`/`)

- **Hero card glass** (full width) : Shadow P&L cumulé en gros chiffre + variation semaine + ChartArea 30j intégré + badge "Shadow Mode ON" avec dot animé.
- **Row 4 KPI cards** : Alertes 24h (+ sparkline 7j), Win Rate (+ donut mini), Wallets actifs (X/15 + mini bar), Coûts mois (LLM + VPS).
- **Section "Dernières alertes"** (60% gauche) : 5 dernières AlertCard compactes + bouton "Voir tout →".
- **Section "Indexers"** (40% droite) : 6 IndexerRow.
- **Section "Hot Markets"** (full width, en bas) : Top 5 HotMarketRow par score C2.

### Alerts (`/alerts`)

- **Filtres pills** en haut, état dans URL params (`?component=C2&days=7&status=pending`) :
  - Composant : `All` | `C1` | `C2`
  - Période : `24h` | `7d` | `30d` | `All`
  - Status : `All` | `Pending` | `Correct` | `Incorrect` (filtré côté client)
- **Liste AlertCard** verticale (pas une table). Click → expand inline avec features C2, alignment, momentum, risk reasons, alert ID, lien Polymarket externe.
- AlertCard : pastille C1 (orange) / C2 (violet) + titre marché complet (pas tronqué) + side BUY YES (vert) / BUY NO (rouge) + prix + size wallet + size suggérée + score C3 + status pending/correct/incorrect.
- Wallet cliquable → `/wallets/:address`.

### Wallets (`/wallets`)

- Liste WalletCard horizontales. Chaque card : dot activité + nom (depuis `notes`) + adresse complète copyable + tier + confidence + KPIs (trades, résolus, win, P&L) + last trade relatif + flèche vers détail.
- Wallet `active=false` : opacity-50 + label "DEMOTED" rouge.
- Click → `/wallets/:address`.

### WalletDetail (`/wallets/:address`)

- **Header** : nom + adresse complète copyable + tier + confidence + lien externe `https://polymarket.com/profile/{address}`.
- **KPIs** : trades total, résolus, win rate, P&L cumulé, avg trade size.
- **ChartArea** : Shadow P&L cumulé 90j.
- **Section CEX funding** (si présente) : source, deposit address, confidence, method.
- **Section Cluster** (si membre) : cluster_id (lien vers `/clusters/:id` éventuel futur), size, funded_by.
- **Table trades** : derniers 100. Colonnes : date, marché (titre complet), side, outcome, size, prix, status (pending/correct/incorrect).
- **Lien interne** : "Voir les alertes de ce wallet" → `/alerts?wallet=0x...` (filtre côté client si pas de param backend).

### Performance (`/performance`)

- **ChartLine** : Shadow P&L cumulé 30j, 2 lignes (C1 orange, C2 violet) sur même axe.
- **Stats cards** : total alertes, résolues, pending, direction correcte % (donut), avg P&L par alerte, meilleur trade, pire trade.
- **ChartBar** horizontal : alignment distribution (+1 / 0 / -1).
- **Warning banner** stylisé orange si `resolved < 30` : "Échantillon insuffisant (X/30 minimum). Résultats indicatifs."

### System (`/system`)

- **Audit log** : cards scrollables (pas table brute). Icône Lucide par event_type, couleur par action, timestamp relatif.
- **Kill switches** : toggle switches visuels readonly (modifications via Telegram `/toggle` uniquement).
- **Rate limits** : barres de progression (current/max) par composant.
- **Disk/RAM** : barres de progression couleur vert/jaune/rouge selon utilisation. (Note : nécessite source data — à voir si endpoint existant. Si non disponible, masquer cette section ou afficher "—".)
- **Indexers expanded** : chaque indexer en card avec dot timeline des 5 derniers runs. (Note : nécessite historique runs — pas dispo dans `/api/status` actuel qui ne donne que `last_run_status`. Si non disponible, afficher juste le dernier état.)

## Data flow

### Fetcher SWR — `src/api.js`

```javascript
const API_BASE = "/api";

export async function fetcher(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    err.info = await res.text().catch(() => null);
    throw err;
  }
  return res.json();
}

export const urls = {
  status: () => "/status",
  alerts: ({ days = 7, component } = {}) =>
    `/alerts?days=${days}${component ? `&component=${component}` : ""}`,
  wallets: () => "/wallets",
  walletDetail: (addr) => `/wallets/${addr}`,
  walletTrades: (addr, limit = 100) => `/wallets/${addr}/trades?limit=${limit}`,
  performance: (days = 30) => `/performance?days=${days}`,
  hotMarkets: () => "/markets/hot",
  audit: (limit = 50) => `/audit?limit=${limit}`,
  costs: () => "/costs",
  clusters: () => "/clusters",
};
```

### SWR config global — `main.jsx`

```jsx
<SWRConfig value={{
  fetcher,
  revalidateOnFocus: true,
  dedupingInterval: 5000,
  errorRetryCount: 2,
  errorRetryInterval: 5000,
}}>
  <RouterProvider router={router}/>
</SWRConfig>
```

### Polling par endpoint

| Endpoint | refreshInterval | Rationale |
|---|---|---|
| `/status` | 30s | Indexers en cours, kill switches, signaux temps quasi réel |
| `/alerts` | 60s | Nouvelles alertes apparaissent |
| `/performance` | 60s | Bouge avec résolutions |
| `/wallets`, `/wallets/{addr}`, `/clusters` | off | Stables, focus revalidate suffit |
| `/markets/hot` | 120s | Hot markets ne changent pas vite |
| `/audit`, `/costs` | off | Focus revalidate suffit |

### Filtres URL params (Alerts)

```jsx
const [params, setParams] = useSearchParams();
const component = params.get("component");        // "C1" | "C2" | null
const days = parseInt(params.get("days") ?? "7"); // 1 | 7 | 30 | 365
const status = params.get("status");              // "pending" | "correct" | "incorrect" | null

const { data, error, isLoading } = useSWR(
  urls.alerts({ days, component }),
  { refreshInterval: 60_000 }
);

// Status filtré côté client (l'API n'a pas ce param)
const filtered = status ? data?.filter(a => matchesStatus(a, status)) : data;
```

### Refresh manuel

Bouton refresh global dans TopBar : appelle `mutate(key)` SWR sur tous les keys actifs de la page. Utiliser `useSWRConfig().cache` pour itérer ou maintenir une liste explicite par page.

### Auth

Caddy basicauth gère tout. Aucune logique React. Si l'user annule le prompt navigateur, browser affiche erreur HTTP standard.

## Error handling & edge cases

### Pattern standard par page

```jsx
const { data, error, isLoading } = useSWR(urls.alerts(), { refreshInterval: 60_000 });

if (isLoading) return <SkeletonList count={5}/>;
if (error)     return <ErrorState error={error} onRetry={() => mutate(urls.alerts())}/>;
if (!data?.length) return <EmptyState icon={Inbox} message="Aucune alerte sur cette période"/>;

return data.map(a => <AlertCard key={a.alert_id} alert={a}/>);
```

### Composants standards

- **`<SkeletonList count={N}/>`** : N cards `bg-bg-cardHover animate-pulse`, hauteur ≈ card finale (évite layout shift).
- **`<EmptyState icon message subtitle?/>`** : icône Lucide grise + message centré.
- **`<ErrorState error onRetry/>`** : icône `AlertTriangle` rouge + message + `<details>` collapsible (debug) + bouton "Réessayer".

### Edge cases

- **Overview** : `pnl_series` vide ou < 7j → "Données insuffisantes" sans graphe. Tous indexers `running` → "En attente du premier run".
- **Alerts** : `market_title=null` → "Marché inconnu" + condition_id tronqué. `features_passed` JSON parse fail → catch, "Features indisponibles".
- **Wallets** : `notes` null → adresse seule. `active=false` → opacity-50 + "DEMOTED" rouge. Aucun trade → "Aucun trade", win rate "—".
- **WalletDetail** : 404 → page d'erreur + lien retour. `pnl_series` vide → graphe remplacé par EmptyState. Pas de cex / cluster → sections masquées (pas d'EmptyState dédié).
- **Performance** : `resolved < 30` → bandeau warning orange. Aucune résolue → EmptyState global, masquer graphes.
- **System** : audit vide → "Aucun événement". Indexers vides → "Aucun indexer enregistré".

### Defensive coding

- `?.` sur tous les nested props.
- Helpers `formatUSD(null) → "—"`, `formatPct(null) → "—"`, etc.
- `parseFeaturesSafe(json)` utility try/catch.
- Pas d'ErrorBoundary racine en v1 (overkill).

### Responsive

- Desktop (≥1024px) : sidebar 240px + content.
- Tablet (768-1023px) : sidebar 64px (icônes only).
- Mobile (<768px) : sidebar hidden, hamburger → overlay full-height. TopBar pills scrollables (`overflow-x-auto`). Cards stack vertical. Tables `overflow-x-auto`.

## Tests

### Backend — `tests/unit/test_dashboard_api.py` (extension)

**+8 tests nouveaux** :

```python
class TestWalletDetailEndpoint:
    def test_returns_full_wallet_with_metrics(client, db_path):
        # seed 1 wallet + 5 trades + 3 alerts (2 correct, 1 incorrect)
        # GET /api/wallets/0xABC
        # assert name, trades_total, resolved, win_rate, pnl, pnl_series

    def test_returns_404_when_wallet_not_found(client):
        # GET /api/wallets/0xDEADBEEF → 404

    def test_includes_cex_funding_when_present(client, db_path):
        # seed wallet + cex_funding_map → assert cex_funding object

    def test_includes_cluster_when_member(client, db_path):
        # seed wallet + cluster_members + clusters → assert cluster object

class TestWalletTradesEndpoint:
    def test_returns_recent_trades_for_wallet(client, db_path):
        # seed 150 trades → GET ?limit=100 → assert len=100, trié desc

    def test_dedupes_trades_when_multiple_alerts_per_market(client, db_path):
        # seed 1 trade + 2 alerts même condition_id → assert 1 row

class TestClustersEndpoint:
    def test_returns_clusters_with_member_count(client, db_path):
        # seed 2 clusters (3 et 5 membres dont 2 Tier A) → ordering tier_a desc

class TestHotMarketsRanking:
    def test_orders_by_c2_score_max(client, db_path):
        # seed 3 markets, alertes C2 scores variés → assert ordre score desc
        # assert features_passed inclus dans la réponse
```

### Frontend — vérification manuelle (pas de Vitest en v1)

Checklist :

- [ ] `npm install` puis `npm run build` : compile sans warning bloquant
- [ ] `npm run dev` : toutes les pages loadent
- [ ] Overview : hero P&L, 4 KPIs, 5 dernières alertes cliquables, indexers, hot markets
- [ ] Alerts : filtres URL (`?component=C2&days=7&status=pending`), reload conserve filtres
- [ ] Alerts : click card → expand inline avec features C2/risk/P&L
- [ ] Wallets : noms (Domer, Aenews2, Kickstand7) affichés, démotés grisés
- [ ] WalletDetail : header + KPIs + ChartArea + table trades + sections CEX/cluster
- [ ] Performance : ChartLine C1 vs C2, donut direction %, bar alignment, warning si <30
- [ ] System : audit scrollable, kill switches readonly, rate limits avec barres, indexers
- [ ] Mobile (<768px) : hamburger, overlay sidebar, cards stack, tables scroll horizontal
- [ ] Tablet (768-1023px) : sidebar 64px, pages lisibles
- [ ] Polling : laisser Overview ouvert 2 min → données se rafraîchissent
- [ ] Auth Caddy : `curl http://62.146.230.73:3000/api/status` sans auth → 401, avec auth → 200

### Critères "done"

- ✅ 8 tests backend nouveaux verts + tests existants verts
- ✅ Build frontend zéro erreur, zéro warning bloquant, taille `dist/` raisonnable (<500kb gzippé idéalement)
- ✅ 6 pages naviguables localement avec data réelle (DB locale)
- ✅ Mobile + tablet OK (DevTools resize check)
- ✅ Deploy VPS OK avec screenshots prouvant chaque page

## Deploy

1. Build frontend local : `cd dashboard && npm run build`
2. Push branch + merge `main`
3. SSH polybot : `git pull` + `uv sync`
4. Restart `polybot-bot` (qui sert l'API embarqué) : `systemctl restart polybot-bot`
5. Rsync `dist/` : `rsync -avz dashboard/dist/ polybot:/root/polybot/dashboard/dist/`
6. Caddy reload : `systemctl reload caddy`
7. Smoke test : ouvrir `http://62.146.230.73:3000` (avec VPN US) → navigation 6 pages avec data réelle, screenshots stockés en preuve

## Dependencies

### Backend (pas de nouvelle dep Python)

Tout est déjà en place (FastAPI, uvicorn, duckdb, pydantic).

### Frontend (`dashboard/package.json` — additions)

```json
{
  "dependencies": {
    "lucide-react": "^0.460.0",
    "swr": "^2.2.5"
  }
}
```

(versions indicatives, à confirmer au moment du `npm install`)

## What NOT to do

- ❌ Garder le code frontend existant (wipe `dashboard/src/` complet)
- ❌ Utiliser MUI / Ant Design / shadcn / autre UI framework
- ❌ Modifier le backend FastAPI au-delà des 3 nouveaux endpoints + modif `markets/hot`
- ❌ Créer une migration DB (on lit ce qui existe, `notes` contient déjà les noms)
- ❌ Utiliser `#000000` comme background (palette définie : `#0a0a0f`)
- ❌ Tronquer les titres de marchés dans les alertes (titre complet)
- ❌ Ajouter Vitest / tests frontend en v1 (manuel suffit)
- ❌ Installer Node.js sur le VPS (build local + rsync)
- ❌ Exposer l'API sur 0.0.0.0 (127.0.0.1 only, Caddy reverse proxy)
- ❌ Créer un service systemd dédié dashboard (l'API est embarquée dans `polybot-bot.service` — voir commit `bcf5987`)
