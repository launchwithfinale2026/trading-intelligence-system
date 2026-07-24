from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.database.database import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token
from app.schemas.user import UserRead, UserRegister
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> UserRead:
    service = UserService(db)
    user = service.create_user(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        account_size=payload.profile.account_size,
        risk_preference=payload.profile.risk_preference,
        trading_style=payload.profile.trading_style,
        alert_preference=payload.profile.alert_preference,
    )
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    user = UserRepository(db).get_by_username(form_data.username)
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise UnauthorizedError("invalid username or password")

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout() -> dict[str, str]:
    """Stateless logout.

    Access tokens are short-lived JWTs with no server-side session, so
    "logging out" means the client discards its token — there is nothing to
    invalidate server-side. This endpoint exists so clients have a
    consistent, documented call to make on logout.
    """
    return {"detail": "logged out"}
