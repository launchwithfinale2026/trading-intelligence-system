from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.decision import Decision
from app.repositories.base import BaseRepository


class DecisionRepository(BaseRepository[Decision]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Decision)

    def get_by_user_and_signal(self, user_id: int, signal_id: int) -> Decision | None:
        stmt = select(Decision).where(Decision.user_id == user_id, Decision.signal_id == signal_id)
        return self.db.scalar(stmt)

    def list_for_user(self, user_id: int) -> list[Decision]:
        stmt = select(Decision).where(Decision.user_id == user_id).order_by(Decision.created_at.desc(), Decision.id.desc())
        return list(self.db.scalars(stmt))
