from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.telegram_contact import TelegramContact
from app.repositories.base import BaseRepository


class TelegramContactRepository(BaseRepository[TelegramContact]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, TelegramContact)

    def get_by_telegram_id(self, telegram_id: int) -> TelegramContact | None:
        return self.db.scalar(select(TelegramContact).where(TelegramContact.telegram_id == telegram_id))

    def upsert(
        self,
        *,
        telegram_id: int,
        chat_id: int,
        username: str | None,
        first_name: str | None,
    ) -> TelegramContact:
        """Records or refreshes a contact's info. updated_at (bumped by
        TimestampMixin's onupdate) doubles as "last seen".
        """
        contact = self.get_by_telegram_id(telegram_id)
        if contact is None:
            return self.add(
                TelegramContact(telegram_id=telegram_id, chat_id=chat_id, username=username, first_name=first_name)
            )

        contact.chat_id = chat_id
        contact.username = username
        contact.first_name = first_name
        self.db.flush()
        return contact
