from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.user import User
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.watchlist import WatchlistSymbolCreate, WatchlistSymbolRead
from app.services.watchlist_service import WatchlistService

router = APIRouter(prefix="/users/me/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistSymbolRead])
def list_my_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WatchlistSymbolRead]:
    symbols = WatchlistRepository(db).list_for_user(current_user.id)
    return [WatchlistSymbolRead.model_validate(s) for s in symbols]


@router.post("", response_model=WatchlistSymbolRead, status_code=status.HTTP_201_CREATED)
def add_to_my_watchlist(
    payload: WatchlistSymbolCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WatchlistSymbolRead:
    entry = WatchlistService(db).add_symbol(current_user.id, payload.symbol)
    return WatchlistSymbolRead.model_validate(entry)


@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_my_watchlist(
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    WatchlistService(db).remove_symbol(current_user.id, symbol)
