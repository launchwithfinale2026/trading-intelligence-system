from decimal import Decimal

import pytest

from app.analysis.technical import average_volume, is_uptrend, percent_change, simple_moving_average


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
