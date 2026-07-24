"""Ties the scanner, strategies, risk engine, and Telegram alerts into one
end-to-end cycle: scan the universe -> evaluate strategies -> persist any
signal produced -> size it per interested user -> alert them.

Not run automatically — see core.config.Settings.enable_scheduled_scanning.
Automatically messaging real people is a product decision for a human to
switch on deliberately, not something that should start happening the
moment this code merges.
"""

import logging

from sqlalchemy.orm import Session
from telegram import Bot

from app.core.config import get_settings
from app.core.exceptions import MarketDataError
from app.database.database import SessionLocal
from app.database.models.user import User
from app.domain.enums import AlertPreference
from app.market.factory import get_market_data_provider
from app.market.provider import MarketDataProvider
from app.market.scanner import Scanner
from app.market.universe import DEFAULT_UNIVERSE
from app.repositories.signal_repository import SignalRepository
from app.repositories.telegram_event_repository import TelegramEventRepository
from app.repositories.user_repository import UserRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.feedback_service import FeedbackService
from app.services.position_service import PositionService
from app.services.risk_policy_service import RiskPolicyService
from app.services.signal_service import SignalService
from app.strategies.base import Signal as StrategySignal
from app.strategies.base import Strategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.momentum import MomentumStrategy
from app.strategies.momentum_breakout import MomentumBreakoutStrategy
from app.telegram.alerts import send_alert, send_position_closed_alert

logger = logging.getLogger(__name__)

_HIGH_CONFIDENCE_THRESHOLD = 75
_HISTORY_PERIOD = "6mo"

DEFAULT_STRATEGIES: list[Strategy] = [MomentumStrategy(), BreakoutStrategy(), MomentumBreakoutStrategy()]


def _should_alert(preference: AlertPreference, confidence: int) -> bool:
    if preference == AlertPreference.NONE:
        return False
    if preference == AlertPreference.HIGH_CONFIDENCE_ONLY:
        return confidence >= _HIGH_CONFIDENCE_THRESHOLD
    return True  # ALL_SIGNALS


def _is_watching(watchlist: set[str], symbol: str) -> bool:
    """A user with no custom watchlist watches everything scanned (the
    system default universe) — customizing a watchlist is opt-in, not a
    prerequisite for getting alerted at all.
    """
    return not watchlist or symbol in watchlist


async def _alert_interested_users(
    bot: Bot,
    db: Session,
    users: list[User],
    watchlists: dict[int, set[str]],
    strategy_signal: StrategySignal,
) -> None:
    persisted = SignalService(db).record_signal(strategy_signal)

    for user in users:
        if user.telegram_id is None or user.profile is None:
            continue
        if not _is_watching(watchlists.get(user.id, set()), persisted.symbol):
            continue
        if not _should_alert(user.profile.alert_preference, persisted.confidence):
            continue

        position_size = RiskPolicyService(db).size_position(
            account_size=user.profile.account_size,
            risk_preference=user.profile.risk_preference,
            entry=persisted.entry,
            stop_loss=persisted.stop_loss,
        )
        if position_size.shares <= 0:
            logger.info("skipping alert to user %s: risk budget affords 0 shares", user.id)
            continue

        sent = await send_alert(bot, user, persisted, position_size)
        if sent:
            TelegramEventRepository(db).log(kind="alert", chat_id=user.telegram_id, text=f"signal {persisted.id}")
            db.commit()


async def run_scan_cycle(
    bot: Bot,
    *,
    provider: MarketDataProvider | None = None,
    strategies: list[Strategy] | None = None,
    universe: list[str] | None = None,
    db: Session | None = None,
) -> int:
    """Runs one full scan/alert cycle. Returns the number of signals
    produced (for logging/monitoring), regardless of how many users were
    actually alerted.

    When universe isn't passed explicitly, it's the system default universe
    plus every user's custom watchlist symbols unioned in — so a user can
    watch a symbol outside the default universe and still get scanned for
    it. Callers that pass universe explicitly (e.g. tests) get exactly that
    set scanned, no watchlist expansion.
    """
    provider = provider or get_market_data_provider()
    strategies = strategies if strategies is not None else DEFAULT_STRATEGIES
    owns_session = db is None
    db = db or SessionLocal()

    signals_produced = 0
    try:
        users = UserRepository(db).list()
        watchlists: dict[int, set[str]] = {
            user.id: {w.symbol for w in WatchlistRepository(db).list_for_user(user.id)} for user in users
        }

        if universe is None:
            universe = list(dict.fromkeys([*DEFAULT_UNIVERSE, *WatchlistRepository(db).list_all_distinct_symbols()]))

        scanner = Scanner(provider)
        ranked = scanner.scan(universe)

        for candidate in ranked:
            try:
                history = provider.get_history(candidate.symbol, period=_HISTORY_PERIOD)
            except MarketDataError as exc:
                logger.warning("skipping %s: %s", candidate.symbol, exc)
                continue

            for strategy in strategies:
                strategy_signal = strategy.evaluate(candidate.symbol, history)
                if strategy_signal is None:
                    continue
                await _alert_interested_users(bot, db, users, watchlists, strategy_signal)
                signals_produced += 1

        return signals_produced
    finally:
        if owns_session:
            db.close()


def run_scan_cycle_sync() -> int:
    """Sync entrypoint for the (thread-based) Scheduler, which cannot await
    a coroutine directly. Creates its own event loop and Bot instance.
    """
    import asyncio

    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning("scan cycle skipped: TELEGRAM_BOT_TOKEN is not set")
        return 0

    bot = Bot(token=settings.telegram_bot_token)
    return asyncio.run(run_scan_cycle(bot))


async def run_position_monitor_cycle(
    bot: Bot,
    *,
    provider: MarketDataProvider | None = None,
    db: Session | None = None,
) -> int:
    """Checks every open position against current prices and closes (+
    alerts) any that have hit their stop or target. Returns the number of
    positions closed this cycle.
    """
    provider = provider or get_market_data_provider()
    owns_session = db is None
    db = db or SessionLocal()

    try:
        closed_positions = PositionService(db).check_and_close_open_positions(provider)

        for position in closed_positions:
            user = UserRepository(db).get(position.user_id)
            signal = SignalRepository(db).get(position.signal_id)
            if user is None or signal is None:
                logger.warning("closed position %s missing user or signal for alerting", position.id)
                continue

            FeedbackService(db).record_trade_result(position=position, signal=signal)
            sent = await send_position_closed_alert(bot, user, position, signal)
            if sent:
                TelegramEventRepository(db).log(
                    kind="position_closed", chat_id=user.telegram_id, text=f"position {position.id}"
                )
                db.commit()

        return len(closed_positions)
    finally:
        if owns_session:
            db.close()


def run_position_monitor_cycle_sync() -> int:
    import asyncio

    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning("position monitor cycle skipped: TELEGRAM_BOT_TOKEN is not set")
        return 0

    bot = Bot(token=settings.telegram_bot_token)
    return asyncio.run(run_position_monitor_cycle(bot))
