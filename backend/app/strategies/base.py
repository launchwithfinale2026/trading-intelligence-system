"""Strategy interface and the Signal contract every strategy must return.

Signal here is a plain dataclass, not the SQLAlchemy model — strategies are
pure functions of price history and shouldn't know about the database.
Persisting a Signal (Phase 9, once alerts are wired up) is the caller's job.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import SignalDirection
from app.market.provider import PricePoint


@dataclass(frozen=True, slots=True)
class Signal:
    symbol: str
    direction: SignalDirection
    entry: Decimal
    stop_loss: Decimal
    target: Decimal
    confidence: int  # 0-100
    reasoning: list[str]
    strategy_name: str


class Strategy(ABC):
    """One trading strategy. Implementations are pure: given the same price
    history, evaluate() always returns the same result (or None).
    """

    name: str

    @abstractmethod
    def evaluate(self, symbol: str, history: list[PricePoint]) -> Signal | None:
        """Returns a Signal if this strategy's conditions are met for the
        given history, oldest-first; otherwise None. Never raises for
        "no signal" — only for genuinely malformed input.
        """
