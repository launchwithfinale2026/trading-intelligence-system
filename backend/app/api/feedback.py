from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.user import User
from app.schemas.feedback import StrategyPerformanceRead
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/performance", response_model=list[StrategyPerformanceRead])
def get_performance_by_strategy(
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StrategyPerformanceRead]:
    performance = FeedbackService(db).get_performance_by_strategy()
    return [StrategyPerformanceRead.model_validate(p) for p in performance]
