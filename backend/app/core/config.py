from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Trading Intelligence System"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./trading.db"

    # Auth. secret_key has a dev-only default so local setup works out of the
    # box; production deployments MUST override it via SECRET_KEY in .env.
    secret_key: str = "dev-only-insecure-secret-change-me"
    access_token_expire_minutes: int = 60 * 24

    # Market data. "yfinance" is the only implementation today; the value
    # exists so a future provider is a config change, not a code change.
    market_data_provider: str = "yfinance"

    # Telegram. None until a real bot is created via BotFather (a human,
    # credentialed step — see docs/ROADMAP.md) and set in .env.
    telegram_bot_token: str | None = None

    # Off by default: automatically scanning and messaging real users is a
    # deliberate product decision a human should switch on, not something
    # that starts happening the moment this code is deployed.
    enable_scheduled_scanning: bool = False
    scan_interval_seconds: int = 900


@lru_cache
def get_settings() -> Settings:
    return Settings()
