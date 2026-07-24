from decimal import Decimal

from sqlalchemy import JSON, Enum as SAEnum, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.database.models.base import TimestampMixin
from app.domain.enums import SignalDirection


class Signal(TimestampMixin, Base):
    """A trade idea a strategy produced, independent of any user's decision
    on it. One Signal can generate a Decision per user who was alerted
    (Phase 9/11) — Signal itself doesn't belong to a user.
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    direction: Mapped[SignalDirection] = mapped_column(
        SAEnum(SignalDirection, native_enum=False, length=16), nullable=False
    )
    entry: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    target: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    reasoning: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    def __repr__(self) -> str:
        return f"Signal(id={self.id}, symbol={self.symbol!r}, strategy={self.strategy_name!r})"
