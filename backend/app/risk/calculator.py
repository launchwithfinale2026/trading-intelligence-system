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
#
# This dict is the fallback only — services.risk_policy_service.RiskPolicyService
# looks up a same-named, data-driven RiskPolicy row first (see risk/policy.py)
# and only falls back to these fixed values if no such row exists (e.g. a
# fresh, unseeded database, or a unit test that doesn't seed risk_policies).
# EXPERIMENTAL has no natural fixed value of its own — it exists purely as a
# named slot for a database-defined policy, so its fallback mirrors aggressive.
RISK_PERCENT_BY_PREFERENCE: dict[RiskPreference, Decimal] = {
    RiskPreference.CONSERVATIVE: Decimal("0.005"),
    RiskPreference.MODERATE: Decimal("0.01"),
    RiskPreference.AGGRESSIVE: Decimal("0.02"),
    RiskPreference.EXPERIMENTAL: Decimal("0.02"),
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
    """Whole-share position size for one of the fixed named preferences.

    Prefer services.risk_policy_service.RiskPolicyService.size_position for
    anything user-facing — it resolves the same preference against the
    database-driven policy first and only falls back to the fixed percents
    here when no such policy is configured.
    """
    return calculate_position_size_from_percent(
        account_size=account_size,
        risk_percent=RISK_PERCENT_BY_PREFERENCE[risk_preference],
        entry=entry,
        stop_loss=stop_loss,
    )


def calculate_position_size_from_percent(
    *,
    account_size: Decimal,
    risk_percent: Decimal,
    entry: Decimal,
    stop_loss: Decimal,
) -> PositionSize:
    """Whole-share position size such that a stop-out risks no more than
    risk_percent of the account.

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

    risk_budget = account_size * risk_percent
    per_share_risk = abs(entry - stop_loss)

    shares = math.floor(risk_budget / per_share_risk)

    return PositionSize(
        shares=shares,
        position_value=shares * entry,
        dollar_risk=shares * per_share_risk,
        risk_percent=risk_percent,
    )
