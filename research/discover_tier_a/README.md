# Tier A Wallet Candidate Discovery

Identifies top Polymarket traders for the Tier A seed list (M2).

## Method

1. **Wallet discovery** — fetch top 20 holders for each of the top 150 active markets (Data API `/holders`), collect unique wallets
2. **Trade pull** — for each wallet seen in >= 3 markets, fetch full trade history (Data API `/trades`)
3. **Metrics** — aggregate per wallet: trades, markets, categories, HHI, PnL, temporal consistency
4. **Filters** (rapport 4 §4.3):
   - N_trades >= 100
   - K_markets >= 20
   - L_categories >= 3
   - HHI < 0.5
   - PnL >= $50K (approximate, based on trade prices)
   - Last trade < 30 days ago
   - Anti-market-maker: exclude wallets with ~50/50 buy/sell ratio per token
5. **Scoring** — composite z-score: PnL 50%, trades 25%, diversification 25%
6. **Dedup** — exclude known sharps (sharps_positive.csv) and insiders (wallets.csv)

## Running

```bash
# Requires US VPN active
PYTHONPATH=src uv run python research/discover_tier_a/discover_candidates.py
```

## Output

`data/research_outputs/tier_a_candidates_YYYYMMDD.csv` with top 30 candidates.

## Limitations

- PnL is approximate (uses trade price * size, not actual resolution outcomes)
- Category classification is keyword-based, not exhaustive
- Data API `/holders` returns top 20 per token — misses large traders on long-tail markets
- Rate limited to ~1 req/s on Data API
