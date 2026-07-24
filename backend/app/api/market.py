from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.database.models.user import User
from app.market.factory import get_market_data_provider
from app.schemas.market import MarketStatusRead

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/status", response_model=MarketStatusRead)
def get_market_status(_current_user: User = Depends(get_current_user)) -> MarketStatusRead:
    status = get_market_data_provider().get_market_status()
    return MarketStatusRead(is_open=status.is_open, session=status.session, as_of=status.as_of)
