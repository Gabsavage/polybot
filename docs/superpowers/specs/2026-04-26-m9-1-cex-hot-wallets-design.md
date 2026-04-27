# M9-1 — CEX Hot Wallets + Migration 008

## Objective

Set up the foundations for CEX funding detection: a curated list of CEX hot wallet addresses on Polygon and the database tables to store funding relationships. This is the data layer for M9's `shared_cex_deposit_ratio` feature.

## Deliverables

### 1. `config/cex_hot_wallets.yaml`

Curated list of ~30-50 hot wallet addresses for 10 exchanges on Polygon:
Binance, Coinbase, OKX, Kraken, Bybit, Kucoin, Gate.io, Crypto.com, Gemini, MEXC.

**Format:**
```yaml
exchanges:
  binance:
    name: "Binance"
    hot_wallets:
      - address: "0x..."
        label: "Binance Hot Wallet 1"
        verified: true
        source: "polygonscan"
```

**Sourcing strategy:** Web search for publicly documented addresses (Polygonscan labels, Arkham, GitHub repos, blockchain analytics articles). Priority on Binance and Coinbase (highest coverage of insider cases: Iran cluster, Maduro).

**What counts as a hot wallet:** Large wallets with millions of outgoing transactions (withdrawal wallets), NOT per-user deposit addresses.

### 2. `migrations/008_m9_cex_funding.sql`

Two tables:

**`cex_hot_wallets`** — Reference table for known CEX addresses.
- `address VARCHAR PRIMARY KEY`
- `exchange_name VARCHAR NOT NULL`
- `label VARCHAR`
- `verified BOOLEAN DEFAULT TRUE`
- `source VARCHAR`
- `added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

**`cex_funding_map`** — Maps trader wallets to their CEX funding source.
- `wallet_address VARCHAR PRIMARY KEY`
- `funded_by VARCHAR`
- `funded_by_hop2 VARCHAR`
- `cex_source VARCHAR`
- `deposit_address VARCHAR`
- `confidence DECIMAL(3,2)`
- `method VARCHAR CHECK (method IN ('direct_hot_wallet', 'hop2_hot_wallet', 'deposit_address_match'))`
- `traced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

Indexes on `deposit_address` (for shared_cex_deposit_ratio lookups) and `cex_source`.

### 3. `scripts/seed_cex_hot_wallets.py`

Loader script following `seed_tier_a.py` pattern:
- Reads `config/cex_hot_wallets.yaml`
- Upserts into `cex_hot_wallets` table
- Normalizes addresses to lowercase
- Idempotent (INSERT...ON CONFLICT DO UPDATE)

### 4. Tests

| Test | What it verifies |
|------|-----------------|
| Load YAML | Mock YAML with 3 exchanges, 5 wallets → 5 rows |
| Idempotent | Load twice → still 5 rows |
| Lowercase normalization | Mixed-case address → stored lowercase |
| Migration schema | DESCRIBE both tables → correct columns |
| YAML structure | Real YAML file parses correctly |

Test fixture: `db_path` with `tmp_path` + `apply_migrations`, matching existing project pattern.

## Explicitly out of scope

- Indexer `cex_funding` (M9 prompt 2)
- C2 modifications (M9 prompt 2)
- Deposit addresses (discovered via tracing, not hardcoded)
- VPS deployment
