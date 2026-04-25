"""Configuration via pydantic-settings — loads from .env file."""

from pathlib import Path

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

    # Cloudflare R2 — reads R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_ENDPOINT: str  # full URL e.g. https://<account_id>.r2.cloudflarestorage.com/...
    R2_BUCKET: str = "polybot-snapshots"

    # Alchemy RPC (Polygon)
    ALCHEMY_POLYGON_URL: str = ""

    # Polymarket APIs
    GAMMA_API_URL: str = "https://gamma-api.polymarket.com"
    CLOB_API_URL: str = "https://clob.polymarket.com"

    # Snapshot config
    SNAPSHOT_TOP_N: int = 150
    SNAPSHOT_MIN_VOLUME_24H: float = 50_000.0
    SNAPSHOT_UNIVERSE_REFRESH_HOURS: int = 6

    # Anthropic (Claude Haiku for C3 resolution risk)
    ANTHROPIC_API_KEY: str = ""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: int = 0
    TELEGRAM_TOPIC_ALERTS: int = 0
    TELEGRAM_TOPIC_OPS: int = 0
    TELEGRAM_TOPIC_ERRORS: int = 0
    TELEGRAM_TOPIC_RISK: int = 0

    # C1 Sharp Money
    C1_SIZE_MIN_USD: float = 1000.0
    C1_RATE_LIMIT_HOURS: int = 3
    C1_DEDUP_BUCKET_SECONDS: int = 300
    C1_LIQUIDITY_MIN_DEPTH: float = 500.0
    C1_KELLY_FRACTION: float = 0.25
    C1_EDGE_DEFAULT_A1: float = 0.04
    C1_EDGE_DEFAULT_A2: float = 0.02
    C1_CONFIDENCE_MULTIPLIER_A1: float = 1.0
    C1_CONFIDENCE_MULTIPLIER_A2: float = 0.6
    C1_SIZE_MAX_PCT_BANKROLL: float = 0.05
    C1_SIZE_MIN_ALERT: float = 10.0
    C1_POLL_INTERVAL: int = 60

    # C2 Informed Trading
    C2_SCAN_INTERVAL: int = 300  # 5 minutes

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = Path("logs")

    @property
    def r2_endpoint_url(self) -> str:
        """Extract base endpoint (without bucket path) from R2_ENDPOINT."""
        # R2_ENDPOINT may be https://<id>.r2.cloudflarestorage.com/bucket-name
        # We need just https://<id>.r2.cloudflarestorage.com
        url = self.R2_ENDPOINT.rstrip("/")
        # Remove bucket name suffix if present
        if url.endswith(f"/{self.R2_BUCKET}"):
            url = url[: -len(f"/{self.R2_BUCKET}")]
        return url
