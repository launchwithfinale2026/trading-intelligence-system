import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import Base
from app.domain.enums import RiskPreference, SignalDirection, TradingStyle
from app.services.signal_service import SignalService
from app.services.user_service import UserService
from app.strategies.base import Signal as StrategySignal
from app.telegram import handlers


@pytest.fixture
def bot_session_factory(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(handlers, "SessionLocal", session_factory)
    yield session_factory
    engine.dispose()


def _fake_update(telegram_user_id: int | None = 12345):
    message = SimpleNamespace(reply_text=AsyncMock())
    effective_user = SimpleNamespace(id=telegram_user_id) if telegram_user_id is not None else None
    return SimpleNamespace(message=message, effective_user=effective_user)


def _fake_context(args: list[str] | None = None):
    return SimpleNamespace(args=args or [])


def _fake_reply_update(telegram_user_id: int, text: str, parent_text: str | None):
    parent = SimpleNamespace(text=parent_text) if parent_text is not None else None
    message = SimpleNamespace(reply_text=AsyncMock(), text=text, reply_to_message=parent)
    return SimpleNamespace(message=message, effective_user=SimpleNamespace(id=telegram_user_id))


def _seed_user(session_factory, *, telegram_id: int | None = None) -> int:
    db = session_factory()
    try:
        user = UserService(db).create_user(
            username="jake",
            email="jake@example.com",
            password_hash="not-a-real-hash",
            account_size=Decimal("1000.00"),
            risk_preference=RiskPreference.AGGRESSIVE,
            trading_style=TradingStyle.MOMENTUM,
        )
        if telegram_id is not None:
            user.telegram_id = telegram_id
            db.commit()
        return user.id
    finally:
        db.close()


def _seed_signal(session_factory) -> int:
    db = session_factory()
    try:
        signal = SignalService(db).record_signal(
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
    finally:
        db.close()


def test_start_links_account_for_known_username(bot_session_factory) -> None:
    _seed_user(bot_session_factory)
    update = _fake_update(telegram_user_id=999)

    asyncio.run(handlers.start(update, _fake_context(["jake"])))

    update.message.reply_text.assert_awaited_once()
    assert "Linked" in update.message.reply_text.call_args[0][0]

    db = bot_session_factory()
    try:
        from app.repositories.user_repository import UserRepository

        user = UserRepository(db).get_by_telegram_id(999)
        assert user is not None
        assert user.username == "jake"
    finally:
        db.close()


def test_start_rejects_unknown_username(bot_session_factory) -> None:
    update = _fake_update()

    asyncio.run(handlers.start(update, _fake_context(["ghost"])))

    assert "No account found" in update.message.reply_text.call_args[0][0]


def test_start_without_args_shows_usage(bot_session_factory) -> None:
    update = _fake_update()

    asyncio.run(handlers.start(update, _fake_context([])))

    assert "Usage" in update.message.reply_text.call_args[0][0]


def test_start_rejects_relinking_to_a_different_telegram_user(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=111)
    update = _fake_update(telegram_user_id=222)  # a different Telegram account

    asyncio.run(handlers.start(update, _fake_context(["jake"])))

    assert "already linked to a different" in update.message.reply_text.call_args[0][0]


def test_profile_returns_profile_for_linked_user(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    update = _fake_update(telegram_user_id=12345)

    asyncio.run(handlers.profile(update, _fake_context()))

    reply = update.message.reply_text.call_args[0][0]
    assert "aggressive" in reply
    assert "momentum" in reply


def test_profile_for_unlinked_user_is_handled_gracefully(bot_session_factory) -> None:
    update = _fake_update(telegram_user_id=999999)

    asyncio.run(handlers.profile(update, _fake_context()))

    assert "isn't linked" in update.message.reply_text.call_args[0][0]


def test_positions_reports_none_for_linked_user(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    update = _fake_update(telegram_user_id=12345)

    asyncio.run(handlers.positions(update, _fake_context()))

    assert "no active positions" in update.message.reply_text.call_args[0][0]


def test_status_replies_with_market_state(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    update = _fake_update(telegram_user_id=12345)

    asyncio.run(handlers.status(update, _fake_context()))

    assert "Market is" in update.message.reply_text.call_args[0][0]


def test_open_records_decision_for_known_signal(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    signal_id = _seed_signal(bot_session_factory)
    update = _fake_update(telegram_user_id=12345)

    asyncio.run(handlers.open_command(update, _fake_context([str(signal_id)])))

    assert f"Recorded: OPEN on signal {signal_id}" in update.message.reply_text.call_args[0][0]


def test_open_creates_a_real_position_reflected_in_positions_command(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    signal_id = _seed_signal(bot_session_factory)
    update = _fake_update(telegram_user_id=12345)

    asyncio.run(handlers.open_command(update, _fake_context([str(signal_id)])))
    assert "Position opened" in update.message.reply_text.call_args[0][0]

    positions_update = _fake_update(telegram_user_id=12345)
    asyncio.run(handlers.positions(positions_update, _fake_context()))

    reply = positions_update.message.reply_text.call_args[0][0]
    assert "NVDA" in reply
    assert "no active positions" not in reply


def test_ignore_does_not_create_a_position(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    signal_id = _seed_signal(bot_session_factory)
    update = _fake_update(telegram_user_id=12345)

    asyncio.run(handlers.ignore_command(update, _fake_context([str(signal_id)])))

    positions_update = _fake_update(telegram_user_id=12345)
    asyncio.run(handlers.positions(positions_update, _fake_context()))
    assert "no active positions" in positions_update.message.reply_text.call_args[0][0]


def test_ignore_after_open_on_same_signal_is_a_conflict(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    signal_id = _seed_signal(bot_session_factory)
    update = _fake_update(telegram_user_id=12345)

    asyncio.run(handlers.open_command(update, _fake_context([str(signal_id)])))
    asyncio.run(handlers.ignore_command(update, _fake_context([str(signal_id)])))

    assert "already recorded" in update.message.reply_text.call_args[0][0]


def test_open_for_unknown_signal_is_handled_gracefully(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    update = _fake_update(telegram_user_id=12345)

    asyncio.run(handlers.open_command(update, _fake_context(["999"])))

    assert "No signal found" in update.message.reply_text.call_args[0][0]


def test_open_with_non_numeric_signal_id_is_handled_gracefully(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    update = _fake_update(telegram_user_id=12345)

    asyncio.run(handlers.open_command(update, _fake_context(["not-a-number"])))

    assert "must be a number" in update.message.reply_text.call_args[0][0]


def test_open_for_unlinked_telegram_user_is_handled_gracefully(bot_session_factory) -> None:
    signal_id = _seed_signal(bot_session_factory)
    update = _fake_update(telegram_user_id=555)

    asyncio.run(handlers.open_command(update, _fake_context([str(signal_id)])))

    assert "isn't linked" in update.message.reply_text.call_args[0][0]


def test_text_reply_open_records_decision(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    signal_id = _seed_signal(bot_session_factory)
    update = _fake_reply_update(12345, "OPEN", f"...\nSignal ID: {signal_id}")

    asyncio.run(handlers.handle_text_reply(update, _fake_context()))

    assert f"Recorded: OPEN on signal {signal_id}" in update.message.reply_text.call_args[0][0]


def test_text_reply_ignore_records_decision_case_insensitively(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    signal_id = _seed_signal(bot_session_factory)
    update = _fake_reply_update(12345, "  ignore  ", f"...\nSignal ID: {signal_id}")

    asyncio.run(handlers.handle_text_reply(update, _fake_context()))

    assert f"Recorded: IGNORE on signal {signal_id}" in update.message.reply_text.call_args[0][0]


def test_text_reply_ignores_unrelated_text(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    signal_id = _seed_signal(bot_session_factory)
    update = _fake_reply_update(12345, "sounds good thanks", f"...\nSignal ID: {signal_id}")

    asyncio.run(handlers.handle_text_reply(update, _fake_context()))

    update.message.reply_text.assert_not_called()


def test_text_reply_ignores_when_parent_has_no_signal_id(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    update = _fake_reply_update(12345, "OPEN", "just a regular message")

    asyncio.run(handlers.handle_text_reply(update, _fake_context()))

    update.message.reply_text.assert_not_called()


def test_text_reply_ignores_messages_that_are_not_replies(bot_session_factory) -> None:
    _seed_user(bot_session_factory, telegram_id=12345)
    update = _fake_reply_update(12345, "OPEN", None)

    asyncio.run(handlers.handle_text_reply(update, _fake_context()))

    update.message.reply_text.assert_not_called()
