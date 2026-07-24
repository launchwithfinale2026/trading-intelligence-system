from sqlalchemy.orm import Session

from app.database.models.signal import Signal as SignalModel
from app.repositories.signal_repository import SignalRepository
from app.strategies.base import Signal as StrategySignal


class SignalService:
    """Persists strategy output and serves signal history.

    Signals aren't user-owned (they're broadcast candidates every alerted
    user sees), so unlike UserService there's no requesting-user isolation
    check here — anyone authenticated can read signal history.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.signals = SignalRepository(db)

    def record_signal(self, signal: StrategySignal) -> SignalModel:
        model = SignalModel(
            symbol=signal.symbol,
            strategy_name=signal.strategy_name,
            direction=signal.direction,
            entry=signal.entry,
            stop_loss=signal.stop_loss,
            target=signal.target,
            confidence=signal.confidence,
            reasoning=signal.reasoning,
        )
        self.signals.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def list_recent(self, limit: int = 50) -> list[SignalModel]:
        return self.signals.list_recent(limit)
