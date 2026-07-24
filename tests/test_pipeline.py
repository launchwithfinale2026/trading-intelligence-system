import asyncio
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import MarketDataError
from app.domain.enums import AlertPreference, RiskPreference, TradingStyle
from app.engine.pipeline import run_scan_cycle
from app.market.provider import MarketDataProvider, MarketStatus, PricePoint
from app.services.user_service import UserService
from app.services.watchlist_service import WatchlistService
from app.strategies.momentum import MomentumStrategy


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


class FakeProvider(MarketDataProvider):
    """Single-symbol ('NVDA') fake tuned to pass both the scanner's quality
    filters and the momentum strategy's conditions, so the pipeline has a
    real signal to work with end-to-end.
    """

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
        raise NotImplementedError("not needed for pipeline tests")


def _seed_user(
    db_session: Session,
    *,
    username: str,
    telegram_id: int | None,
    alert_preference: AlertPreference,
    account_size: Decimal = Decimal("100000.00"),
    risk_preference: RiskPreference = RiskPreference.AGGRESSIVE,
):
    user = UserService(db_session).create_user(
        username=username,
        email=f"{username}@example.com",
        password_hash="not-a-real-hash",
        account_size=account_size,
        risk_preference=risk_preference,
        trading_style=TradingStyle.MOMENTUM,
        alert_preference=alert_preference,
    )
    if telegram_id is not None:
        user.telegram_id = telegram_id
        db_session.commit()
    return user


@pytest.fixture
def fake_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


def _run(db_session: Session, bot, users_are_seeded_before_call=True, universe=None):
    return asyncio.run(
        run_scan_cycle(
            bot,
            provider=FakeProvider(),
            strategies=[MomentumStrategy()],
            universe=universe or ["NVDA"],
            db=db_session,
        )
    )


def test_pipeline_alerts_linked_user_who_wants_all_signals(db_session: Session, fake_bot) -> None:
    _seed_user(db_session, username="jake", telegram_id=111, alert_preference=AlertPreference.ALL_SIGNALS)

    signals_produced = _run(db_session, fake_bot)

    assert signals_produced == 1
    fake_bot.send_message.assert_awaited_once()
    kwargs = fake_bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == 111
    assert "NVDA" in kwargs["text"]


def test_pipeline_skips_user_with_no_linked_telegram_account(db_session: Session, fake_bot) -> None:
    _seed_user(db_session, username="jake", telegram_id=None, alert_preference=AlertPreference.ALL_SIGNALS)

    signals_produced = _run(db_session, fake_bot)

    assert signals_produced == 1  # the signal is still recorded
    fake_bot.send_message.assert_not_awaited()  # but nobody could be alerted


def test_pipeline_skips_user_who_opted_out_of_alerts(db_session: Session, fake_bot) -> None:
    _seed_user(db_session, username="jake", telegram_id=111, alert_preference=AlertPreference.NONE)

    _run(db_session, fake_bot)

    fake_bot.send_message.assert_not_awaited()


def test_pipeline_alerts_high_confidence_only_user_for_a_qualifying_signal(db_session: Session, fake_bot) -> None:
    _seed_user(db_session, username="jake", telegram_id=111, alert_preference=AlertPreference.HIGH_CONFIDENCE_ONLY)

    _run(db_session, fake_bot)

    # The fixture's momentum burst is strong enough to clear the 75 threshold.
    fake_bot.send_message.assert_awaited_once()


def test_pipeline_skips_user_whose_risk_budget_affords_zero_shares(db_session: Session, fake_bot) -> None:
    _seed_user(
        db_session,
        username="jake",
        telegram_id=111,
        alert_preference=AlertPreference.ALL_SIGNALS,
        account_size=Decimal("10.00"),  # 2% of $10 = $0.20 budget, entry ~$115 -> 0 shares
    )

    _run(db_session, fake_bot)

    fake_bot.send_message.assert_not_awaited()


def test_pipeline_alerts_multiple_interested_users_independently(db_session: Session, fake_bot) -> None:
    _seed_user(db_session, username="jake", telegram_id=111, alert_preference=AlertPreference.ALL_SIGNALS)
    _seed_user(db_session, username="friend", telegram_id=222, alert_preference=AlertPreference.ALL_SIGNALS)

    _run(db_session, fake_bot)

    assert fake_bot.send_message.await_count == 2
    chat_ids = {call.kwargs["chat_id"] for call in fake_bot.send_message.await_args_list}
    assert chat_ids == {111, 222}


def test_pipeline_returns_zero_when_no_symbols_qualify(db_session: Session, fake_bot) -> None:
    _seed_user(db_session, username="jake", telegram_id=111, alert_preference=AlertPreference.ALL_SIGNALS)

    signals_produced = _run(db_session, fake_bot, universe=["GHOST"])  # not in FakeProvider's known symbols

    assert signals_produced == 0
    fake_bot.send_message.assert_not_awaited()


def test_pipeline_alerts_user_with_empty_watchlist_for_any_scanned_symbol(db_session: Session, fake_bot) -> None:
    # No watchlist customization -> watches everything scanned, same as before watchlists existed.
    _seed_user(db_session, username="jake", telegram_id=111, alert_preference=AlertPreference.ALL_SIGNALS)

    _run(db_session, fake_bot)

    fake_bot.send_message.assert_awaited_once()


def test_pipeline_only_alerts_user_for_symbols_on_their_watchlist(db_session: Session, fake_bot) -> None:
    user = _seed_user(db_session, username="jake", telegram_id=111, alert_preference=AlertPreference.ALL_SIGNALS)
    WatchlistService(db_session).add_symbol(user.id, "TSLA")  # not NVDA, the symbol that will qualify

    _run(db_session, fake_bot)

    fake_bot.send_message.assert_not_awaited()


def test_pipeline_alerts_user_whose_watchlist_includes_the_qualifying_symbol(db_session: Session, fake_bot) -> None:
    user = _seed_user(db_session, username="jake", telegram_id=111, alert_preference=AlertPreference.ALL_SIGNALS)
    WatchlistService(db_session).add_symbol(user.id, "NVDA")

    _run(db_session, fake_bot)

    fake_bot.send_message.assert_awaited_once()
