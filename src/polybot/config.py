"""Configuration via pydantic-settings — loads from .env file."""

from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DuckDB
    DUCKDB_PATH: Path = Path("data/pm.duckdb")
    MIGRATIONS_DIR: Path = Path("migrations")

    # Cloudflare R2
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str = "polybot-snapshots"

    # Polymarket APIs
    GAMMA_API_URL: str = "https://gamma-api.polymarket.com"
    CLOB_API_URL: str = "https://clob.polymarket.com"

    # Snapshot config
    SNAPSHOT_TOP_N: int = 150
    SNAPSHOT_MIN_VOLUME_24H: float = 50_000.0
    SNAPSHOT_UNIVERSE_REFRESH_HOURS: int = 6

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = Path("logs")

    @computed_field
    @property
    def r2_endpoint_url(self) -> str:
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
