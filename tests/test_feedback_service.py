from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.domain.enums import (
    AlertPreference,
    DecisionType,
    PositionStatus,
    RiskPreference,
    SignalDirection,
    TradingStyle,
)
from app.services.decision_service import DecisionService
from app.services.feedback_service import FeedbackService
from app.services.position_service import PositionService
from app.services.signal_service import SignalService
from app.services.user_service import UserService
from app.strategies.base import Signal as StrategySignal


def _seed_user(db_session: Session, username: str = "jake"):
    return UserService(db_session).create_user(
        username=username,
        email=f"{username}@example.com",
        password_hash="not-a-real-hash",
        account_size=Decimal("100000.00"),
        risk_preference=RiskPreference.AGGRESSIVE,
        trading_style=TradingStyle.MOMENTUM,
        alert_preference=AlertPreference.ALL_SIGNALS,
    )


def _seed_signal(db_session: Session, *, strategy_name: str, symbol: str = "NVDA"):
    return SignalService(db_session).record_signal(
        StrategySignal(
            symbol=symbol,
            direction=SignalDirection.LONG,
            entry=Decimal("100.00"),
            stop_loss=Decimal("90.00"),
            target=Decimal("120.00"),
            confidence=80,
            reasoning=["fixture"],
            strategy_name=strategy_name,
        )
    )


def _open_and_close(db_session: Session, user, signal, *, close_price: Decimal, status: PositionStatus):
    position = PositionService(db_session).open_position(user=user, signal=signal)
    closed = PositionService(db_session).close_position(position, close_price=close_price, status=status)
    return closed


def test_record_trade_result_computes_win_and_r_multiple_for_target_hit(db_session: Session) -> None:
    user = _seed_user(db_session)
    signal = _seed_signal(db_session, strategy_name="momentum")
    position = _open_and_close(db_session, user, signal, close_price=Decimal("120.00"), status=PositionStatus.CLOSED_TARGET)

    result = FeedbackService(db_session).record_trade_result(position=position, signal=signal)

    # entry 100, stop 90 -> $10/share risk; closed at 120 -> +$20/share -> +2.00R
    assert result.is_win is True
    assert result.r_multiple == Decimal("2.00")
    assert result.pnl == Decimal("20.00") * position.shares


def test_record_trade_result_computes_loss_for_stop_hit(db_session: Session) -> None:
    user = _seed_user(db_session)
    signal = _seed_signal(db_session, strategy_name="momentum")
    position = _open_and_close(db_session, user, signal, close_price=Decimal("90.00"), status=PositionStatus.CLOSED_STOP)

    result = FeedbackService(db_session).record_trade_result(position=position, signal=signal)

    assert result.is_win is False
    assert result.r_multiple == Decimal("-1.00")


def test_record_trade_result_rejects_duplicate_for_same_position(db_session: Session) -> None:
    user = _seed_user(db_session)
    signal = _seed_signal(db_session, strategy_name="momentum")
    position = _open_and_close(db_session, user, signal, close_price=Decimal("120.00"), status=PositionStatus.CLOSED_TARGET)
    service = FeedbackService(db_session)
    service.record_trade_result(position=position, signal=signal)

    with pytest.raises(ConflictError):
        service.record_trade_result(position=position, signal=signal)


def test_record_trade_result_rejects_open_position(db_session: Session) -> None:
    user = _seed_user(db_session)
    signal = _seed_signal(db_session, strategy_name="momentum")
    position = PositionService(db_session).open_position(user=user, signal=signal)

    with pytest.raises(ValueError):
        FeedbackService(db_session).record_trade_result(position=position, signal=signal)


def test_performance_by_strategy_hand_computed(db_session: Session) -> None:
    """
    Scenario, hand-computed:
      momentum: 3 signals generated.
        - signal A: jake OPENs -> position closes at target -> win, +2.00R
        - signal B: jake OPENs -> position closes at stop -> loss, -1.00R
        - signal C: friend IGNOREs -> no position
      breakout: 1 signal generated, no decisions, no trades.

    Expected momentum stats: signals_generated=3, accepted=1 (OPEN count;
    each user's decision counts once — here 2 OPENs total across 2 signals,
    but we assert precisely below rather than guessing), ignored=1,
    trades_closed=2, wins=1, win_rate=50.0, average_r_multiple=(2.00-1.00)/2=0.50
    """
    jake = _seed_user(db_session, "jake")
    friend = _seed_user(db_session, "friend")

    signal_a = _seed_signal(db_session, strategy_name="momentum", symbol="AAA")
    signal_b = _seed_signal(db_session, strategy_name="momentum", symbol="BBB")
    signal_c = _seed_signal(db_session, strategy_name="momentum", symbol="CCC")
    _seed_signal(db_session, strategy_name="breakout", symbol="DDD")

    decision_service = DecisionService(db_session)
    position_service = PositionService(db_session)
    feedback_service = FeedbackService(db_session)

    decision_service.record_decision(user_id=jake.id, signal_id=signal_a.id, decision=DecisionType.OPEN)
    position_a = position_service.open_position(user=jake, signal=signal_a)
    position_a = position_service.close_position(position_a, close_price=Decimal("120.00"), status=PositionStatus.CLOSED_TARGET)
    feedback_service.record_trade_result(position=position_a, signal=signal_a)

    decision_service.record_decision(user_id=jake.id, signal_id=signal_b.id, decision=DecisionType.OPEN)
    position_b = position_service.open_position(user=jake, signal=signal_b)
    position_b = position_service.close_position(position_b, close_price=Decimal("90.00"), status=PositionStatus.CLOSED_STOP)
    feedback_service.record_trade_result(position=position_b, signal=signal_b)

    decision_service.record_decision(user_id=friend.id, signal_id=signal_c.id, decision=DecisionType.IGNORE)

    performance = feedback_service.get_performance_by_strategy()
    by_name = {p.strategy_name: p for p in performance}

    momentum = by_name["momentum"]
    assert momentum.signals_generated == 3
    assert momentum.accepted == 2  # signal_a and signal_b each OPENed once
    assert momentum.ignored == 1
    assert momentum.trades_closed == 2
    assert momentum.wins == 1
    assert momentum.win_rate == Decimal("50.0")
    assert momentum.average_r_multiple == Decimal("0.50")

    breakout = by_name["breakout"]
    assert breakout.signals_generated == 1
    assert breakout.accepted == 0
    assert breakout.ignored == 0
    assert breakout.trades_closed == 0
    assert breakout.win_rate is None
    assert breakout.average_r_multiple is None


def test_performance_by_strategy_returns_empty_list_with_no_data(db_session: Session) -> None:
    assert FeedbackService(db_session).get_performance_by_strategy() == []
