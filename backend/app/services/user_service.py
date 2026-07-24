from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.database.models.profile import Profile
from app.database.models.user import User
from app.domain.enums import AlertPreference, RiskPreference, TradingStyle
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository


class UserService:
    """Business rules for users and profiles.

    Every method that reads or writes another user's data takes an explicit
    `requesting_user_id` and enforces that it matches the target — this is
    the one place isolation is enforced, so every API route (and, later,
    every Telegram handler) goes through here rather than the repositories
    directly.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.profiles = ProfileRepository(db)

    def create_user(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        account_size: Decimal,
        risk_preference: RiskPreference,
        trading_style: TradingStyle,
        alert_preference: AlertPreference = AlertPreference.ALL_SIGNALS,
    ) -> User:
        if self.users.get_by_username(username) is not None:
            raise ConflictError(f"username {username!r} is already taken")
        if self.users.get_by_email(email) is not None:
            raise ConflictError(f"email {email!r} is already registered")

        user = self.users.add(User(username=username, email=email, password_hash=password_hash))
        self.profiles.add(
            Profile(
                user_id=user.id,
                account_size=account_size,
                risk_preference=risk_preference,
                trading_style=trading_style,
                alert_preference=alert_preference,
            )
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"user {user_id} not found")
        return user

    def get_profile(self, *, requesting_user_id: int, target_user_id: int) -> Profile:
        if requesting_user_id != target_user_id:
            raise ForbiddenError("cannot access another user's profile")

        profile = self.profiles.get_by_user_id(target_user_id)
        if profile is None:
            raise NotFoundError(f"profile for user {target_user_id} not found")
        return profile

    def update_profile(
        self,
        *,
        requesting_user_id: int,
        target_user_id: int,
        account_size: Decimal | None = None,
        risk_preference: RiskPreference | None = None,
        trading_style: TradingStyle | None = None,
        alert_preference: AlertPreference | None = None,
    ) -> Profile:
        profile = self.get_profile(requesting_user_id=requesting_user_id, target_user_id=target_user_id)

        if account_size is not None:
            profile.account_size = account_size
        if risk_preference is not None:
            profile.risk_preference = risk_preference
        if trading_style is not None:
            profile.trading_style = trading_style
        if alert_preference is not None:
            profile.alert_preference = alert_preference

        self.db.commit()
        self.db.refresh(profile)
        return profile
