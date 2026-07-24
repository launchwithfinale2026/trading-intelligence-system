from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.database.models.base import TimestampMixin
from app.domain.enums import PositionStatus


class Position(TimestampMixin, Base):
    """An active or closed position opened from an accepted (OPEN) signal.

    entry/stop_loss/target/shares are captured at open time rather than
    read live off the Signal — the user's risk sizing is recomputed at the
    moment they OPEN (their account size may have changed since the alert
    was sent), so this is the authoritative record of what was actually
    opened, independent of anything that happens to the Signal afterward.
    """

    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("user_id", "signal_id", name="uq_position_user_signal"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), nullable=False)

    entry: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    target: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[PositionStatus] = mapped_column(
        SAEnum(PositionStatus, native_enum=False, length=16), nullable=False, default=PositionStatus.OPEN
    )
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"Position(id={self.id}, user_id={self.user_id}, signal_id={self.signal_id}, status={self.status})"
