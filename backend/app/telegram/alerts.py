"""Formats a Signal + its sized position into the Telegram alert message,
and sends it to a specific user. Pure formatting is kept separate from the
send (network) step so the format itself is trivially unit-testable.
"""

import logging
import re

from telegram import Bot
from telegram.error import TelegramError

from app.database.models.position import Position
from app.database.models.signal import Signal
from app.database.models.user import User
from app.domain.enums import PositionStatus
from app.risk.calculator import PositionSize

logger = logging.getLogger(__name__)

# Embedded in every alert so a plain-text OPEN/IGNORE reply can be traced
# back to the signal it's replying to (see handlers.handle_text_reply).
_SIGNAL_ID_PATTERN = re.compile(r"Signal ID:\s*(\d+)")


def format_alert(signal: Signal, position_size: PositionSize) -> str:
    reasoning_lines = "\n".join(f"- {reason}" for reason in signal.reasoning)

    return (
        "🚨 HIGH QUALITY SETUP\n\n"
        f"Symbol: {signal.symbol}\n"
        f"Setup: {signal.strategy_name}\n"
        f"Direction: {signal.direction.value.upper()}\n"
        f"Entry: {signal.entry}\n"
        f"Position: {position_size.shares} shares (${position_size.position_value})\n"
        f"Stop: {signal.stop_loss}\n"
        f"Target: {signal.target}\n"
        f"Confidence: {signal.confidence}%\n\n"
        f"Reason:\n{reasoning_lines}\n\n"
        "Reply OPEN or IGNORE.\n"
        f"Signal ID: {signal.id}"
    )


def extract_signal_id(alert_text: str) -> int | None:
    match = _SIGNAL_ID_PATTERN.search(alert_text)
    return int(match.group(1)) if match else None


def format_position_closed_alert(position: Position, signal: Signal) -> str:
    is_win = position.status == PositionStatus.CLOSED_TARGET
    header = "✅ TAKE PROFIT ALERT" if is_win else "🛑 STOP LOSS ALERT"
    pnl_per_share = position.close_price - position.entry
    total_pnl = pnl_per_share * position.shares

    return (
        f"{header}\n\n"
        f"Symbol: {signal.symbol}\n"
        f"Entry: {position.entry}\n"
        f"Close: {position.close_price}\n"
        f"Shares: {position.shares}\n"
        f"P/L: {'+' if total_pnl >= 0 else ''}{total_pnl}\n\n"
        f"Signal ID: {signal.id}"
    )


async def send_alert(bot: Bot, user: User, signal: Signal, position_size: PositionSize) -> bool:
    """Sends the entry alert to one user. Returns False (logged, not
    raised) if the user has no linked Telegram account or the send
    otherwise fails — a delivery failure for one user must not abort
    alerting the rest.
    """
    return await _send_text(bot, user, format_alert(signal, position_size))


async def send_position_closed_alert(bot: Bot, user: User, position: Position, signal: Signal) -> bool:
    return await _send_text(bot, user, format_position_closed_alert(position, signal))


async def _send_text(bot: Bot, user: User, text: str) -> bool:
    if user.telegram_id is None:
        logger.warning("cannot message user %s: no linked Telegram account", user.id)
        return False

    return await send_message(bot, user.telegram_id, text)


async def send_message(bot: Bot, chat_id: int, text: str) -> bool:
    """Lowest-level reusable send: any chat_id, any text. Returns False
    (logged, not raised) on failure — one bad send must never take down a
    caller that's messaging several chats in a loop.
    """
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        return True
    except TelegramError as exc:
        logger.warning("failed to send message to chat %s: %s", chat_id, exc)
        return False


async def send_error(bot: Bot, chat_id: int, error_text: str) -> bool:
    return await send_message(bot, chat_id, f"⚠️ Error: {error_text}")


async def send_startup(bot: Bot, chat_ids: list[int]) -> None:
    for chat_id in chat_ids:
        await send_message(bot, chat_id, "Trading Intelligence System is online.")


async def send_shutdown(bot: Bot, chat_ids: list[int]) -> None:
    for chat_id in chat_ids:
        await send_message(bot, chat_id, "Trading Intelligence System is shutting down.")


async def send_system_notification(bot: Bot, chat_ids: list[int], text: str) -> None:
    for chat_id in chat_ids:
        await send_message(bot, chat_id, text)
