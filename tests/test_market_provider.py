from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.core.exceptions import MarketDataError
from app.market.yfinance_provider import YFinanceProvider


def _fake_history_frame() -> pd.DataFrame:
    index = pd.to_datetime(["2026-07-20", "2026-07-21"]).tz_localize("America/New_York")
    return pd.DataFrame(
        {
            "Open": [100.0, 101.5],
            "High": [102.0, 103.0],
            "Low": [99.5, 100.5],
            "Close": [101.0, 102.5],
            "Volume": [1_000_000, 1_200_000],
        },
        index=index,
    )


@patch("app.market.yfinance_provider.yf.Ticker")
def test_get_price_returns_decimal(mock_ticker_cls: MagicMock) -> None:
    mock_ticker_cls.return_value.fast_info = {"lastPrice": 187.23}

    price = YFinanceProvider().get_price("AAPL")

    assert price == Decimal("187.23")
    mock_ticker_cls.assert_called_once_with("AAPL")


@patch("app.market.yfinance_provider.yf.Ticker")
def test_get_volume_returns_int(mock_ticker_cls: MagicMock) -> None:
    mock_ticker_cls.return_value.fast_info = {"lastVolume": 42_000_000}

    volume = YFinanceProvider().get_volume("AAPL")

    assert volume == 42_000_000
    assert isinstance(volume, int)


@patch("app.market.yfinance_provider.yf.Ticker")
def test_missing_price_raises_market_data_error(mock_ticker_cls: MagicMock) -> None:
    mock_ticker_cls.return_value.fast_info = {}

    with pytest.raises(MarketDataError):
        YFinanceProvider().get_price("AAPL")


@patch("app.market.yfinance_provider.yf.Ticker")
def test_fast_info_exception_raises_market_data_error(mock_ticker_cls: MagicMock) -> None:
    instance = MagicMock()
    type(instance).fast_info = PropertyMock(side_effect=KeyError("exchangeTimezoneName"))
    mock_ticker_cls.return_value = instance

    with pytest.raises(MarketDataError):
        YFinanceProvider().get_price("NOTREAL")


@patch("app.market.yfinance_provider.yf.Ticker")
def test_get_history_parses_ohlcv_into_price_points(mock_ticker_cls: MagicMock) -> None:
    mock_ticker_cls.return_value.history.return_value = _fake_history_frame()

    history = YFinanceProvider().get_history("AAPL", period="5d", interval="1d")

    assert len(history) == 2
    first = history[0]
    assert first.open == Decimal("100.0")
    assert first.high == Decimal("102.0")
    assert first.low == Decimal("99.5")
    assert first.close == Decimal("101.0")
    assert first.volume == 1_000_000


@patch("app.market.yfinance_provider.yf.Ticker")
def test_get_market_cap_returns_decimal(mock_ticker_cls: MagicMock) -> None:
    mock_ticker_cls.return_value.fast_info = {"marketCap": 3_500_000_000_000.5}

    market_cap = YFinanceProvider().get_market_cap("AAPL")

    assert market_cap == Decimal("3500000000000.50")


@patch("app.market.yfinance_provider.yf.Ticker")
def test_get_market_cap_raises_when_missing(mock_ticker_cls: MagicMock) -> None:
    mock_ticker_cls.return_value.fast_info = {}

    with pytest.raises(MarketDataError):
        YFinanceProvider().get_market_cap("AAPL")


@patch("app.market.yfinance_provider.yf.Ticker")
def test_get_history_raises_on_empty_result(mock_ticker_cls: MagicMock) -> None:
    mock_ticker_cls.return_value.history.return_value = pd.DataFrame()

    with pytest.raises(MarketDataError):
        YFinanceProvider().get_history("NOTREAL")


def test_market_status_reports_open_during_regular_hours() -> None:
    provider = YFinanceProvider()
    tuesday_at_noon = datetime(2026, 7, 21, 12, 0, tzinfo=ZoneInfo("America/New_York"))

    with patch("app.market.yfinance_provider.datetime") as mock_datetime:
        mock_datetime.now.return_value = tuesday_at_noon
        status = provider.get_market_status()

    assert status.is_open is True
    assert status.session == "regular"


def test_market_status_reports_closed_on_weekend() -> None:
    provider = YFinanceProvider()
    saturday_at_noon = datetime(2026, 7, 25, 12, 0, tzinfo=ZoneInfo("America/New_York"))

    with patch("app.market.yfinance_provider.datetime") as mock_datetime:
        mock_datetime.now.return_value = saturday_at_noon
        status = provider.get_market_status()

    assert status.is_open is False
    assert status.session == "closed"


def test_market_status_reports_closed_before_open() -> None:
    provider = YFinanceProvider()
    early_morning = datetime(2026, 7, 21, 6, 0, tzinfo=ZoneInfo("America/New_York"))

    with patch("app.market.yfinance_provider.datetime") as mock_datetime:
        mock_datetime.now.return_value = early_morning
        status = provider.get_market_status()

    assert status.is_open is False
