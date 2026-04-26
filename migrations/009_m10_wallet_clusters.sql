-- M10: Wallet clustering tables

CREATE TABLE IF NOT EXISTS wallet_clusters (
    cluster_id VARCHAR PRIMARY KEY,
    funded_by VARCHAR NOT NULL,
    cex_source VARCHAR,
    size INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wallet_cluster_members (
    wallet_address VARCHAR PRIMARY KEY,
    cluster_id VARCHAR NOT NULL,
    funded_by VARCHAR NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cluster_members_cluster ON wallet_cluster_members (cluster_id);
