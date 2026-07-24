from datetime import date, timedelta
from decimal import Decimal

from app.domain.enums import SignalDirection
from app.market.provider import PricePoint
from app.strategies.momentum import MomentumStrategy


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


def _qualifying_history() -> list[PricePoint]:
    flat = [100.0] * 50
    uptrend = [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 115.0]
    closes = flat + uptrend
    volumes = [1_000_000] * 59 + [2_000_000]
    return _history(closes, volumes)


def test_momentum_strategy_fires_signal_when_all_conditions_met() -> None:
    strategy = MomentumStrategy()

    signal = strategy.evaluate("NVDA", _qualifying_history())

    assert signal is not None
    assert signal.symbol == "NVDA"
    assert signal.direction == SignalDirection.LONG
    assert signal.strategy_name == "momentum"
    assert signal.entry == Decimal("115.00")
    assert signal.stop_loss < signal.entry
    assert signal.target > signal.entry
    assert 0 <= signal.confidence <= 100
    assert len(signal.reasoning) == 3


def test_momentum_strategy_returns_none_with_insufficient_history() -> None:
    strategy = MomentumStrategy()
    short_history = _history([100.0] * 30, [1_000_000] * 30)

    assert strategy.evaluate("NVDA", short_history) is None


def test_momentum_strategy_returns_none_without_momentum_burst() -> None:
    strategy = MomentumStrategy()
    # Flat the whole way through, tiny uptick at the end — no real momentum.
    closes = [100.0] * 59 + [100.5]
    volumes = [1_000_000] * 59 + [1_050_000]
    history = _history(closes, volumes)

    assert strategy.evaluate("NVDA", history) is None


def test_momentum_strategy_returns_none_without_volume_confirmation() -> None:
    strategy = MomentumStrategy()
    flat = [100.0] * 50
    uptrend = [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 115.0]
    closes = flat + uptrend
    # No volume surge on the breakout day.
    volumes = [1_000_000] * 60
    history = _history(closes, volumes)

    assert strategy.evaluate("NVDA", history) is None


def test_momentum_strategy_returns_none_when_price_below_moving_average() -> None:
    strategy = MomentumStrategy()
    # Downtrend overall, even with a brief recent pop.
    closes = [200.0] * 50 + [150.0, 148.0, 146.0, 144.0, 142.0, 140.0, 138.0, 136.0, 134.0, 140.0]
    volumes = [1_000_000] * 59 + [2_000_000]
    history = _history(closes, volumes)

    assert strategy.evaluate("NVDA", history) is None
