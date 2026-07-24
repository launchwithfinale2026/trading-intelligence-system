from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.telegram_event import TelegramEvent
from app.repositories.base import BaseRepository


class TelegramEventRepository(BaseRepository[TelegramEvent]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, TelegramEvent)

    def log(self, *, kind: str, chat_id: int | None = None, text: str | None = None) -> TelegramEvent:
        return self.add(TelegramEvent(kind=kind, chat_id=chat_id, text=text))

    def count_since(self, *, kind: str, since: datetime) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(TelegramEvent)
                .where(TelegramEvent.kind == kind, TelegramEvent.created_at >= since)
            )
            or 0
        )
