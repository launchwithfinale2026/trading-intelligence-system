"""Pure technical-indicator functions.

Every function here takes plain numbers/lists and returns plain numbers —
no MarketDataProvider, no I/O. That's what makes the scanner (Phase 6) and
strategies (Phase 7) that call these fully unit-testable with fixture data.
"""

from decimal import Decimal


def simple_moving_average(values: list[Decimal], period: int) -> Decimal:
    """Average of the most recent `period` values (last item = most recent)."""
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        raise ValueError(f"need at least {period} values, got {len(values)}")

    window = values[-period:]
    return sum(window, Decimal(0)) / period


def percent_change(start: Decimal, end: Decimal) -> Decimal:
    """Percentage change from start to end, e.g. Decimal('12.5') for +12.5%."""
    if start == 0:
        raise ValueError("start must be non-zero")
    return (end - start) / start * 100


def average_volume(volumes: list[int], period: int) -> Decimal:
    """Average of the most recent `period` volumes (last item = most recent)."""
    if period <= 0:
        raise ValueError("period must be positive")
    if len(volumes) < period:
        raise ValueError(f"need at least {period} volumes, got {len(volumes)}")

    window = volumes[-period:]
    return Decimal(sum(window)) / period


def is_uptrend(price: Decimal, moving_average: Decimal) -> bool:
    """True when price is above its own moving average — a simple trend proxy."""
    return price > moving_average
