from pathlib import Path

from polybot.config import Settings

R2_DEFAULTS = {
    "R2_ACCESS_KEY_ID": "test-key",
    "R2_SECRET_ACCESS_KEY": "test-secret",
    "R2_ENDPOINT": "https://abc123.r2.cloudflarestorage.com/polybot-snapshots",
}


def test_settings_defaults():
    """Settings should work with minimal env vars (all have defaults or are optional)."""
    settings = Settings(**R2_DEFAULTS)
    assert Path("data/pm.duckdb") == settings.DUCKDB_PATH
    assert settings.R2_BUCKET == "polybot-snapshots"
    assert settings.GAMMA_API_URL == "https://gamma-api.polymarket.com"
    assert settings.CLOB_API_URL == "https://clob.polymarket.com"
    assert settings.LOG_LEVEL == "INFO"


def test_settings_r2_endpoint_url():
    settings = Settings(**R2_DEFAULTS)
    assert settings.r2_endpoint_url == "https://abc123.r2.cloudflarestorage.com"


def test_settings_r2_endpoint_url_no_bucket_suffix():
    """Endpoint without bucket suffix should be returned as-is."""
    settings = Settings(
        R2_ACCESS_KEY_ID="key",
        R2_SECRET_ACCESS_KEY="secret",
        R2_ENDPOINT="https://abc123.r2.cloudflarestorage.com",
    )
    assert settings.r2_endpoint_url == "https://abc123.r2.cloudflarestorage.com"


def test_settings_migrations_dir():
    settings = Settings(**R2_DEFAULTS)
    assert Path("migrations") == settings.MIGRATIONS_DIR
