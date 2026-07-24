from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.database.models.decision import Decision
from app.domain.enums import DecisionType
from app.repositories.decision_repository import DecisionRepository
from app.repositories.signal_repository import SignalRepository


class DecisionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.decisions = DecisionRepository(db)
        self.signals = SignalRepository(db)

    def record_decision(self, *, user_id: int, signal_id: int, decision: DecisionType) -> Decision:
        if self.signals.get(signal_id) is None:
            raise NotFoundError(f"signal {signal_id} not found")

        existing = self.decisions.get_by_user_and_signal(user_id, signal_id)
        if existing is not None:
            raise ConflictError(
                f"user {user_id} already recorded {existing.decision.value} for signal {signal_id}"
            )

        record = self.decisions.add(Decision(user_id=user_id, signal_id=signal_id, decision=decision))
        self.db.commit()
        self.db.refresh(record)
        return record
