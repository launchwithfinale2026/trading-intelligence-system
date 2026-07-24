from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.database.models.watchlist_symbol import WatchlistSymbol
from app.repositories.watchlist_repository import WatchlistRepository


class WatchlistService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.watchlist = WatchlistRepository(db)

    def list_symbols(self, user_id: int) -> list[WatchlistSymbol]:
        return self.watchlist.list_for_user(user_id)

    def add_symbol(self, user_id: int, symbol: str) -> WatchlistSymbol:
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol must not be empty")
        if self.watchlist.get_by_user_and_symbol(user_id, symbol) is not None:
            raise ConflictError(f"{symbol} is already on your watchlist")

        entry = self.watchlist.add(WatchlistSymbol(user_id=user_id, symbol=symbol))
        self.db.commit()
        return entry

    def remove_symbol(self, user_id: int, symbol: str) -> None:
        symbol = symbol.strip().upper()
        entry = self.watchlist.get_by_user_and_symbol(user_id, symbol)
        if entry is None:
            raise NotFoundError(f"{symbol} is not on your watchlist")

        self.watchlist.delete(entry)
        self.db.commit()
