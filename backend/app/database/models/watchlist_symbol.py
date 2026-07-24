from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.database.models.base import TimestampMixin


class WatchlistSymbol(TimestampMixin, Base):
    """One symbol on one user's personal watchlist.

    A user with zero rows here watches the system default universe (see
    market/universe.py) — an empty watchlist means "no customization yet,"
    not "watch nothing." Once a user adds at least one symbol, the scanner
    only alerts them for symbols they've explicitly added (see
    engine/pipeline.py's _is_watching).
    """

    __tablename__ = "watchlist_symbols"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)

    def __repr__(self) -> str:
        return f"WatchlistSymbol(user_id={self.user_id}, symbol={self.symbol!r})"
