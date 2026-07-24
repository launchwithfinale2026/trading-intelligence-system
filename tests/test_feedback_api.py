from decimal import Decimal

from fastapi.testclient import TestClient

from app.domain.enums import PositionStatus, SignalDirection
from app.services.position_service import PositionService
from app.services.signal_service import SignalService
from app.strategies.base import Signal as StrategySignal

USER_PAYLOAD = {
    "username": "jake",
    "email": "jake@example.com",
    "password": "correct-horse-battery-staple",
    "profile": {
        "account_size": "100000.00",
        "risk_preference": "aggressive",
        "trading_style": "momentum",
    },
}


def _auth_token(client: TestClient) -> str:
    client.post("/auth/register", json=USER_PAYLOAD)
    response = client.post("/auth/login", data={"username": "jake", "password": "correct-horse-battery-staple"})
    return response.json()["access_token"]


def test_performance_requires_authentication(client: TestClient) -> None:
    response = client.get("/feedback/performance")

    assert response.status_code == 401


def test_performance_returns_empty_list_with_no_data(client: TestClient) -> None:
    token = _auth_token(client)

    response = client.get("/feedback/performance", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == []


def test_performance_reflects_a_closed_trade(client: TestClient) -> None:
    from app.repositories.user_repository import UserRepository

    token = _auth_token(client)

    session = client.session_factory()
    try:
        user = UserRepository(session).get_by_username("jake")
        signal = SignalService(session).record_signal(
            StrategySignal(
                symbol="NVDA",
                direction=SignalDirection.LONG,
                entry=Decimal("100.00"),
                stop_loss=Decimal("90.00"),
                target=Decimal("120.00"),
                confidence=80,
                reasoning=["fixture"],
                strategy_name="momentum",
            )
        )
        position_service = PositionService(session)
        position = position_service.open_position(user=user, signal=signal)
        position_service.close_position(position, close_price=Decimal("120.00"), status=PositionStatus.CLOSED_TARGET)

        from app.services.feedback_service import FeedbackService

        FeedbackService(session).record_trade_result(position=position, signal=signal)
    finally:
        session.close()

    response = client.get("/feedback/performance", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["strategy_name"] == "momentum"
    assert body[0]["wins"] == 1
    assert body[0]["win_rate"] == "100.0"
