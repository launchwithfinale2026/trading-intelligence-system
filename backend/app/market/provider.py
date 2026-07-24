"""The market data abstraction every other subsystem depends on.

Nothing outside this module (and its concrete implementations) should ever
import a specific data vendor's SDK. Callers (Scanner, Strategy Engine,
Portfolio Tracker) depend only on MarketDataProvider, so swapping the
backing vendor later is a new adapter class, not a rewrite of callers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PricePoint:
    """One bar of OHLCV history."""

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True, slots=True)
class MarketStatus:
    is_open: bool
    session: str  # "regular" | "closed"
    as_of: datetime


class MarketDataProvider(ABC):
    """Interface every market data vendor adapter must implement.

    Implementations must raise app.core.exceptions.MarketDataError when real
    data cannot be obtained — never return fabricated or placeholder values.
    """

    @abstractmethod
    def get_price(self, symbol: str) -> Decimal:
        """Latest known trade price for symbol."""

    @abstractmethod
    def get_history(self, symbol: str, *, period: str = "3mo", interval: str = "1d") -> list[PricePoint]:
        """OHLCV history for symbol, oldest first.

        period/interval follow yfinance's vocabulary (e.g. "3mo"/"1d") since
        it's the first implementation, but any adapter may accept the same
        strings and map them internally.
        """

    @abstractmethod
    def get_volume(self, symbol: str) -> int:
        """Latest known trading volume for symbol."""

    @abstractmethod
    def get_market_status(self) -> MarketStatus:
        """Whether the market is currently open, as of now."""
