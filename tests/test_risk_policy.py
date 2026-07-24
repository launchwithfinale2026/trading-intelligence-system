from decimal import Decimal

import pytest

from app.risk.policy import resolve_risk_percent


def test_flat_below_first_breakpoint() -> None:
    breakpoints = [(Decimal("1000"), Decimal("0.02")), (Decimal("10000"), Decimal("0.01"))]

    assert resolve_risk_percent(breakpoints, Decimal("10")) == Decimal("0.02")


def test_flat_above_last_breakpoint() -> None:
    breakpoints = [(Decimal("1000"), Decimal("0.02")), (Decimal("10000"), Decimal("0.01"))]

    assert resolve_risk_percent(breakpoints, Decimal("50000")) == Decimal("0.01")


def test_linear_interpolation_at_midpoint() -> None:
    breakpoints = [(Decimal("1000"), Decimal("0.02")), (Decimal("2000"), Decimal("0.01"))]

    assert resolve_risk_percent(breakpoints, Decimal("1500")) == Decimal("0.015")


def test_experimental_curve_hand_computed() -> None:
    # 50% at $10, tapering to 20% at $999, tapering to 1% at $10,000.
    breakpoints = [(Decimal("10"), Decimal("0.50")), (Decimal("999"), Decimal("0.20")), (Decimal("10000"), Decimal("0.01"))]

    assert resolve_risk_percent(breakpoints, Decimal("10")) == Decimal("0.50")
    assert resolve_risk_percent(breakpoints, Decimal("999")) == Decimal("0.20")
    assert resolve_risk_percent(breakpoints, Decimal("10000")) == Decimal("0.01")
    assert resolve_risk_percent(breakpoints, Decimal("5")) == Decimal("0.50")  # below first point
    assert resolve_risk_percent(breakpoints, Decimal("20000")) == Decimal("0.01")  # above last point


def test_single_breakpoint_is_flat_regardless_of_account_size() -> None:
    breakpoints = [(Decimal("0"), Decimal("0.02"))]

    assert resolve_risk_percent(breakpoints, Decimal("10")) == Decimal("0.02")
    assert resolve_risk_percent(breakpoints, Decimal("1000000")) == Decimal("0.02")


def test_rejects_empty_breakpoints() -> None:
    with pytest.raises(ValueError):
        resolve_risk_percent([], Decimal("1000"))


def test_breakpoints_do_not_need_to_be_pre_sorted() -> None:
    breakpoints = [(Decimal("2000"), Decimal("0.01")), (Decimal("1000"), Decimal("0.02"))]

    assert resolve_risk_percent(breakpoints, Decimal("1500")) == Decimal("0.015")
