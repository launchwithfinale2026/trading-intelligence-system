import pytest

from app.market.factory import get_market_data_provider
from app.market.yfinance_provider import YFinanceProvider


def test_default_provider_is_yfinance() -> None:
    get_market_data_provider.cache_clear()

    provider = get_market_data_provider()

    assert isinstance(provider, YFinanceProvider)


def test_unknown_provider_name_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    get_market_data_provider.cache_clear()
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "not-a-real-provider")

    with pytest.raises(ValueError):
        get_market_data_provider()

    monkeypatch.delenv("MARKET_DATA_PROVIDER", raising=False)
    get_settings.cache_clear()
    get_market_data_provider.cache_clear()
