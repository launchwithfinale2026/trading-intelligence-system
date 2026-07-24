"""yfinance-backed implementation of MarketDataProvider.

yfinance requires no API key, which makes it the fastest path to a working
system, but it's a scraper against Yahoo Finance with no reliability
guarantee — see Decision 8 in docs/DECISIONS.md for why it's wrapped behind
an interface rather than called directly elsewhere in the codebase.
"""

import logging
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

import yfinance as yf

from app.core.exceptions import MarketDataError
from app.market.provider import MarketDataProvider, MarketStatus, PricePoint

logger = logging.getLogger(__name__)

_EASTERN = ZoneInfo("America/New_York")
_MARKET_OPEN = (9, 30)
_MARKET_CLOSE = (16, 0)
_CENT = Decimal("0.01")


def _to_price(value: float) -> Decimal:
    """Quantizes a raw float quote to the nearest cent.

    yfinance returns prices as floats, which carry binary-float noise
    (e.g. 321.6600036621094 for what is really $321.66) — equities trade in
    cents, so rounding to 2 decimal places removes that noise rather than
    hiding real precision.
    """
    return Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP)


class YFinanceProvider(MarketDataProvider):
    def get_price(self, symbol: str) -> Decimal:
        fast_info = self._fast_info(symbol)
        price = fast_info.get("lastPrice")
        if price is None:
            raise MarketDataError(f"no price available for {symbol!r}")
        return _to_price(price)

    def get_volume(self, symbol: str) -> int:
        fast_info = self._fast_info(symbol)
        volume = fast_info.get("lastVolume")
        if volume is None:
            raise MarketDataError(f"no volume available for {symbol!r}")
        return int(volume)

    def get_history(self, symbol: str, *, period: str = "3mo", interval: str = "1d") -> list[PricePoint]:
        try:
            frame = yf.Ticker(symbol).history(period=period, interval=interval)
        except Exception as exc:  # yfinance can raise a variety of network/parse errors
            raise MarketDataError(f"failed to fetch history for {symbol!r}: {exc}") from exc

        if frame.empty:
            raise MarketDataError(f"no history available for {symbol!r} (period={period}, interval={interval})")

        return [
            PricePoint(
                date=index.date(),
                open=_to_price(row["Open"]),
                high=_to_price(row["High"]),
                low=_to_price(row["Low"]),
                close=_to_price(row["Close"]),
                volume=int(row["Volume"]),
            )
            for index, row in frame.iterrows()
        ]

    def get_market_cap(self, symbol: str) -> Decimal:
        fast_info = self._fast_info(symbol)
        market_cap = fast_info.get("marketCap")
        if market_cap is None:
            raise MarketDataError(f"no market cap available for {symbol!r}")
        return Decimal(str(market_cap)).quantize(_CENT, rounding=ROUND_HALF_UP)

    def get_market_status(self) -> MarketStatus:
        """US equity regular-session hours (9:30-16:00 America/New_York, Mon-Fri).

        Does not account for market holidays — a known v1 simplification,
        not fabricated data (the open/closed answer is computed from the
        real current time, and will just be wrong on a handful of holidays
        per year until a holiday calendar is added).
        """
        now = datetime.now(_EASTERN)
        is_weekday = now.weekday() < 5
        open_time = now.replace(hour=_MARKET_OPEN[0], minute=_MARKET_OPEN[1], second=0, microsecond=0)
        close_time = now.replace(hour=_MARKET_CLOSE[0], minute=_MARKET_CLOSE[1], second=0, microsecond=0)
        is_open = is_weekday and open_time <= now < close_time

        return MarketStatus(is_open=is_open, session="regular" if is_open else "closed", as_of=now)

    @staticmethod
    def _fast_info(symbol: str) -> dict:
        try:
            return dict(yf.Ticker(symbol).fast_info)
        except Exception as exc:
            raise MarketDataError(f"failed to fetch quote for {symbol!r}: {exc}") from exc
