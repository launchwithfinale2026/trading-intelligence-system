"""Telegram command handlers.

Runs as a separate process from the FastAPI app (see bot.py), so handlers
open their own DB session per update rather than using FastAPI's
request-scoped Depends(get_db). `SessionLocal` is imported as a module
attribute (not called at import time) so tests can monkeypatch
`app.telegram.handlers.SessionLocal` to point at an isolated test database.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.core.exceptions import ConflictError, NotFoundError
from app.database.database import SessionLocal
from app.database.models.user import User
from app.domain.enums import DecisionType
from app.market.factory import get_market_data_provider
from app.repositories.user_repository import UserRepository
from app.services.decision_service import DecisionService

logger = logging.getLogger(__name__)

_NOT_LINKED_MESSAGE = "This Telegram account isn't linked to a Trading Intelligence System user yet. Send /start <your username> to link it."


def _resolve_user(db, update: Update) -> User | None:
    if update.effective_user is None:
        return None
    return UserRepository(db).get_by_telegram_id(update.effective_user.id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /start <username>")
        return

    username = context.args[0]
    telegram_id = update.effective_user.id

    db = SessionLocal()
    try:
        user = UserRepository(db).get_by_username(username)
        if user is None:
            await update.message.reply_text(f"No account found for username {username!r}. Register on the dashboard first.")
            return

        if user.telegram_id == telegram_id:
            await update.message.reply_text(f"Already linked. Welcome back, {username}.")
            return

        if user.telegram_id is not None:
            await update.message.reply_text("This account is already linked to a different Telegram user.")
            return

        user.telegram_id = telegram_id
        db.commit()
        await update.message.reply_text(f"Linked! Welcome, {username}.")
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


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        if _resolve_user(db, update) is None:
            await update.message.reply_text(_NOT_LINKED_MESSAGE)
            return
    finally:
        db.close()

    market_status = get_market_data_provider().get_market_status()
    state = "OPEN" if market_status.is_open else "CLOSED"
    await update.message.reply_text(f"Market is {state} (as of {market_status.as_of:%Y-%m-%d %H:%M %Z})")


async def positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = SessionLocal()
    try:
        if _resolve_user(db, update) is None:
            await update.message.reply_text(_NOT_LINKED_MESSAGE)
            return
    finally:
        db.close()

    # Position tracking is built in Phase 10 — until then this is always
    # true (no position can exist yet), not a placeholder pretending success.
    await update.message.reply_text("You have no active positions.")


async def _decide(update: Update, context: ContextTypes.DEFAULT_TYPE, decision_type: DecisionType) -> None:
    command = decision_type.value.upper()
    if not context.args:
        await update.message.reply_text(f"Usage: /{decision_type.value} <signal_id>")
        return

    try:
        signal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("signal_id must be a number.")
        return

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

        await update.message.reply_text(f"Recorded: {command} on signal {signal_id}.")
    finally:
        db.close()


async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _decide(update, context, DecisionType.OPEN)


async def ignore_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _decide(update, context, DecisionType.IGNORE)
