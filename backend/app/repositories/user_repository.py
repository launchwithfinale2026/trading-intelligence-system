from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, User)

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self.db.scalar(select(User).where(User.telegram_id == telegram_id))
