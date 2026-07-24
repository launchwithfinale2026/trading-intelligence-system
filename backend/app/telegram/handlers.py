"""Telegram command handlers.

Runs as a separate process from the FastAPI app (see bot.py), so handlers
open their own DB session per update rather than using FastAPI's
request-scoped Depends(get_db). `SessionLocal` is imported as a module
attribute (not called at import time) so tests can monkeypatch
`app.telegram.handlers.SessionLocal` to point at an isolated test database.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, RiskLimitError
from app.database.database import SessionLocal
from app.database.models.signal import Signal
from app.database.models.user import User
from app.domain.enums import DecisionType
from app.market.factory import get_market_data_provider
from app.market.universe import DEFAULT_UNIVERSE
from app.repositories.position_repository import PositionRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.telegram_contact_repository import TelegramContactRepository
from app.repositories.telegram_event_repository import TelegramEventRepository
from app.repositories.user_repository import UserRepository
from app.services.decision_service import DecisionService
from app.services.position_service import PositionService
from app.telegram.alerts import extract_signal_id

logger = logging.getLogger(__name__)

_NOT_LINKED_MESSAGE = "This Telegram account isn't linked to a Trading Intelligence System user yet. Send /start <your username> to link it."
_ONLINE_MESSAGE = "Trading Intelligence System is online."
_HELP_MESSAGE = (
    "Available commands:\n"
    "/start <username> - link this chat to your dashboard account\n"
    "/status - backend, scanner, and market status\n"
    "/ping - check the bot is responsive\n"
    "/profile - your risk profile\n"
    "/positions - your open positions\n"
    "/open <signal_id> - open a position from a signal\n"
    "/ignore <signal_id> - ignore a signal\n"
    "/help - show this message"
)

# Process start time, used for the "bot uptime" line in /status. Set at
# import time — this module is only ever imported once per bot process.
_START_TIME = datetime.now(timezone.utc)


def _capture_contact(db, update: Update) -> None:
    """Automatically records/refreshes whoever just messaged the bot,
    independent of whether they have (or ever link) a dashboard account.
    """
    user = update.effective_user
    if user is None:
        return

    chat = getattr(update, "effective_chat", None)
    chat_id = getattr(chat, "id", None)
    if chat_id is None:
        chat_id = user.id  # private chats: chat id == user id

    TelegramContactRepository(db).upsert(
        telegram_id=user.id,
        chat_id=chat_id,
        username=getattr(user, "username", None),
        first_name=getattr(user, "first_name", None),
    )
    db.commit()


def _resolve_user(db, update: Update) -> User | None:
    if update.effective_user is None:
        return None
    return UserRepository(db).get_by_telegram_id(update.effective_user.id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        _capture_contact(db, update)

        if not context.args:
            await update.message.reply_text(f"{_ONLINE_MESSAGE}\n\nUsage: /start <username>")
            return

        username = context.args[0]
        telegram_id = update.effective_user.id

        user = UserRepository(db).get_by_username(username)
        if user is None:
            await update.message.reply_text(
                f"{_ONLINE_MESSAGE}\n\nNo account found for username {username!r}. Register on the dashboard first."
            )
            return

        if user.telegram_id == telegram_id:
            await update.message.reply_text(f"{_ONLINE_MESSAGE}\n\nAlready linked. Welcome back, {username}.")
            return

        if user.telegram_id is not None:
            await update.message.reply_text(f"{_ONLINE_MESSAGE}\n\nThis account is already linked to a different Telegram user.")
            return

        user.telegram_id = telegram_id
        db.commit()
        await update.message.reply_text(f"{_ONLINE_MESSAGE}\n\nLinked! Welcome, {username}.")
    finally:
        db.close()


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        user = _resolve_user(db, update)
        if user is None:
            await update.message.reply_text(_NOT_LINKED_MESSAGE)
            return

        p = user.profile
        await update.message.reply_text(
            "Profile\n"
            f"Account size: ${p.account_size}\n"
            f"Risk preference: {p.risk_preference.value}\n"
            f"Trading style: {p.trading_style.value}\n"
            f"Alert preference: {p.alert_preference.value}"
        )
    finally:
        db.close()


def _format_uptime(delta) -> str:
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        if _resolve_user(db, update) is None:
            await update.message.reply_text(_NOT_LINKED_MESSAGE)
            return

        try:
            db.execute(select(1))
            db_status = "connected"
        except Exception:
            db_status = "error"

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        signals_today = (
            db.scalar(select(func.count()).select_from(Signal).where(Signal.created_at >= today_start)) or 0
        )
        alerts_today = TelegramEventRepository(db).count_since(kind="alert", since=today_start)
        last_scan = db.scalar(select(func.max(Signal.created_at)))
    finally:
        db.close()

    market_status = get_market_data_provider().get_market_status()
    market_state = "OPEN" if market_status.is_open else "CLOSED"
    scanner_state = "enabled" if get_settings().enable_scheduled_scanning else "manual only"
    last_scan_text = f"{last_scan:%Y-%m-%d %H:%M} UTC" if last_scan else "never"

    await update.message.reply_text(
        "System Status\n"
        "Backend: online\n"
        f"Scanner: {scanner_state} (last scan: {last_scan_text})\n"
        f"Database: {db_status}\n"
        f"Watchlist size: {len(DEFAULT_UNIVERSE)}\n"
        f"Signals generated today: {signals_today}\n"
        f"Alerts sent today: {alerts_today}\n"
        f"Bot uptime: {_format_uptime(datetime.now(timezone.utc) - _START_TIME)}\n"
        f"Market is {market_state} (as of {market_status.as_of:%Y-%m-%d %H:%M %Z})"
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sent_at = getattr(update.message, "date", None)
    if sent_at is not None:
        latency_ms = (datetime.now(timezone.utc) - sent_at).total_seconds() * 1000
        await update.message.reply_text(f"PONG ({latency_ms:.0f} ms)")
    else:
        await update.message.reply_text("PONG")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(_HELP_MESSAGE)


async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        user = _resolve_user(db, update)
        if user is None:
            await update.message.reply_text(_NOT_LINKED_MESSAGE)
            return

        open_positions = PositionRepository(db).list_open_for_user(user.id)
        if not open_positions:
            await update.message.reply_text("You have no active positions.")
            return

        lines = ["Active positions:"]
        for position in open_positions:
            signal = SignalRepository(db).get(position.signal_id)
            symbol = signal.symbol if signal else f"signal {position.signal_id}"
            lines.append(f"- {symbol}: {position.shares} shares @ {position.entry} (stop {position.stop_loss}, target {position.target})")
        await update.message.reply_text("\n".join(lines))
    finally:
        db.close()


async def _record_decision_and_reply(update: Update, decision_type: DecisionType, signal_id: int) -> None:
    """Shared by the /open,/ignore commands and the plain-text reply
    handler — both ultimately do the same thing: resolve the user, record
    the decision, tell them what happened.
    """
    command = decision_type.value.upper()
    db = SessionLocal()
    try:
        user = _resolve_user(db, update)
        if user is None:
            await update.message.reply_text(_NOT_LINKED_MESSAGE)
            return

        try:
            DecisionService(db).record_decision(user_id=user.id, signal_id=signal_id, decision=decision_type)
        except NotFoundError:
            await update.message.reply_text(f"No signal found with id {signal_id}.")
            return
        except ConflictError as exc:
            await update.message.reply_text(str(exc))
            return

        if decision_type != DecisionType.OPEN:
            await update.message.reply_text(f"Recorded: {command} on signal {signal_id}.")
            return

        signal = SignalRepository(db).get(signal_id)
        try:
            position = PositionService(db).open_position(user=user, signal=signal)
        except RiskLimitError as exc:
            await update.message.reply_text(f"Recorded: OPEN on signal {signal_id}. But no position was opened: {exc}")
            return

        await update.message.reply_text(
            f"Recorded: OPEN on signal {signal_id}. Position opened: {position.shares} shares @ {position.entry}."
        )
    finally:
        db.close()


async def _decide(update: Update, context: ContextTypes.DEFAULT_TYPE, decision_type: DecisionType) -> None:
    if not context.args:
        await update.message.reply_text(f"Usage: /{decision_type.value} <signal_id>")
        return

    try:
        signal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("signal_id must be a number.")
        return

    await _record_decision_and_reply(update, decision_type, signal_id)


async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _decide(update, context, DecisionType.OPEN)


async def ignore_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _decide(update, context, DecisionType.IGNORE)


_TEXT_TO_DECISION = {"open": DecisionType.OPEN, "ignore": DecisionType.IGNORE}


async def handle_text_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles a bare "OPEN"/"IGNORE" sent as a reply to an alert message
    (the UX the alert text asks for), as opposed to the explicit
    /open <id> / /ignore <id> commands. Silently does nothing for replies
    that aren't OPEN/IGNORE, or whose parent message isn't a recognizable
    alert — this handler shares the update loop with anything else a user
    might type, so it must not respond to unrelated messages.
    """
    if update.message is None or update.message.reply_to_message is None:
        return

    text = (update.message.text or "").strip().lower()
    decision_type = _TEXT_TO_DECISION.get(text)
    if decision_type is None:
        return

    parent_text = update.message.reply_to_message.text or ""
    signal_id = extract_signal_id(parent_text)
    if signal_id is None:
        return  # not a reply to an alert we recognize

    await _record_decision_and_reply(update, decision_type, signal_id)
