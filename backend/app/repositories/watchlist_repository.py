from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.watchlist_symbol import WatchlistSymbol
from app.repositories.base import BaseRepository


class WatchlistRepository(BaseRepository[WatchlistSymbol]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, WatchlistSymbol)

    def list_for_user(self, user_id: int) -> list[WatchlistSymbol]:
        stmt = select(WatchlistSymbol).where(WatchlistSymbol.user_id == user_id).order_by(WatchlistSymbol.symbol)
        return list(self.db.scalars(stmt))

    def get_by_user_and_symbol(self, user_id: int, symbol: str) -> WatchlistSymbol | None:
        stmt = select(WatchlistSymbol).where(WatchlistSymbol.user_id == user_id, WatchlistSymbol.symbol == symbol)
        return self.db.scalar(stmt)

    def list_all_distinct_symbols(self) -> list[str]:
        stmt = select(WatchlistSymbol.symbol).distinct()
        return list(self.db.scalars(stmt))
