from datetime import date, timedelta
from decimal import Decimal

from app.domain.enums import SignalDirection
from app.market.provider import PricePoint
from app.strategies.momentum_breakout import MomentumBreakoutStrategy


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


# 20 flat bars establish a resistance level, then a choppy-but-net-up run
# breaks above it on strong volume while keeping RSI out of overbought
# territory (mixed up/down days, not one big vertical move).
_QUALIFYING_TAIL = [98, 101, 97, 102, 98, 103, 99, 104, 100, 106]


def _qualifying_history() -> list[PricePoint]:
    closes = [100.0] * 20 + _QUALIFYING_TAIL
    volumes = [1_000_000] * 29 + [3_000_000]
    return _history(closes, volumes)


def test_fires_when_all_four_conditions_are_met() -> None:
    strategy = MomentumBreakoutStrategy()

    signal = strategy.evaluate("TEST", _qualifying_history())

    assert signal is not None
    assert signal.direction == SignalDirection.LONG
    assert signal.strategy_name == "momentum_breakout"
    assert signal.entry == Decimal("106")
    assert signal.stop_loss == Decimal("104")  # the broken resistance level
    assert signal.target == Decimal("111.00")  # entry + 2.5R
    assert 0 <= signal.confidence <= 100
    assert len(signal.reasoning) == 4


def test_returns_none_with_insufficient_history() -> None:
    strategy = MomentumBreakoutStrategy()
    short_history = _history([100.0] * 20, [1_000_000] * 20)

    assert strategy.evaluate("TEST", short_history) is None


def test_returns_none_without_structure_break() -> None:
    strategy = MomentumBreakoutStrategy()
    closes = [100.0] * 20 + [98, 101, 97, 102, 98, 103, 99, 104, 100, 103]  # stays under 104
    volumes = [1_000_000] * 29 + [3_000_000]

    assert strategy.evaluate("TEST", _history(closes, volumes)) is None


def test_returns_none_without_volume_confirmation() -> None:
    strategy = MomentumBreakoutStrategy()
    closes = [100.0] * 20 + _QUALIFYING_TAIL
    volumes = [1_000_000] * 30  # no surge on the breakout bar

    assert strategy.evaluate("TEST", _history(closes, volumes)) is None


def test_returns_none_when_already_overbought() -> None:
    strategy = MomentumBreakoutStrategy()
    # A single sharp vertical move instead of a choppy climb pushes RSI to 100.
    closes = [100.0] * 29 + [115.0]
    volumes = [1_000_000] * 29 + [3_000_000]

    assert strategy.evaluate("TEST", _history(closes, volumes)) is None


def test_returns_none_without_momentum() -> None:
    strategy = MomentumBreakoutStrategy()
    # Breaks the recent high only very slightly with no real momentum.
    closes = [100.0] * 29 + [100.5]
    volumes = [1_000_000] * 29 + [3_000_000]

    assert strategy.evaluate("TEST", _history(closes, volumes)) is None
