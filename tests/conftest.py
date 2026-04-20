import pytest

from polybot.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Settings with test defaults. Override R2 creds via env or parametrize."""
    return Settings(
        R2_ACCOUNT_ID="test",
        R2_ACCESS_KEY_ID="test-key",
        R2_SECRET_ACCESS_KEY="test-secret",
        DUCKDB_PATH="data/test.duckdb",
    )
