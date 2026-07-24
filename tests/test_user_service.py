from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.domain.enums import AlertPreference, RiskPreference, TradingStyle
from app.services.user_service import UserService


def _create_jake(service: UserService):
    return service.create_user(
        username="jake",
        email="jake@example.com",
        password_hash="hashed-not-a-real-password",
        account_size=Decimal("1000.00"),
        risk_preference=RiskPreference.AGGRESSIVE,
        trading_style=TradingStyle.MOMENTUM,
    )


def _create_friend(service: UserService):
    return service.create_user(
        username="friend",
        email="friend@example.com",
        password_hash="hashed-not-a-real-password",
        account_size=Decimal("5000.00"),
        risk_preference=RiskPreference.CONSERVATIVE,
        trading_style=TradingStyle.SWING,
        alert_preference=AlertPreference.HIGH_CONFIDENCE_ONLY,
    )


def test_create_user_creates_user_and_profile_together(db_session: Session) -> None:
    service = UserService(db_session)

    jake = _create_jake(service)

    assert jake.id is not None
    profile = service.get_profile(requesting_user_id=jake.id, target_user_id=jake.id)
    assert profile.account_size == Decimal("1000.00")
    assert profile.risk_preference == RiskPreference.AGGRESSIVE
    assert profile.trading_style == TradingStyle.MOMENTUM
    assert profile.alert_preference == AlertPreference.ALL_SIGNALS


def test_duplicate_username_is_rejected(db_session: Session) -> None:
    service = UserService(db_session)
    _create_jake(service)

    with pytest.raises(ConflictError):
        service.create_user(
            username="jake",
            email="someone-else@example.com",
            password_hash="x",
            account_size=Decimal("100"),
            risk_preference=RiskPreference.MODERATE,
            trading_style=TradingStyle.SWING,
        )


def test_duplicate_email_is_rejected(db_session: Session) -> None:
    service = UserService(db_session)
    _create_jake(service)

    with pytest.raises(ConflictError):
        service.create_user(
            username="someone-else",
            email="jake@example.com",
            password_hash="x",
            account_size=Decimal("100"),
            risk_preference=RiskPreference.MODERATE,
            trading_style=TradingStyle.SWING,
        )


def test_user_cannot_read_another_users_profile(db_session: Session) -> None:
    service = UserService(db_session)
    jake = _create_jake(service)
    friend = _create_friend(service)

    with pytest.raises(ForbiddenError):
        service.get_profile(requesting_user_id=jake.id, target_user_id=friend.id)

    with pytest.raises(ForbiddenError):
        service.get_profile(requesting_user_id=friend.id, target_user_id=jake.id)


def test_two_users_have_correctly_isolated_profile_data(db_session: Session) -> None:
    service = UserService(db_session)
    jake = _create_jake(service)
    friend = _create_friend(service)

    jake_profile = service.get_profile(requesting_user_id=jake.id, target_user_id=jake.id)
    friend_profile = service.get_profile(requesting_user_id=friend.id, target_user_id=friend.id)

    assert jake_profile.risk_preference == RiskPreference.AGGRESSIVE
    assert jake_profile.account_size == Decimal("1000.00")
    assert friend_profile.risk_preference == RiskPreference.CONSERVATIVE
    assert friend_profile.account_size == Decimal("5000.00")


def test_get_profile_for_missing_user_raises_not_found(db_session: Session) -> None:
    service = UserService(db_session)

    with pytest.raises(NotFoundError):
        service.get_profile(requesting_user_id=999, target_user_id=999)


def test_update_profile_only_changes_provided_fields(db_session: Session) -> None:
    service = UserService(db_session)
    jake = _create_jake(service)

    updated = service.update_profile(
        requesting_user_id=jake.id,
        target_user_id=jake.id,
        account_size=Decimal("2500.00"),
    )

    assert updated.account_size == Decimal("2500.00")
    assert updated.risk_preference == RiskPreference.AGGRESSIVE  # unchanged
    assert updated.trading_style == TradingStyle.MOMENTUM  # unchanged


def test_update_profile_is_isolated(db_session: Session) -> None:
    service = UserService(db_session)
    jake = _create_jake(service)
    friend = _create_friend(service)

    with pytest.raises(ForbiddenError):
        service.update_profile(
            requesting_user_id=friend.id,
            target_user_id=jake.id,
            account_size=Decimal("999999"),
        )
