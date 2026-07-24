from datetime import date, timedelta
from decimal import Decimal

from app.domain.enums import SignalDirection
from app.market.provider import PricePoint
from app.strategies.breakout import BreakoutStrategy


def _history(closes: list[float], volumes: list[int]) -> list[PricePoint]:
    start = date(2026, 1, 1)
    return [
        PricePoint(
            date=start + timedelta(days=i),
            open=Decimal(str(c)),
            high=Decimal(str(c)),
            low=Decimal(str(c)),
            close=Decimal(str(c)),
            volume=v,
        )
        for i, (c, v) in enumerate(zip(closes, volumes, strict=True))
    ]


def test_breakout_strategy_fires_signal_on_structure_break_with_volume() -> None:
    strategy = BreakoutStrategy()
    closes = [100.0] * 20 + [110.0]
    volumes = [1_000_000] * 20 + [2_000_000]
    history = _history(closes, volumes)

    signal = strategy.evaluate("AMD", history)

    assert signal is not None
    assert signal.direction == SignalDirection.LONG
    assert signal.strategy_name == "breakout"
    assert signal.entry == Decimal("110.0")
    assert signal.stop_loss == Decimal("100.0")  # broken resistance becomes support
    assert signal.target == Decimal("130.00")  # 2R above entry
    assert 0 <= signal.confidence <= 100
    assert len(signal.reasoning) == 3


def test_breakout_strategy_returns_none_with_insufficient_history() -> None:
    strategy = BreakoutStrategy()
    short_history = _history([100.0] * 10, [1_000_000] * 10)

    assert strategy.evaluate("AMD", short_history) is None


def test_breakout_strategy_returns_none_without_structure_break() -> None:
    strategy = BreakoutStrategy()
    closes = [100.0] * 20 + [99.0]  # stays inside prior range
    volumes = [1_000_000] * 20 + [2_000_000]
    history = _history(closes, volumes)

    assert strategy.evaluate("AMD", history) is None


def test_breakout_strategy_returns_none_without_volume_confirmation() -> None:
    strategy = BreakoutStrategy()
    closes = [100.0] * 20 + [110.0]
    volumes = [1_000_000] * 21  # no surge on the breakout bar

    assert strategy.evaluate("AMD", _history(closes, volumes)) is None
