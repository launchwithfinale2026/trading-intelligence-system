from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, MarketDataError, RiskLimitError
from app.domain.enums import (
    AlertPreference,
    PositionStatus,
    RiskPreference,
    SignalDirection,
    TradingStyle,
)
from app.market.provider import MarketDataProvider, MarketStatus
from app.services.position_service import PositionService
from app.services.signal_service import SignalService
from app.services.user_service import UserService
from app.strategies.base import Signal as StrategySignal


def _seed_user(db_session: Session, account_size: Decimal = Decimal("100000.00")):
    return UserService(db_session).create_user(
        username="jake",
        email="jake@example.com",
        password_hash="not-a-real-hash",
        account_size=account_size,
        risk_preference=RiskPreference.AGGRESSIVE,
        trading_style=TradingStyle.MOMENTUM,
        alert_preference=AlertPreference.ALL_SIGNALS,
    )


def _seed_signal(db_session: Session, *, symbol: str = "NVDA", direction: SignalDirection = SignalDirection.LONG):
    return SignalService(db_session).record_signal(
        StrategySignal(
            symbol=symbol,
            direction=direction,
            entry=Decimal("100.00"),
            stop_loss=Decimal("90.00"),
            target=Decimal("120.00"),
            confidence=80,
            reasoning=["fixture"],
            strategy_name="momentum",
        )
    )


class FakePriceProvider(MarketDataProvider):
    def __init__(self, prices: dict[str, Decimal]) -> None:
        self.prices = prices

    def get_price(self, symbol):
        if symbol not in self.prices:
            raise MarketDataError(f"no price for {symbol}")
        return self.prices[symbol]

    def get_volume(self, symbol):
        raise NotImplementedError

    def get_market_cap(self, symbol):
        raise NotImplementedError

    def get_history(self, symbol, *, period="3mo", interval="1d"):
        raise NotImplementedError

    def get_market_status(self) -> MarketStatus:
        raise NotImplementedError


def test_open_position_sizes_from_current_profile(db_session: Session) -> None:
    user = _seed_user(db_session)
    signal = _seed_signal(db_session)

    position = PositionService(db_session).open_position(user=user, signal=signal)

    assert position.shares > 0
    assert position.entry == signal.entry
    assert position.stop_loss == signal.stop_loss
    assert position.target == signal.target
    assert position.status == PositionStatus.OPEN


def test_open_position_rejects_duplicate_for_same_user_and_signal(db_session: Session) -> None:
    user = _seed_user(db_session)
    signal = _seed_signal(db_session)
    service = PositionService(db_session)
    service.open_position(user=user, signal=signal)

    with pytest.raises(ConflictError):
        service.open_position(user=user, signal=signal)


def test_open_position_rejects_when_risk_budget_affords_zero_shares(db_session: Session) -> None:
    user = _seed_user(db_session, account_size=Decimal("1.00"))
    signal = _seed_signal(db_session)

    with pytest.raises(RiskLimitError):
        PositionService(db_session).open_position(user=user, signal=signal)


def test_check_and_close_closes_long_position_on_stop_hit(db_session: Session) -> None:
    user = _seed_user(db_session)
    signal = _seed_signal(db_session)
    service = PositionService(db_session)
    position = service.open_position(user=user, signal=signal)

    closed = service.check_and_close_open_positions(FakePriceProvider({"NVDA": Decimal("89.00")}))

    assert len(closed) == 1
    assert closed[0].id == position.id
    assert closed[0].status == PositionStatus.CLOSED_STOP
    assert closed[0].close_price == Decimal("89.00")
    assert closed[0].closed_at is not None


def test_check_and_close_closes_long_position_on_target_hit(db_session: Session) -> None:
    user = _seed_user(db_session)
    signal = _seed_signal(db_session)
    service = PositionService(db_session)
    service.open_position(user=user, signal=signal)

    closed = service.check_and_close_open_positions(FakePriceProvider({"NVDA": Decimal("121.00")}))

    assert closed[0].status == PositionStatus.CLOSED_TARGET


def test_check_and_close_leaves_position_open_between_stop_and_target(db_session: Session) -> None:
    user = _seed_user(db_session)
    signal = _seed_signal(db_session)
    service = PositionService(db_session)
    service.open_position(user=user, signal=signal)

    closed = service.check_and_close_open_positions(FakePriceProvider({"NVDA": Decimal("105.00")}))

    assert closed == []


def test_evaluate_close_short_position_stop_and_target() -> None:
    from app.database.models.position import Position

    position = Position(entry=Decimal("100"), stop_loss=Decimal("110"), target=Decimal("80"), shares=10)

    assert PositionService._evaluate_close(position, SignalDirection.SHORT, Decimal("111")) == PositionStatus.CLOSED_STOP
    assert PositionService._evaluate_close(position, SignalDirection.SHORT, Decimal("79")) == PositionStatus.CLOSED_TARGET
    assert PositionService._evaluate_close(position, SignalDirection.SHORT, Decimal("95")) is None


def test_check_and_close_skips_symbol_with_unavailable_price(db_session: Session) -> None:
    user = _seed_user(db_session)
    signal = _seed_signal(db_session)
    service = PositionService(db_session)
    service.open_position(user=user, signal=signal)

    closed = service.check_and_close_open_positions(FakePriceProvider({}))  # no price for NVDA

    assert closed == []
