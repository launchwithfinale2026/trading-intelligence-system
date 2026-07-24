from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.user import User
from app.repositories.decision_repository import DecisionRepository
from app.repositories.position_repository import PositionRepository
from app.schemas.decision import DecisionRead
from app.schemas.position import PositionRead

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/positions", response_model=list[PositionRead])
def list_my_positions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PositionRead]:
    positions = PositionRepository(db).list_for_user(current_user.id)
    return [PositionRead.model_validate(p) for p in positions]


@router.get("/decisions", response_model=list[DecisionRead])
def list_my_decisions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DecisionRead]:
    decisions = DecisionRepository(db).list_for_user(current_user.id)
    return [DecisionRead.model_validate(d) for d in decisions]
