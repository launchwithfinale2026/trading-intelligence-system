"""SQLAlchemy models. Import every model here so Base.metadata and Alembic's
autogenerate can discover them from a single import.
"""

from app.database.database import Base
from app.database.models.decision import Decision
from app.database.models.position import Position
from app.database.models.profile import Profile
from app.database.models.signal import Signal
from app.database.models.trade_result import TradeResult
from app.database.models.user import User

__all__ = ["Base", "User", "Profile", "Signal", "Decision", "Position", "TradeResult"]
