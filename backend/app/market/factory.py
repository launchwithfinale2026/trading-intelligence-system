from functools import lru_cache

from app.core.config import get_settings
from app.market.provider import MarketDataProvider
from app.market.yfinance_provider import YFinanceProvider

_PROVIDERS: dict[str, type[MarketDataProvider]] = {
    "yfinance": YFinanceProvider,
}


@lru_cache
def get_market_data_provider() -> MarketDataProvider:
    provider_name = get_settings().market_data_provider
    try:
        provider_cls = _PROVIDERS[provider_name]
    except KeyError:
        raise ValueError(
            f"unknown market_data_provider {provider_name!r}; available: {sorted(_PROVIDERS)}"
        ) from None
    return provider_cls()
