"""Formats a Signal + its sized position into the Telegram alert message,
and sends it to a specific user. Pure formatting is kept separate from the
send (network) step so the format itself is trivially unit-testable.
"""

import logging
import re

from telegram import Bot
from telegram.error import TelegramError

from app.database.models.signal import Signal
from app.database.models.user import User
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
        f"Strategy: {signal.strategy_name}\n"
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


async def send_alert(bot: Bot, user: User, signal: Signal, position_size: PositionSize) -> bool:
    """Sends the alert to one user. Returns False (logged, not raised) if
    the user has no linked Telegram account or the send otherwise fails —
    a delivery failure for one user must not abort alerting the rest.
    """
    if user.telegram_id is None:
        logger.warning("cannot alert user %s: no linked Telegram account", user.id)
        return False

    try:
        await bot.send_message(chat_id=user.telegram_id, text=format_alert(signal, position_size))
        return True
    except TelegramError as exc:
        logger.warning("failed to send alert to user %s: %s", user.id, exc)
        return False
