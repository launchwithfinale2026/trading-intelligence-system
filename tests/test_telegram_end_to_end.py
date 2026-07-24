"""End-to-end Telegram coverage: not individual handler units (see
test_telegram_handlers.py) but the full wiring — bot construction/token
handling, the real scan→signal→alert pipeline routing to the correct
users, one user's delivery failure not affecting another's, and the full
alert→reply→decision round trip a real user would experience.
"""

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from telegram.error import TelegramError

from app.core.exceptions import MarketDataError
from app.database.models import Base
from app.domain.enums import AlertPreference, RiskPreference, SignalDirection, TradingStyle
from app.engine.pipeline import run_scan_cycle
from app.market.provider import MarketDataProvider, MarketStatus, PricePoint
from app.repositories.telegram_event_repository import TelegramEventRepository
from app.services.signal_service import SignalService
from app.services.user_service import UserService
from app.strategies.base import Signal as StrategySignal
from app.strategies.momentum import MomentumStrategy
from app.telegram import bot, handlers
from app.telegram.alerts import extract_signal_id, format_alert, send_alert, send_message

# ---------------------------------------------------------------------------
# 1. Bot construction / token handling
# ---------------------------------------------------------------------------


def test_build_application_refuses_to_start_without_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot, "get_settings", lambda: SimpleNamespace(telegram_bot_token=None))

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        bot.build_application()


def test_build_application_registers_every_command_with_a_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot, "get_settings", lambda: SimpleNamespace(telegram_bot_token="123456:fake-token-for-test"))

    application = bot.build_application()

    command_names: set[str] = set()
    for group in application.handlers.values():
        for h in group:
            if hasattr(h, "commands"):
                command_names |= set(h.commands)
    assert command_names == {"start", "help", "ping", "profile", "status", "positions", "open", "ignore"}
    assert application.error_handlers  # _on_error is registered


# ---------------------------------------------------------------------------
# 2. Full pipeline: scan -> signal -> alert, routed to the correct users only
# ---------------------------------------------------------------------------


def _qualifying_history() -> list[PricePoint]:
    start = date(2026, 1, 1)
    closes = [100.0] * 50 + [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 115.0]
    volumes = [1_000_000] * 59 + [3_000_000]
    return [
        PricePoint(
            date=start + timedelta(days=i),
            open=Decimal(str(c)),
            high=Decimal(str(c)),
            low=Decimal(str(c)),
            close=Decimal(str(c)),
            volume=v,
        )
        for i, (c, v) in enumerate(zip(closes, volumes, strict=True))
    ]


class _FakeProvider(MarketDataProvider):
    def __init__(self, symbols: list[str] | None = None) -> None:
        self.symbols = symbols or ["NVDA"]

    def get_price(self, symbol: str) -> Decimal:
        if symbol not in self.symbols:
            raise MarketDataError(f"unknown {symbol!r}")
        return Decimal("115.00")

    def get_volume(self, symbol: str) -> int:
        return 3_000_000

    def get_market_cap(self, symbol: str) -> Decimal:
        return Decimal("1000000000000")

    def get_history(self, symbol: str, *, period: str = "3mo", interval: str = "1d") -> list[PricePoint]:
        if symbol not in self.symbols:
            raise MarketDataError(f"unknown {symbol!r}")
        return _qualifying_history()

    def get_market_status(self) -> MarketStatus:
        raise NotImplementedError("not needed for this test")


def _seed_linked_user(db_session, *, username: str, telegram_id: int, alert_preference=AlertPreference.ALL_SIGNALS):
    user = UserService(db_session).create_user(
        username=username,
        email=f"{username}@example.com",
        password_hash="not-a-real-hash",
        account_size=Decimal("100000.00"),
        risk_preference=RiskPreference.AGGRESSIVE,
        trading_style=TradingStyle.MOMENTUM,
        alert_preference=alert_preference,
    )
    user.telegram_id = telegram_id
    db_session.commit()
    return user


def test_pipeline_end_to_end_routes_alert_to_correct_chat_id_only(db_session) -> None:
    _seed_linked_user(db_session, username="jake", telegram_id=111)
    _seed_linked_user(db_session, username="friend", telegram_id=222, alert_preference=AlertPreference.NONE)

    fake_bot = AsyncMock()
    fake_bot.send_message = AsyncMock()

    signals_produced = asyncio.run(
        run_scan_cycle(
            fake_bot,
            provider=_FakeProvider(),
            strategies=[MomentumStrategy()],
            universe=["NVDA"],
            db=db_session,
        )
    )

    assert signals_produced == 1
    fake_bot.send_message.assert_awaited_once()  # only the opted-in user
    kwargs = fake_bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == 111
    assert "NVDA" in kwargs["text"]

    # The outbound alert was logged for status/audit purposes.
    events = TelegramEventRepository(db_session).count_since(kind="alert", since=date(2020, 1, 1))
    assert events == 1


