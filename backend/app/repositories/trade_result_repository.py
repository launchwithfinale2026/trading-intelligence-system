from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.trade_result import TradeResult
from app.repositories.base import BaseRepository


class TradeResultRepository(BaseRepository[TradeResult]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, TradeResult)

    def get_by_position(self, position_id: int) -> TradeResult | None:
        return self.db.scalar(select(TradeResult).where(TradeResult.position_id == position_id))

    def list_all(self) -> list[TradeResult]:
        return list(self.db.scalars(select(TradeResult)))
