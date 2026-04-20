from pathlib import Path

from polybot.config import Settings


def test_settings_defaults():
    """Settings should work with minimal env vars (all have defaults or are optional)."""
    settings = Settings(
        R2_ACCOUNT_ID="test-account",
        R2_ACCESS_KEY_ID="test-key",
        R2_SECRET_ACCESS_KEY="test-secret",
    )
    assert settings.DUCKDB_PATH == Path("data/pm.duckdb")
    assert settings.R2_BUCKET_NAME == "polybot-snapshots"
    assert settings.GAMMA_API_URL == "https://gamma-api.polymarket.com"
    assert settings.CLOB_API_URL == "https://clob.polymarket.com"
    assert settings.LOG_LEVEL == "INFO"


def test_settings_r2_endpoint_url():
    settings = Settings(
        R2_ACCOUNT_ID="abc123",
        R2_ACCESS_KEY_ID="key",
        R2_SECRET_ACCESS_KEY="secret",
    )
    assert settings.r2_endpoint_url == "https://abc123.r2.cloudflarestorage.com"


def test_settings_migrations_dir():
    settings = Settings(
        R2_ACCOUNT_ID="test",
        R2_ACCESS_KEY_ID="key",
        R2_SECRET_ACCESS_KEY="secret",
    )
    assert settings.MIGRATIONS_DIR == Path("migrations")
