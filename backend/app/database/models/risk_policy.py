from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.database.models.base import TimestampMixin


class RiskPolicy(TimestampMixin, Base):
    """A named, data-driven risk curve.

    `breakpoints` is a JSON list of [account_size, risk_percent] pairs
    (both stored as strings to preserve exact decimal precision — JSON has
    no decimal type), sorted by account_size. See risk/policy.py for how
    they're interpolated: flat below the first point, flat above the last,
    linear in between. A single breakpoint means "flat regardless of
    account size" — that's how conservative/moderate/aggressive are
    represented, with no separate "flat policy" concept needed.

    `name` matches a RiskPreference enum value — that's the join key
    RiskPolicyService uses to look up "the active policy" for a user's
    chosen preference at runtime. Editing thresholds/percentages is just
    editing this row's breakpoints; no code change or deploy required.
    """

    __tablename__ = "risk_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    breakpoints: Mapped[list] = mapped_column(JSON, nullable=False)

    def __repr__(self) -> str:
        return f"RiskPolicy(name={self.name!r})"
