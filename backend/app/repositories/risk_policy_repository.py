from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.risk_policy import RiskPolicy
from app.repositories.base import BaseRepository


class RiskPolicyRepository(BaseRepository[RiskPolicy]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, RiskPolicy)

    def get_by_name(self, name: str) -> RiskPolicy | None:
        return self.db.scalar(select(RiskPolicy).where(RiskPolicy.name == name))
