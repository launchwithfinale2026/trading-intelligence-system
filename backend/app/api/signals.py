from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.user import User
from app.schemas.signal import SignalRead
from app.services.signal_service import SignalService

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalRead])
def list_recent_signals(
    limit: int = Query(default=50, ge=1, le=200),
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SignalRead]:
    signals = SignalService(db).list_recent(limit)
    return [SignalRead.model_validate(signal) for signal in signals]
