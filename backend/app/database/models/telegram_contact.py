from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.database.models.base import TimestampMixin


class TelegramContact(TimestampMixin, Base):
    """Anyone who has ever messaged the bot, captured automatically on
    /start regardless of whether they have (or link) a dashboard User
    account. created_at is first contact, updated_at is last contact —
    TimestampMixin's onupdate does the "last seen" bookkeeping for free.
    """

    __tablename__ = "telegram_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"TelegramContact(telegram_id={self.telegram_id}, username={self.username!r})"
