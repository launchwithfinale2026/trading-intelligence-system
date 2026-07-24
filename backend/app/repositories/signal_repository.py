from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.signal import Signal
from app.repositories.base import BaseRepository


class SignalRepository(BaseRepository[Signal]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Signal)

    def list_recent(self, limit: int = 50) -> list[Signal]:
        # id DESC as a tiebreaker: created_at has only 1-second resolution on
        # SQLite, so signals inserted within the same second would otherwise
        # sort arbitrarily rather than in actual insertion order.
        stmt = select(Signal).order_by(Signal.created_at.desc(), Signal.id.desc()).limit(limit)
        return list(self.db.scalars(stmt))
