import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import MarketDataError
from app.domain.enums import AlertPreference, PositionStatus, RiskPreference, SignalDirection, TradingStyle
from app.engine.pipeline import run_position_monitor_cycle
from app.market.provider import MarketDataProvider, MarketStatus
from app.services.position_service import PositionService
from app.services.signal_service import SignalService
from app.services.user_service import UserService
from app.strategies.base import Signal as StrategySignal


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


def _seed_user_with_open_position(db_session: Session, *, telegram_id: int = 111):
    user = UserService(db_session).create_user(
        username="jake",
        email="jake@example.com",
        password_hash="not-a-real-hash",
        account_size=Decimal("100000.00"),
        risk_preference=RiskPreference.AGGRESSIVE,
        trading_style=TradingStyle.MOMENTUM,
        alert_preference=AlertPreference.ALL_SIGNALS,
    )
    user.telegram_id = telegram_id
    db_session.commit()

    signal = SignalService(db_session).record_signal(
        StrategySignal(
            symbol="NVDA",
            direction=SignalDirection.LONG,
            entry=Decimal("100.00"),
            stop_loss=Decimal("90.00"),
            target=Decimal("120.00"),
            confidence=80,
            reasoning=["fixture"],
            strategy_name="momentum",
        )
    )
    position = PositionService(db_session).open_position(user=user, signal=signal)
    return user, signal, position


@pytest.fixture
def fake_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


def test_monitor_cycle_closes_and_alerts_on_stop_hit(db_session: Session, fake_bot) -> None:
    _seed_user_with_open_position(db_session)

    closed_count = asyncio.run(
        run_position_monitor_cycle(fake_bot, provider=FakePriceProvider({"NVDA": Decimal("89.00")}), db=db_session)
    )

    assert closed_count == 1
    fake_bot.send_message.assert_awaited_once()
    text = fake_bot.send_message.call_args.kwargs["text"]
    assert "STOP LOSS" in text
    assert "NVDA" in text


def test_monitor_cycle_closes_and_alerts_on_target_hit(db_session: Session, fake_bot) -> None:
    _seed_user_with_open_position(db_session)

    closed_count = asyncio.run(
        run_position_monitor_cycle(fake_bot, provider=FakePriceProvider({"NVDA": Decimal("121.00")}), db=db_session)
    )

    assert closed_count == 1
    text = fake_bot.send_message.call_args.kwargs["text"]
    assert "TAKE PROFIT" in text


def test_monitor_cycle_does_nothing_when_price_is_between_stop_and_target(db_session: Session, fake_bot) -> None:
    _seed_user_with_open_position(db_session)

    closed_count = asyncio.run(
        run_position_monitor_cycle(fake_bot, provider=FakePriceProvider({"NVDA": Decimal("105.00")}), db=db_session)
    )

    assert closed_count == 0
    fake_bot.send_message.assert_not_awaited()


def test_monitor_cycle_updates_position_status_in_database(db_session: Session, fake_bot) -> None:
    _, _, position = _seed_user_with_open_position(db_session)

    asyncio.run(
        run_position_monitor_cycle(fake_bot, provider=FakePriceProvider({"NVDA": Decimal("89.00")}), db=db_session)
    )

    db_session.refresh(position)
    assert position.status == PositionStatus.CLOSED_STOP
    assert position.close_price == Decimal("89.00")


def test_monitor_cycle_records_a_trade_result(db_session: Session, fake_bot) -> None:
    from app.repositories.trade_result_repository import TradeResultRepository

    _, _, position = _seed_user_with_open_position(db_session)

    asyncio.run(
        run_position_monitor_cycle(fake_bot, provider=FakePriceProvider({"NVDA": Decimal("89.00")}), db=db_session)
    )

    result = TradeResultRepository(db_session).get_by_position(position.id)
    assert result is not None
    assert result.is_win is False
    assert result.strategy_name == "momentum"
    # entry 100, stop 90 -> $10/share risk; closed at 89 -> -$11/share -> -1.1R
    assert result.r_multiple == Decimal("-1.10")
