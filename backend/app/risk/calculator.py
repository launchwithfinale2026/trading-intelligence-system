"""Position sizing: every signal must translate its entry/stop distance into
a concrete number of shares, bounded by how much of the account a user is
willing to risk on one trade. Pure functions — no I/O, no models — so every
case is exactly reproducible from hand-computed expected values.
"""

import math
from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import RiskPreference

# Percent of account equity risked on a single trade, by preference.
# Spec gives aggressive=2% and conservative=0.5% explicitly; moderate=1% is
# this project's own interpolation (documented in docs/DECISIONS.md).
RISK_PERCENT_BY_PREFERENCE: dict[RiskPreference, Decimal] = {
    RiskPreference.CONSERVATIVE: Decimal("0.005"),
    RiskPreference.MODERATE: Decimal("0.01"),
    RiskPreference.AGGRESSIVE: Decimal("0.02"),
}


@dataclass(frozen=True, slots=True)
class PositionSize:
    shares: int
    position_value: Decimal
    dollar_risk: Decimal
    risk_percent: Decimal


def calculate_position_size(
    *,
    account_size: Decimal,
    risk_preference: RiskPreference,
    entry: Decimal,
    stop_loss: Decimal,
) -> PositionSize:
    """Whole-share position size such that a stop-out risks no more than the
    user's risk percentage of their account.

    Works for both long (stop below entry) and short (stop above entry)
    signals — only the distance between entry and stop matters.

    Raises ValueError for inputs that can't produce a real position: a
    non-positive account/entry, or a stop equal to entry (zero risk per
    share, so no amount of sizing logic can bound the risk).
    """
    if account_size <= 0:
        raise ValueError("account_size must be positive")
    if entry <= 0:
        raise ValueError("entry must be positive")
    if entry == stop_loss:
        raise ValueError("stop_loss cannot equal entry (zero risk per share)")

    risk_percent = RISK_PERCENT_BY_PREFERENCE[risk_preference]
    risk_budget = account_size * risk_percent
    per_share_risk = abs(entry - stop_loss)

    shares = math.floor(risk_budget / per_share_risk)

    return PositionSize(
        shares=shares,
        position_value=shares * entry,
        dollar_risk=shares * per_share_risk,
        risk_percent=risk_percent,
    )
