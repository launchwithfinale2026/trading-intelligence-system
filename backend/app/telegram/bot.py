"""Telegram bot bootstrap.

Runs as its own process, separate from the FastAPI app — the API server
shouldn't fail to start just because no Telegram bot token is configured
yet, and a long-polling bot has a different lifecycle (run forever) than a
request/response web server.

    python -m app.telegram.bot
"""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.database import SessionLocal
from app.repositories.telegram_event_repository import TelegramEventRepository
from app.repositories.user_repository import UserRepository
from app.telegram import handlers
from app.telegram.alerts import send_shutdown, send_startup

logger = logging.getLogger(__name__)


def _linked_chat_ids() -> list[int]:
    db = SessionLocal()
    try:
        return [user.telegram_id for user in UserRepository(db).list() if user.telegram_id is not None]
    finally:
        db.close()


async def _on_startup(application: Application) -> None:
    chat_ids = _linked_chat_ids()
    await send_startup(application.bot, chat_ids)
    if chat_ids:
        db = SessionLocal()
        try:
            TelegramEventRepository(db).log(kind="startup", text="bot started")
            db.commit()
        finally:
            db.close()
    logger.info("startup message sent to %d linked chat(s)", len(chat_ids))


async def _on_shutdown(application: Application) -> None:
    chat_ids = _linked_chat_ids()
    await send_shutdown(application.bot, chat_ids)
    logger.info("shutdown message sent to %d linked chat(s)", len(chat_ids))


async def _on_error(update: Update | None, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("unhandled error while processing update %s", update, exc_info=context.error)


def build_application() -> Application:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Create a bot via @BotFather and set it in .env before running the bot."
        )

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_on_startup)
        .post_shutdown(_on_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("ping", handlers.ping))
    application.add_handler(CommandHandler("profile", handlers.profile))
    application.add_handler(CommandHandler("status", handlers.status))
    application.add_handler(CommandHandler("positions", handlers.positions))
    application.add_handler(CommandHandler("open", handlers.open_command))
    application.add_handler(CommandHandler("ignore", handlers.ignore_command))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handlers.handle_text_reply))
    application.add_error_handler(_on_error)
    return application


def run_bot() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = build_application()
    logger.info("Telegram bot starting (long polling)")
    # run_polling retries transparently on transient network errors — see
    # python-telegram-bot's Updater internals — so no hand-rolled reconnect
    # loop is needed here.
    application.run_polling()


if __name__ == "__main__":
    run_bot()
