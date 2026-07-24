from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.database import get_db
from app.database.models.user import User
from app.schemas.profile import ProfileRead, ProfileUpdate
from app.schemas.user import UserRead
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me/profile", response_model=ProfileRead)
def update_current_user_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileRead:
    service = UserService(db)
    profile = service.update_profile(
        requesting_user_id=current_user.id,
        target_user_id=current_user.id,
        **payload.model_dump(exclude_unset=True),
    )
    return ProfileRead.model_validate(profile)
