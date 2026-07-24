from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.models.risk_policy import RiskPolicy
from app.domain.enums import RiskPreference
from app.services.risk_policy_service import RiskPolicyService


def test_uses_database_policy_when_one_exists(db_session: Session) -> None:
    db_session.add(
        RiskPolicy(
            name="experimental",
            breakpoints=[["10", "0.50"], ["999", "0.20"], ["10000", "0.01"]],
        )
    )
    db_session.commit()

    result = RiskPolicyService(db_session).size_position(
        account_size=Decimal("10"),
        risk_preference=RiskPreference.EXPERIMENTAL,
        entry=Decimal("100"),
        stop_loss=Decimal("90"),
    )

    # $10 account, 50% risk -> $5 budget; $10/share risk -> floor(5/10) = 0 shares
    assert result.risk_percent == Decimal("0.50")
    assert result.shares == 0


def test_scaled_curve_produces_real_shares_at_larger_account_size(db_session: Session) -> None:
    db_session.add(
        RiskPolicy(
            name="experimental",
            breakpoints=[["10", "0.50"], ["999", "0.20"], ["10000", "0.01"]],
        )
    )
    db_session.commit()

    result = RiskPolicyService(db_session).size_position(
        account_size=Decimal("999"),
        risk_preference=RiskPreference.EXPERIMENTAL,
        entry=Decimal("100"),
        stop_loss=Decimal("90"),
    )

    # $999 account, 20% risk -> $199.80 budget; $10/share risk -> floor(19.98) = 19 shares
    assert result.risk_percent == Decimal("0.20")
    assert result.shares == 19


def test_falls_back_to_fixed_percent_when_no_policy_row_exists(db_session: Session) -> None:
    result = RiskPolicyService(db_session).size_position(
        account_size=Decimal("1000"),
        risk_preference=RiskPreference.AGGRESSIVE,
        entry=Decimal("175"),
        stop_loss=Decimal("168"),
    )

    assert result.risk_percent == Decimal("0.02")
    assert result.shares == 2


def test_flat_policy_matches_fixed_percent_when_seeded(db_session: Session) -> None:
    db_session.add(RiskPolicy(name="conservative", breakpoints=[["0", "0.005"]]))
    db_session.commit()

    result = RiskPolicyService(db_session).size_position(
        account_size=Decimal("5000"),
        risk_preference=RiskPreference.CONSERVATIVE,
        entry=Decimal("50"),
        stop_loss=Decimal("45"),
    )

    assert result.risk_percent == Decimal("0.005")
    assert result.shares == 5
