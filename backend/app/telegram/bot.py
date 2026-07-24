"""Telegram bot bootstrap.

Runs as its own process, separate from the FastAPI app — the API server
shouldn't fail to start just because no Telegram bot token is configured
yet, and a long-polling bot has a different lifecycle (run forever) than a
request/response web server.

    python -m app.telegram.bot
"""

import logging

from telegram.ext import Application, CommandHandler

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.telegram import handlers

logger = logging.getLogger(__name__)


def build_application() -> Application:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Create a bot via @BotFather and set it in .env before running the bot."
        )

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("profile", handlers.profile))
    application.add_handler(CommandHandler("status", handlers.status))
    application.add_handler(CommandHandler("positions", handlers.positions))
    application.add_handler(CommandHandler("open", handlers.open_command))
    application.add_handler(CommandHandler("ignore", handlers.ignore_command))
    return application


def run_bot() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = build_application()
    logger.info("Telegram bot starting (long polling)")
    application.run_polling()


if __name__ == "__main__":
    run_bot()
