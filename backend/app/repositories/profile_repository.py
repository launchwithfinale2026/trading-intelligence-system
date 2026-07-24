from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.profile import Profile
from app.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Profile)

    def get_by_user_id(self, user_id: int) -> Profile | None:
        return self.db.scalar(select(Profile).where(Profile.user_id == user_id))
