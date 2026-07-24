from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.position import Position
from app.domain.enums import PositionStatus
from app.repositories.base import BaseRepository


class PositionRepository(BaseRepository[Position]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Position)

    def get_by_user_and_signal(self, user_id: int, signal_id: int) -> Position | None:
        stmt = select(Position).where(Position.user_id == user_id, Position.signal_id == signal_id)
        return self.db.scalar(stmt)

    def list_open(self) -> list[Position]:
        stmt = select(Position).where(Position.status == PositionStatus.OPEN)
        return list(self.db.scalars(stmt))

    def list_open_for_user(self, user_id: int) -> list[Position]:
        stmt = select(Position).where(Position.user_id == user_id, Position.status == PositionStatus.OPEN)
        return list(self.db.scalars(stmt))

    def list_for_user(self, user_id: int) -> list[Position]:
        stmt = select(Position).where(Position.user_id == user_id).order_by(Position.created_at.desc(), Position.id.desc())
        return list(self.db.scalars(stmt))
