from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Exported so callers (main.py's production startup guard) can compare
# against it without duplicating the literal and risking drift.
INSECURE_DEFAULT_SECRET_KEY = "dev-only-insecure-secret-change-me"

# Resolved to an absolute path (backend/app/core/config.py -> repo root)
# rather than the CWD-relative ".env" pydantic-settings defaults to.
# Real env vars (Docker, hosting platforms) always take precedence over
# this file regardless, so this only affects local dev — and it makes
# ".env" loading work the same way whether a command is run from the repo
# root or from backend/ (the documented convention, matching
# alembic.ini/Dockerfile), instead of silently loading nothing when run
# from backend/ because ".env" resolved relative to the wrong directory.
_REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Trading Intelligence System"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./trading.db"

    @field_validator("database_url")
    @classmethod
    def _normalize_postgres_scheme(cls, value: str) -> str:
        """Several managed Postgres providers (Heroku-style, some Render/
        Railway configurations) hand out connection strings starting with
        `postgres://` — a scheme SQLAlchemy 1.4+ no longer recognizes
        (`NoSuchModuleError`, raised at create_engine time, i.e. app
        startup). Normalize it to the psycopg2 dialect URL so pasting a
        provider's connection string straight into DATABASE_URL just works.
        """
        if value.startswith("postgres://"):
            return "postgresql+psycopg2://" + value[len("postgres://") :]
        return value

    # Auth. secret_key has a dev-only default so local setup works out of the
    # box; production deployments MUST override it via SECRET_KEY in .env.
    secret_key: str = INSECURE_DEFAULT_SECRET_KEY
    access_token_expire_minutes: int = 60 * 24

    # Dashboard. Comma-separated list of origins allowed to call this API
    # from a browser (CORS). The Next.js dev server's default is included
    # so `npm run dev` works out of the box against a local backend.
    cors_allowed_origins: str = "http://localhost:3000"

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
    position_monitor_interval_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()


def assert_production_secret_key_is_set(settings: Settings) -> None:
    """Refuses to let the app start in production with the hardcoded
    dev-only SECRET_KEY — every JWT issued would be forgeable by anyone who
    reads the source. Called from main.py at import time (fail fast, before
    the process ever binds a port), not folded into Settings validation
    itself so tests can construct a Settings instance with any secret_key
    for other purposes without tripping this check.
    """
    if settings.environment == "production" and settings.secret_key == INSECURE_DEFAULT_SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY is still the insecure development default while ENVIRONMENT=production. "
            "Every JWT this process issues would be forgeable by anyone who reads the source. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\" "
            "and set it via your deployment's environment variables before starting the app."
        )
