from decimal import Decimal

import pytest

from app.analysis.technical import (
    average_volume,
    historical_volatility,
    is_uptrend,
    percent_change,
    rsi,
    simple_moving_average,
    trend_direction,
)


def test_simple_moving_average_uses_most_recent_window() -> None:
    values = [Decimal(10), Decimal(20), Decimal(30), Decimal(40)]

    assert simple_moving_average(values, 2) == Decimal(35)  # (30+40)/2


def test_simple_moving_average_requires_enough_values() -> None:
    with pytest.raises(ValueError):
        simple_moving_average([Decimal(1), Decimal(2)], 5)


def test_percent_change_positive() -> None:
    assert percent_change(Decimal(100), Decimal(110)) == Decimal(10)


def test_percent_change_negative() -> None:
    assert percent_change(Decimal(100), Decimal(90)) == Decimal(-10)


def test_percent_change_rejects_zero_start() -> None:
    with pytest.raises(ValueError):
        percent_change(Decimal(0), Decimal(10))


def test_average_volume_uses_most_recent_window() -> None:
    volumes = [1000, 2000, 3000, 5000]

    assert average_volume(volumes, 2) == Decimal(4000)  # (3000+5000)/2


def test_is_uptrend_true_when_price_above_average() -> None:
    assert is_uptrend(Decimal(110), Decimal(100)) is True


def test_is_uptrend_false_when_price_at_or_below_average() -> None:
    assert is_uptrend(Decimal(100), Decimal(100)) is False
    assert is_uptrend(Decimal(90), Decimal(100)) is False


def test_rsi_hand_computed_mixed_gains_and_losses() -> None:
    # changes: +2, -1, +4, -1 -> avg_gain=1.5, avg_loss=0.5 -> RS=3
    # RSI = 100 - 100/(1+3) = 75
    closes = [Decimal(100), Decimal(102), Decimal(101), Decimal(105), Decimal(104)]

    assert rsi(closes, period=4) == Decimal(75)


def test_rsi_is_100_when_no_losses() -> None:
    closes = [Decimal(100), Decimal(101), Decimal(102), Decimal(103), Decimal(104)]

    assert rsi(closes, period=4) == Decimal(100)


def test_rsi_is_0_when_no_gains() -> None:
    closes = [Decimal(104), Decimal(103), Decimal(102), Decimal(101), Decimal(100)]

    assert rsi(closes, period=4) == Decimal(0)


def test_rsi_requires_enough_closes() -> None:
    with pytest.raises(ValueError):
        rsi([Decimal(100), Decimal(101)], period=14)


def test_historical_volatility_hand_computed() -> None:
    # Each step is engineered to be exactly +/-10%: returns = [10,-10,10,-10]
    # mean=0, variance=(100*4)/4=100, stdev=sqrt(100)=10
    closes = [Decimal(100), Decimal(110), Decimal(99), Decimal("108.9"), Decimal("98.01")]

    assert historical_volatility(closes, period=4) == Decimal(10)


def test_historical_volatility_requires_enough_closes() -> None:
    with pytest.raises(ValueError):
        historical_volatility([Decimal(100), Decimal(101)], period=20)


def test_trend_direction_up_when_short_ma_above_long_ma() -> None:
    closes = [Decimal(100), Decimal(100), Decimal(100), Decimal(100), Decimal(200), Decimal(200)]

    assert trend_direction(closes, short_period=2, long_period=4) == "up"


def test_trend_direction_down_when_short_ma_below_long_ma() -> None:
    closes = [Decimal(200), Decimal(200), Decimal(200), Decimal(200), Decimal(100), Decimal(100)]

    assert trend_direction(closes, short_period=2, long_period=4) == "down"


def test_trend_direction_flat_when_mas_are_equal() -> None:
    closes = [Decimal(100)] * 10

    assert trend_direction(closes, short_period=2, long_period=4) == "flat"


def test_trend_direction_rejects_invalid_period_ordering() -> None:
    with pytest.raises(ValueError):
        trend_direction([Decimal(100)] * 10, short_period=10, long_period=5)
