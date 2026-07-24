from decimal import Decimal

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.database.models.base import TimestampMixin
from app.domain.enums import AlertPreference, RiskPreference, TradingStyle


class Profile(TimestampMixin, Base):
    """A user's trading configuration.

    One-to-one with User (enforced by the unique constraint on user_id).
    Kept separate from User rather than flattened onto it because profile
    fields are trading-domain configuration, while User is login identity —
    the two change for different reasons and are read by different code
    paths (auth vs. risk/signal generation).
    """

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    account_size: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    risk_preference: Mapped[RiskPreference] = mapped_column(
        SAEnum(RiskPreference, native_enum=False, length=32), nullable=False
    )
    trading_style: Mapped[TradingStyle] = mapped_column(
        SAEnum(TradingStyle, native_enum=False, length=32), nullable=False
    )
    alert_preference: Mapped[AlertPreference] = mapped_column(
        SAEnum(AlertPreference, native_enum=False, length=32),
        nullable=False,
        default=AlertPreference.ALL_SIGNALS,
    )

    user: Mapped["User"] = relationship(back_populates="profile")

    def __repr__(self) -> str:
        return f"Profile(id={self.id}, user_id={self.user_id}, risk={self.risk_preference})"
