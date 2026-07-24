from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.domain.enums import DecisionType, SignalDirection
from app.services.decision_service import DecisionService
from app.services.signal_service import SignalService
from app.strategies.base import Signal as StrategySignal


def _seed_signal(db_session: Session) -> int:
    signal = SignalService(db_session).record_signal(
        StrategySignal(
            symbol="NVDA",
            direction=SignalDirection.LONG,
            entry=Decimal("175.00"),
            stop_loss=Decimal("168.00"),
            target=Decimal("189.00"),
            confidence=82,
            reasoning=["fixture"],
            strategy_name="momentum",
        )
    )
    return signal.id


def test_record_decision_persists_open(db_session: Session) -> None:
    signal_id = _seed_signal(db_session)

    decision = DecisionService(db_session).record_decision(user_id=1, signal_id=signal_id, decision=DecisionType.OPEN)

    assert decision.id is not None
    assert decision.user_id == 1
    assert decision.signal_id == signal_id
    assert decision.decision == DecisionType.OPEN


def test_record_decision_rejects_duplicate_for_same_user_and_signal(db_session: Session) -> None:
    signal_id = _seed_signal(db_session)
    service = DecisionService(db_session)
    service.record_decision(user_id=1, signal_id=signal_id, decision=DecisionType.OPEN)

    with pytest.raises(ConflictError):
        service.record_decision(user_id=1, signal_id=signal_id, decision=DecisionType.IGNORE)


def test_different_users_can_each_decide_on_the_same_signal(db_session: Session) -> None:
    signal_id = _seed_signal(db_session)
    service = DecisionService(db_session)

    service.record_decision(user_id=1, signal_id=signal_id, decision=DecisionType.OPEN)
    ignored = service.record_decision(user_id=2, signal_id=signal_id, decision=DecisionType.IGNORE)

    assert ignored.decision == DecisionType.IGNORE


def test_record_decision_for_unknown_signal_raises_not_found(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        DecisionService(db_session).record_decision(user_id=1, signal_id=999, decision=DecisionType.OPEN)
