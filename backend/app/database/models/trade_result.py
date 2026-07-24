from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.database.models.base import TimestampMixin


class TradeResult(TimestampMixin, Base):
    """The outcome of one closed position: win/loss, R-multiple, P/L.

    Computed once at close time and persisted here (rather than
    recomputed from Position on every read) so aggregate performance
    queries don't need to re-derive win/loss logic from raw position data,
    and so historical results stay stable even if position-closing logic
    changes later.
    """

    __tablename__ = "trade_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    position_id: Mapped[int] = mapped_column(
        ForeignKey("positions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    is_win: Mapped[bool] = mapped_column(Boolean, nullable=False)
    r_multiple: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    pnl: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    def __repr__(self) -> str:
        return f"TradeResult(position_id={self.position_id}, is_win={self.is_win}, r_multiple={self.r_multiple})"
