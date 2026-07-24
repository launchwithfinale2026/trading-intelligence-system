from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import RiskPreference
from app.repositories.risk_policy_repository import RiskPolicyRepository
from app.risk.calculator import PositionSize, calculate_position_size, calculate_position_size_from_percent
from app.risk.policy import resolve_risk_percent


class RiskPolicyService:
    """The runtime seam between "a user's chosen risk_preference" and "a
    concrete position size": looks up a same-named RiskPolicy row and, if
    one exists, sizes the position from its (database-defined) breakpoints.
    Falls back to the fixed RISK_PERCENT_BY_PREFERENCE percents only when no
    policy is configured for that name — e.g. an unseeded database.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.policies = RiskPolicyRepository(db)

    def size_position(
        self,
        *,
        account_size: Decimal,
        risk_preference: RiskPreference,
        entry: Decimal,
        stop_loss: Decimal,
    ) -> PositionSize:
        policy = self.policies.get_by_name(risk_preference.value)
        if policy is None:
            return calculate_position_size(
                account_size=account_size, risk_preference=risk_preference, entry=entry, stop_loss=stop_loss
            )

        breakpoints = [(Decimal(size), Decimal(percent)) for size, percent in policy.breakpoints]
        risk_percent = resolve_risk_percent(breakpoints, account_size)
        return calculate_position_size_from_percent(
            account_size=account_size, risk_percent=risk_percent, entry=entry, stop_loss=stop_loss
        )
