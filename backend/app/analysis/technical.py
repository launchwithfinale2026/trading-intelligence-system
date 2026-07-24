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


def rsi(closes: list[Decimal], period: int = 14) -> Decimal:
    """Wilder's Relative Strength Index over the trailing `period` closes.

    Returns a value in [0, 100]. When there are no losses in the window,
    RSI is defined as 100 (avoids a division by zero rather than faking a
    number) — a real, if degenerate, outcome of an all-up window.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    if len(closes) < period + 1:
        raise ValueError(f"need at least {period + 1} closes, got {len(closes)}")

    window = closes[-(period + 1):]
    total_gain = Decimal(0)
    total_loss = Decimal(0)
    for previous, current in zip(window, window[1:]):
        change = current - previous
        if change > 0:
            total_gain += change
        else:
            total_loss += -change

    avg_gain = total_gain / period
    avg_loss = total_loss / period
    if avg_loss == 0:
        return Decimal(100)

    relative_strength = avg_gain / avg_loss
    return Decimal(100) - (Decimal(100) / (1 + relative_strength))


def historical_volatility(closes: list[Decimal], period: int) -> Decimal:
    """Standard deviation of daily percent returns over the trailing
    `period` closes, expressed as a percentage (e.g. Decimal('2.35') means
    the day-to-day move size is typically around 2.35%).

    A simple, real measure of how erratically a symbol has actually been
    trading — not implied/options-derived volatility, which would need a
    different data source.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    if len(closes) < period + 1:
        raise ValueError(f"need at least {period + 1} closes, got {len(closes)}")

    window = closes[-(period + 1):]
    returns = [percent_change(previous, current) for previous, current in zip(window, window[1:])]
    mean_return = sum(returns, Decimal(0)) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    return variance.sqrt()


def trend_direction(closes: list[Decimal], short_period: int, long_period: int) -> str:
    """"up" if the short moving average is above the long one, "down" if
    below, "flat" if they're equal. A standard MA-crossover trend proxy.
    """
    if short_period >= long_period:
        raise ValueError("short_period must be less than long_period")

    short_ma = simple_moving_average(closes, short_period)
    long_ma = simple_moving_average(closes, long_period)

    if short_ma > long_ma:
        return "up"
    if short_ma < long_ma:
        return "down"
    return "flat"