def test_one_users_delivery_failure_does_not_block_another_users_alert(db_session) -> None:
    """No shared state / no shared failure blast radius between users:
    send_alert catches TelegramError per-recipient (see alerts.py), so one
    bad chat_id must never prevent everyone else from being alerted.
    """
    _seed_linked_user(db_session, username="jake", telegram_id=111)
    _seed_linked_user(db_session, username="friend", telegram_id=222)

    fake_bot = AsyncMock()

    async def flaky_send(*, chat_id, text):
        if chat_id == 111:
            raise TelegramError("simulated delivery failure for chat 111")
        return None

    fake_bot.send_message = AsyncMock(side_effect=flaky_send)

    signals_produced = asyncio.run(
        run_scan_cycle(
            fake_bot,
            provider=_FakeProvider(),
            strategies=[MomentumStrategy()],
            universe=["NVDA"],
            db=db_session,
        )
    )

    assert signals_produced == 1
    assert fake_bot.send_message.await_count == 2  # both attempted
    delivered_chat_ids = {
        call.kwargs["chat_id"] for call in fake_bot.send_message.await_args_list
    }
    assert delivered_chat_ids == {111, 222}  # both attempted regardless of outcome

    # Only chat 222's successful send was logged as a delivered alert event.
    db_session.expire_all()
    from app.database.models.telegram_event import TelegramEvent

    logged_chat_ids = {e.chat_id for e in db_session.query(TelegramEvent).filter_by(kind="alert").all()}
    assert logged_chat_ids == {222}


# ---------------------------------------------------------------------------
# 3. send_message / send_alert failure handling in isolation
# ---------------------------------------------------------------------------


async def _send_alert_returns_false_on_telegram_error() -> bool:
    fake_bot = AsyncMock()
    fake_bot.send_message = AsyncMock(side_effect=TelegramError("network blip"))
    return await send_message(fake_bot, chat_id=999, text="hello")


def test_send_message_swallows_telegram_errors_and_reports_failure() -> None:
    result = asyncio.run(_send_alert_returns_false_on_telegram_error())

    assert result is False  # logged, not raised — caller must not crash


# ---------------------------------------------------------------------------
# 4. Full alert -> reply -> decision round trip, exactly as a real user sees it
# ---------------------------------------------------------------------------


@pytest.fixture
def bot_session_factory(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(handlers, "SessionLocal", session_factory)
    yield session_factory
    engine.dispose()


def test_full_alert_text_round_trips_through_a_real_open_reply(bot_session_factory) -> None:
    from app.risk.calculator import PositionSize

    db = bot_session_factory()
    try:
        user = UserService(db).create_user(
            username="jake",
            email="jake@example.com",
            password_hash="not-a-real-hash",
            account_size=Decimal("100000.00"),
            risk_preference=RiskPreference.AGGRESSIVE,
            trading_style=TradingStyle.MOMENTUM,
        )
        user.telegram_id = 111
        db.commit()

        signal = SignalService(db).record_signal(
            StrategySignal(
                symbol="NVDA",
                direction=SignalDirection.LONG,
                entry=Decimal("175.00"),
                stop_loss=Decimal("168.00"),
                target=Decimal("189.00"),
                confidence=82,
                reasoning=["Volume expansion", "Trend confirmation"],
                strategy_name="momentum",
            )
        )
        position_size = PositionSize(
            shares=100, position_value=Decimal("17500.00"), dollar_risk=Decimal("700.00"), risk_percent=Decimal("0.02")
        )
        alert_text = format_alert(signal, position_size)
    finally:
        db.close()

    # Exactly what a user sees, and exactly how they're told to respond.
    assert "Reply OPEN or IGNORE." in alert_text
    assert extract_signal_id(alert_text) == signal.id

    # Simulate the user replying "OPEN" to that exact alert message.
    reply_message = SimpleNamespace(
        reply_text=AsyncMock(), text="OPEN", reply_to_message=SimpleNamespace(text=alert_text)
    )
    reply_update = SimpleNamespace(message=reply_message, effective_user=SimpleNamespace(id=111))

    asyncio.run(handlers.handle_text_reply(reply_update, SimpleNamespace(args=[])))

    reply = reply_message.reply_text.call_args[0][0]
    assert f"Recorded: OPEN on signal {signal.id}" in reply
    assert "Position opened" in reply

    db = bot_session_factory()
    try:
        from app.repositories.position_repository import PositionRepository
        from app.repositories.user_repository import UserRepository

        user = UserRepository(db).get_by_telegram_id(111)
        positions = PositionRepository(db).list_for_user(user.id)
        assert len(positions) == 1
        assert positions[0].shares > 0
    finally:
        db.close()


def test_send_alert_to_unlinked_user_fails_gracefully_without_raising(db_session) -> None:
    from app.database.models.user import User
    from app.risk.calculator import PositionSize

    user = UserService(db_session).create_user(
        username="unlinked",
        email="unlinked@example.com",
        password_hash="not-a-real-hash",
        account_size=Decimal("1000.00"),
        risk_preference=RiskPreference.MODERATE,
        trading_style=TradingStyle.MOMENTUM,
    )
    assert user.telegram_id is None

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
    position_size = PositionSize(
        shares=10, position_value=Decimal("1750.00"), dollar_risk=Decimal("70.00"), risk_percent=Decimal("0.02")
    )

    fake_bot = AsyncMock()
    sent = asyncio.run(send_alert(fake_bot, user, signal, position_size))

    assert sent is False
    fake_bot.send_message.assert_not_awaited()
