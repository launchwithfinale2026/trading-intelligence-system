import pytest

from app.core.config import Settings, assert_production_secret_key_is_set


def test_bare_postgres_scheme_is_normalized_to_psycopg2_dialect() -> None:
    settings = Settings(database_url="postgres://user:pass@host:5432/db")

    assert settings.database_url == "postgresql+psycopg2://user:pass@host:5432/db"


def test_already_correct_postgres_url_is_left_unchanged() -> None:
    settings = Settings(database_url="postgresql+psycopg2://user:pass@host:5432/db")

    assert settings.database_url == "postgresql+psycopg2://user:pass@host:5432/db"


def test_sqlite_url_is_left_unchanged() -> None:
    settings = Settings(database_url="sqlite:///./trading.db")

    assert settings.database_url == "sqlite:///./trading.db"


def test_production_with_default_secret_key_is_rejected() -> None:
    settings = Settings(environment="production", secret_key="dev-only-insecure-secret-change-me")

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        assert_production_secret_key_is_set(settings)


def test_production_with_a_real_secret_key_is_accepted() -> None:
    settings = Settings(environment="production", secret_key="a-real-generated-secret")

    assert_production_secret_key_is_set(settings)  # does not raise


def test_development_with_default_secret_key_is_accepted() -> None:
    settings = Settings(environment="development", secret_key="dev-only-insecure-secret-change-me")

    assert_production_secret_key_is_set(settings)  # does not raise
