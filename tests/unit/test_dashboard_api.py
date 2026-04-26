"""Tests for the dashboard API endpoints."""

import duckdb
import pytest
from fastapi.testclient import TestClient


def _seed_alerts(db_path: str) -> None:
    """Insert test data for alerts, wallets, trades, markets, outcomes, and cache."""
    con = duckdb.connect(db_path)

    # Markets
    con.execute(
        "INSERT INTO markets (condition_id, title, slug, volume_24h, liquidity_usd, active) "
        "VALUES ('cond_1', 'Market One', 'market-one', 50000, 20000, TRUE), "
        "       ('cond_2', 'Market Two', 'market-two', 5000, 1000, TRUE)"
    )

    # Alerts: 2 C1 on cond_1, 1 C2 on cond_2
    con.execute(
        "INSERT INTO alerts "
        "(alert_id, component, emitted_at, wallet_address, condition_id, "
        " side, size_usd, price, score, alignment_score, shadow_mode, features_passed) "
        "VALUES "
        "('a1', 'C1', CURRENT_TIMESTAMP, '0xwallet_0', 'cond_1', "
        " 'YES', 100.00, 0.65, 8, 3, TRUE, 'volume,edge'), "
        "('a2', 'C1', CURRENT_TIMESTAMP, '0xwallet_1', 'cond_1', "
        " 'NO', 200.00, 0.35, 7, 2, TRUE, 'volume'), "
        "('a3', 'C2', CURRENT_TIMESTAMP, '0xwallet_2', 'cond_2', "
        " 'YES', 150.00, 0.80, 9, 4, FALSE, 'edge,momentum')"
    )

    # Outcomes: a1 correct +25, a2 incorrect -15
    con.execute(
        "INSERT INTO alert_outcomes "
        "(alert_id, condition_id, resolution_outcome, was_direction_correct, "
        " shadow_pnl_simulated, price_at_alert, price_at_resolution) "
        "VALUES "
        "('a1', 'cond_1', 'YES', TRUE, 25.00, 0.65, 0.90), "
        "('a2', 'cond_1', 'YES', FALSE, -15.00, 0.35, 0.20)"
    )

    # Tracked wallets: 5 tier A (4 active, 1 inactive)
    for i in range(5):
        active = i < 4
        con.execute(
            "INSERT INTO tracked_wallets (address, tier, active, source, added_at) "
            "VALUES (?, 'A', ?, 'scanner', CURRENT_TIMESTAMP)",
            [f"0xwallet_{i}", active],
        )

    # Trades for wallets 0-2 (4 each)
    for i in range(3):
        for j in range(4):
            con.execute(
                "INSERT INTO trades "
                "(transaction_hash, proxy_wallet, condition_id, asset_id, "
                " side, size_usd, price, timestamp_unix, timestamp_ts) "
                "VALUES (?, ?, 'cond_1', 'asset_1', 'YES', 50.00, 0.60, "
                "        1700000000, CURRENT_TIMESTAMP)",
                [f"tx_{i}_{j}", f"0xwallet_{i}"],
            )

    # 50 resolution_risk_cache entries
    for i in range(50):
        con.execute(
            "INSERT INTO resolution_risk_cache "
            "(condition_id, llm_score, computed_at) "
            "VALUES (?, 0.50, CURRENT_TIMESTAMP)",
            [f"cache_cond_{i}"],
        )

    con.close()


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(path)
    con.execute("CREATE SEQUENCE audit_log_seq START 1")
    con.execute("""
        CREATE TABLE kill_switches (
            target VARCHAR PRIMARY KEY,
            enabled BOOLEAN DEFAULT FALSE,
            reason VARCHAR,
            toggled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            toggled_by VARCHAR DEFAULT 'manual'
        )
    """)
    con.execute("""
        CREATE TABLE rate_limit_counters (
            component VARCHAR,
            "window" VARCHAR,
            count INTEGER DEFAULT 0,
            window_start TIMESTAMP,
            PRIMARY KEY (component, "window")
        )
    """)
    con.execute("""
        CREATE TABLE indexer_state (
            indexer_name VARCHAR PRIMARY KEY,
            last_synced_at TIMESTAMP,
            last_block_number BIGINT,
            last_cursor VARCHAR,
            last_run_status VARCHAR,
            last_run_duration_ms INTEGER,
            last_error VARCHAR,
            ingested_count BIGINT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE audit_log (
            id BIGINT DEFAULT nextval('audit_log_seq') PRIMARY KEY,
            event_type VARCHAR, target VARCHAR, action VARCHAR,
            reason VARCHAR, actor VARCHAR DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE alerts (
            alert_id VARCHAR PRIMARY KEY,
            component VARCHAR,
            emitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            trade_hash VARCHAR, wallet_address VARCHAR,
            condition_id VARCHAR, side VARCHAR,
            size_usd DECIMAL(18,2), price DECIMAL(6,4),
            size_suggested_usd DECIMAL(18,2),
            resolution_risk_score DECIMAL(3,2),
            telegram_message_id BIGINT,
            alignment_score INTEGER, score INTEGER,
            features_passed VARCHAR, momentum_4h DECIMAL(6,4),
            shadow_mode BOOLEAN DEFAULT TRUE,
            dedup_hash VARCHAR, tags VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE alert_outcomes (
            alert_id VARCHAR PRIMARY KEY,
            condition_id VARCHAR NOT NULL,
            resolved_at TIMESTAMP,
            resolution_outcome VARCHAR,
            direction_traded VARCHAR,
            was_direction_correct BOOLEAN,
            price_at_alert DECIMAL(6,4),
            price_at_resolution DECIMAL(6,4),
            shadow_pnl_simulated DECIMAL(18,2),
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE markets (
            condition_id VARCHAR PRIMARY KEY,
            title VARCHAR, slug VARCHAR, event_slug VARCHAR,
            volume_24h DECIMAL(18,2), liquidity_usd DECIMAL(18,2),
            end_date TIMESTAMP, active BOOLEAN DEFAULT TRUE,
            volume_cumulative_usd DECIMAL(18,2),
            category VARCHAR, status VARCHAR,
            last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE tracked_wallets (
            address VARCHAR PRIMARY KEY,
            tier VARCHAR, active BOOLEAN, source VARCHAR,
            added_at TIMESTAMP, last_reviewed_at TIMESTAMP,
            honeypot_flag BOOLEAN, honeypot_score DECIMAL(3,2),
            tier_a_confidence DECIMAL(3,2),
            notes TEXT, last_seen_timestamp BIGINT DEFAULT 0
        )
    """)
    con.execute("""
        CREATE TABLE trades (
            transaction_hash VARCHAR PRIMARY KEY,
            proxy_wallet VARCHAR NOT NULL,
            condition_id VARCHAR NOT NULL,
            asset_id VARCHAR NOT NULL,
            side VARCHAR, size_usd DECIMAL(18,2) NOT NULL,
            price DECIMAL(6,4) NOT NULL,
            outcome VARCHAR, outcome_index INTEGER,
            timestamp_unix BIGINT NOT NULL,
            timestamp_ts TIMESTAMP NOT NULL,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE resolution_risk_cache (
            condition_id VARCHAR PRIMARY KEY,
            llm_score DECIMAL(3,2),
            llm_reasons TEXT[], llm_red_flags TEXT[],
            llm_model_version VARCHAR,
            computed_at TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE cex_hot_wallets (
            address VARCHAR PRIMARY KEY,
            exchange_name VARCHAR NOT NULL,
            label VARCHAR,
            verified BOOLEAN DEFAULT TRUE,
            source VARCHAR,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE cex_funding_map (
            wallet_address VARCHAR PRIMARY KEY,
            funded_by VARCHAR,
            funded_by_hop2 VARCHAR,
            cex_source VARCHAR,
            deposit_address VARCHAR,
            confidence DECIMAL(3,2),
            method VARCHAR,
            traced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE wallet_clusters (
            cluster_id VARCHAR PRIMARY KEY,
            funded_by VARCHAR NOT NULL,
            cex_source VARCHAR,
            size INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE wallet_cluster_members (
            wallet_address VARCHAR PRIMARY KEY,
            cluster_id VARCHAR NOT NULL,
            funded_by VARCHAR NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.close()
    return path


@pytest.fixture
def client(db_path):
    from polybot.dashboard.api import app, get_db

    def override_db():
        con = duckdb.connect(db_path)
        try:
            yield con
        finally:
            con.close()

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestStatusEndpoint:
    def test_status_returns_all_sections(self, client, db_path):
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO kill_switches (target, enabled, reason) VALUES ('c1', TRUE, 'test')"
        )
        con.execute(
            'INSERT INTO rate_limit_counters (component, "window", count, window_start) '
            "VALUES ('c1', 'hourly', 5, CURRENT_TIMESTAMP)"
        )
        con.execute(
            "INSERT INTO indexer_state (indexer_name, last_synced_at, last_run_status, "
            "last_run_duration_ms, ingested_count) "
            "VALUES ('markets_gamma', CURRENT_TIMESTAMP, 'success', 1500, 46000)"
        )
        con.close()

        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["kill_switches"]) == 1
        assert data["kill_switches"][0]["target"] == "c1"
        assert len(data["rate_limits"]) == 1
        assert data["rate_limits"][0]["component"] == "c1"
        assert len(data["indexers"]) == 1
        assert data["indexers"][0]["name"] == "markets_gamma"
        assert data["indexers"][0]["ingested_count"] == 46000


class TestAlertsEndpoint:
    def test_alerts_returns_all(self, client, db_path):
        _seed_alerts(db_path)
        resp = client.get("/api/alerts?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_alerts_filter_c1(self, client, db_path):
        _seed_alerts(db_path)
        resp = client.get("/api/alerts?days=7&component=C1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(a["component"] == "C1" for a in data)


class TestWalletsEndpoint:
    def test_wallets_returns_metrics(self, client, db_path):
        _seed_alerts(db_path)
        resp = client.get("/api/wallets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        w0 = next(w for w in data if w["address"] == "0xwallet_0")
        assert w0["trades_total"] == 4
        assert w0["active"] is True


class TestPerformanceEndpoint:
    def test_performance_returns_series(self, client, db_path):
        _seed_alerts(db_path)
        resp = client.get("/api/performance?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert "daily" in data
        assert "cumulative" in data
        assert "alignment" in data
        total_pnl = sum(
            c["pnl"] for c in data["cumulative"] if c["pnl"] is not None
        )
        assert total_pnl == pytest.approx(10.0, abs=0.01)


class TestCostsEndpoint:
    def test_costs_estimate(self, client, db_path):
        _seed_alerts(db_path)
        resp = client.get("/api/costs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["llm_calls_month"] == 50
        assert data["llm_cost_estimate"] == pytest.approx(0.05)
        assert data["vps_monthly"] == 4.0


class TestAuditEndpoint:
    def test_audit_returns_entries(self, client, db_path):
        con = duckdb.connect(db_path)
        con.execute(
            "INSERT INTO audit_log (event_type, target, action, reason) "
            "VALUES ('kill_switch', 'c1', 'enable', 'testing')"
        )
        con.close()
        resp = client.get("/api/audit?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["event_type"] == "kill_switch"


class TestClustersEndpoint:
    def test_clusters_ordered_by_tier_a_count_desc(self, client, db_path):
        con = duckdb.connect(db_path)
        # cluster_b: 5 members (1 Tier A) ; cluster_a: 3 members (2 Tier A)
        con.execute(
            "INSERT INTO wallet_clusters (cluster_id, funded_by, cex_source, size) "
            "VALUES ('cluster_a', '0xfundA', 'Binance', 3), "
            "       ('cluster_b', '0xfundB', 'Coinbase', 5)"
        )
        # 2 Tier A wallets in cluster_a, 1 in cluster_b
        for i in range(3):
            tier = "A" if i < 2 else "B"
            con.execute(
                "INSERT INTO tracked_wallets (address, tier, active) VALUES (?, ?, TRUE)",
                [f"0xa_member_{i}", tier],
            )
            con.execute(
                "INSERT INTO wallet_cluster_members (wallet_address, cluster_id, funded_by) "
                "VALUES (?, 'cluster_a', '0xfundA')",
                [f"0xa_member_{i}"],
            )
        for i in range(5):
            tier = "A" if i < 1 else "B"
            con.execute(
                "INSERT INTO tracked_wallets (address, tier, active) VALUES (?, ?, TRUE)",
                [f"0xb_member_{i}", tier],
            )
            con.execute(
                "INSERT INTO wallet_cluster_members (wallet_address, cluster_id, funded_by) "
                "VALUES (?, 'cluster_b', '0xfundB')",
                [f"0xb_member_{i}"],
            )
        con.close()

        resp = client.get("/api/clusters")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # cluster_a first (2 Tier A) before cluster_b (1 Tier A)
        assert data[0]["cluster_id"] == "cluster_a"
        assert data[0]["tier_a_count"] == 2
        assert data[0]["member_count"] == 3
        assert data[0]["cex_source"] == "Binance"
        assert data[1]["cluster_id"] == "cluster_b"
        assert data[1]["tier_a_count"] == 1
        assert data[1]["member_count"] == 5


class TestWalletDetailEndpoint:
    def test_returns_404_when_wallet_not_found(self, client):
        resp = client.get("/api/wallets/0xDEADBEEF")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Wallet not found"
