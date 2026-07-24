from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.database.models.base import TimestampMixin


class TelegramEvent(TimestampMixin, Base):
    """A log of outbound messages the bot has sent (alerts, position-closed
    alerts, startup/shutdown/system notices, errors) — kept so /status can
    report real counts like "alerts sent today" instead of a guess.
    """

    __tablename__ = "telegram_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"TelegramEvent(kind={self.kind!r}, chat_id={self.chat_id})"
