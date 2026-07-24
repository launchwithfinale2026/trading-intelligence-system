from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.database.models.base import TimestampMixin
from app.domain.enums import DecisionType


class Decision(TimestampMixin, Base):
    """A user's OPEN/IGNORE response to a signal.

    One decision per (user, signal) — the unique constraint makes replaying
    /open or /ignore on the same signal a clear conflict rather than a
    silent duplicate. Position creation on OPEN happens in Phase 10; this
    table only records the decision itself.
    """

    __tablename__ = "decisions"
    __table_args__ = (UniqueConstraint("user_id", "signal_id", name="uq_decision_user_signal"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), nullable=False)
    decision: Mapped[DecisionType] = mapped_column(
        SAEnum(DecisionType, native_enum=False, length=16), nullable=False
    )

    def __repr__(self) -> str:
        return f"Decision(user_id={self.user_id}, signal_id={self.signal_id}, decision={self.decision})"
