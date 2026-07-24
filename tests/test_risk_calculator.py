from decimal import Decimal

import pytest

from app.domain.enums import RiskPreference
from app.risk.calculator import calculate_position_size


def test_aggressive_long_position_hand_computed() -> None:
    # account=1000, 2% risk -> $20 budget; entry 175, stop 168 -> $7/share risk
    # floor(20/7) = 2 shares
    result = calculate_position_size(
        account_size=Decimal("1000"),
        risk_preference=RiskPreference.AGGRESSIVE,
        entry=Decimal("175"),
        stop_loss=Decimal("168"),
    )

    assert result.shares == 2
    assert result.position_value == Decimal("350")
    assert result.dollar_risk == Decimal("14")
    assert result.risk_percent == Decimal("0.02")


def test_conservative_long_position_hand_computed() -> None:
    # account=5000, 0.5% risk -> $25 budget; entry 50, stop 45 -> $5/share risk
    # floor(25/5) = 5 shares
    result = calculate_position_size(
        account_size=Decimal("5000"),
        risk_preference=RiskPreference.CONSERVATIVE,
        entry=Decimal("50"),
        stop_loss=Decimal("45"),
    )

    assert result.shares == 5
    assert result.position_value == Decimal("250")
    assert result.dollar_risk == Decimal("25")
    assert result.risk_percent == Decimal("0.005")


def test_moderate_long_position_hand_computed() -> None:
    # account=2000, 1% risk -> $20 budget; entry 100, stop 90 -> $10/share risk
    # floor(20/10) = 2 shares
    result = calculate_position_size(
        account_size=Decimal("2000"),
        risk_preference=RiskPreference.MODERATE,
        entry=Decimal("100"),
        stop_loss=Decimal("90"),
    )

    assert result.shares == 2
    assert result.position_value == Decimal("200")
    assert result.dollar_risk == Decimal("20")


def test_short_position_uses_absolute_distance() -> None:
    # short: stop above entry. Same $/share risk math as a long.
    result = calculate_position_size(
        account_size=Decimal("2000"),
        risk_preference=RiskPreference.MODERATE,
        entry=Decimal("100"),
        stop_loss=Decimal("110"),
    )

    assert result.shares == 2
    assert result.dollar_risk == Decimal("20")


def test_zero_shares_when_budget_below_one_share_risk() -> None:
    # account=100, 2% -> $2 budget; $7/share risk -> can't afford even 1 share
    result = calculate_position_size(
        account_size=Decimal("100"),
        risk_preference=RiskPreference.AGGRESSIVE,
        entry=Decimal("175"),
        stop_loss=Decimal("168"),
    )

    assert result.shares == 0
    assert result.position_value == Decimal("0")
    assert result.dollar_risk == Decimal("0")


def test_rejects_non_positive_account_size() -> None:
    with pytest.raises(ValueError):
        calculate_position_size(
            account_size=Decimal("0"),
            risk_preference=RiskPreference.MODERATE,
            entry=Decimal("100"),
            stop_loss=Decimal("90"),
        )


def test_rejects_non_positive_entry() -> None:
    with pytest.raises(ValueError):
        calculate_position_size(
            account_size=Decimal("1000"),
            risk_preference=RiskPreference.MODERATE,
            entry=Decimal("0"),
            stop_loss=Decimal("-10"),
        )


def test_rejects_stop_equal_to_entry() -> None:
    with pytest.raises(ValueError):
        calculate_position_size(
            account_size=Decimal("1000"),
            risk_preference=RiskPreference.MODERATE,
            entry=Decimal("100"),
            stop_loss=Decimal("100"),
        )
